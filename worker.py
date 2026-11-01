"""notification-worker : worker de fond de QuickShop (aucun port, aucune URL).

Toutes les POLL_SECONDS secondes, il :
  1. récupère dans order-service les commandes pas encore notifiées et envoie la confirmation au client ;
  2. surveille les produits en stock bas dans catalog-service et lève une alerte ;
  3. signale qu'il est vivant à order-service (visible dans l'écran Architecture) et écrit un heartbeat dans /tmp.
"""
import json
import os
import signal
import socket
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

ORDERS_URL = os.getenv("ORDERS_URL", "http://order-service:8002").rstrip("/")
CATALOG_URL = os.getenv("CATALOG_URL", "http://catalog-service:8001").rstrip("/")
POLL_SECONDS = max(1, int(os.getenv("POLL_SECONDS", "5")))
WORKER_NAME = os.getenv("WORKER_NAME", "notification-worker")
HEARTBEAT_FILE = os.getenv("HEARTBEAT_FILE", "/tmp/notification-worker-heartbeat")
HOSTNAME = socket.gethostname()

running = True


def log(level, message, **fields):
    extra = "  " + " ".join(f"{k}={v}" for k, v in fields.items()) if fields else ""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"{now} {level.upper():5} {message}{extra}", flush=True)


def stop(signum, _frame):
    global running
    running = False
    log("info", f"Signal {signal.Signals(signum).name} reçu : arrêt après le cycle en cours")


def call(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as res:
        raw = res.read()
        return json.loads(raw) if raw else None


def reason(err):
    if isinstance(err, urllib.error.HTTPError):
        return f"HTTP {err.code}"
    if isinstance(err, urllib.error.URLError):
        return str(err.reason)
    return str(err)


class Worker:
    def __init__(self):
        self.sent = 0
        self.alerted = set()
        self.failing = {}  # dépendance -> True si en échec (évite de répéter le même avertissement)

    def guard(self, dependency, action):
        try:
            result = action()
            if self.failing.pop(dependency, False):
                log("info", f"{dependency} de nouveau joignable")
            return result
        except Exception as err:  # noqa: BLE001 - un service en panne ne doit pas arrêter le worker
            if not self.failing.get(dependency):
                log("warn", f"{dependency} injoignable, nouvelle tentative au prochain cycle", error=reason(err))
            self.failing[dependency] = True
            return None

    def send_notifications(self):
        orders = call("GET", f"{ORDERS_URL}/orders?notified=false") or []
        for o in sorted(orders, key=lambda x: x["id"]):
            articles = sum(i["quantity"] for i in o["items"])
            if o["status"] == "CANCELLED":
                message = f"Bonjour {o['customerName']}, votre commande {o['number']} a bien été annulée."
            else:
                message = (
                    f"Bonjour {o['customerName']}, votre commande {o['number']} "
                    f"({articles} article(s), {o['total']:.2f} €) est confirmée. Merci pour votre achat !"
                )
            # Ici on brancherait un vrai fournisseur d'emails (SMTP, SendGrid...) : on journalise l'envoi.
            log("info", f"Email envoyé à {o['customerEmail']}", order=o["number"], total=f"{o['total']:.2f}€")
            call("POST", f"{ORDERS_URL}/orders/{o['id']}/notification",
                 {"channel": "email", "message": message, "worker": HOSTNAME})
            self.sent += 1

    def check_stock(self):
        low = call("GET", f"{CATALOG_URL}/products?lowStock=true") or []
        current = {p["id"] for p in low}
        for p in low:
            if p["id"] not in self.alerted:
                state = "RUPTURE" if p["stock"] == 0 else f"plus que {p['stock']}"
                log("warn", f"Stock bas : {p['name']} ({state})", product=p["id"])
        for pid in self.alerted - current:
            log("info", "Stock rétabli", product=pid)
        self.alerted = current

    def report_alive(self):
        call("POST", f"{ORDERS_URL}/workers/heartbeat", {
            "name": WORKER_NAME, "hostname": HOSTNAME, "processed": self.sent, "lowStockCount": len(self.alerted),
        })

    def cycle(self):
        self.guard("order-service", self.send_notifications)
        self.guard("catalog-service", self.check_stock)
        self.guard("order-service", self.report_alive)
        try:
            with open(HEARTBEAT_FILE, "w", encoding="utf-8") as f:
                f.write(datetime.now(timezone.utc).isoformat())
        except OSError:
            pass


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    log("info", "Démarrage de notification-worker", worker=WORKER_NAME, host=HOSTNAME,
        orders=ORDERS_URL, catalog=CATALOG_URL, poll=f"{POLL_SECONDS}s", port="aucun")
    worker = Worker()
    while running:
        worker.cycle()
        deadline = time.monotonic() + POLL_SECONDS
        while running and time.monotonic() < deadline:
            time.sleep(0.2)
    log("info", "notification-worker arrêté", notificationsSent=worker.sent)


if __name__ == "__main__":
    main()
