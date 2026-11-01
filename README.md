# QuickShop · notification-worker

**Worker** de QuickShop (Python 3.12, bibliothèque standard uniquement) : **aucun port, aucune URL**.

Toutes les `POLL_SECONDS` secondes, il :
1. récupère dans **order-service** les commandes pas encore notifiées et envoie la confirmation (email simulé) ;
2. interroge **catalog-service** et journalise une alerte pour chaque produit en stock bas ;
3. envoie un signal de vie à order-service (visible dans l'écran Architecture) et écrit un heartbeat dans `/tmp`.

```bash
docker build -t notification-worker .
docker run -d -e ORDERS_URL=http://<order-service>:8002 -e CATALOG_URL=http://<catalog-service>:8001 notification-worker
docker logs -f <conteneur>
```

| Variable | Défaut | Rôle |
|---|---|---|
| `ORDERS_URL` | `http://order-service:8002` | URL interne d'order-service |
| `CATALOG_URL` | `http://catalog-service:8001` | URL interne de catalog-service |
| `POLL_SECONDS` | `5` | Intervalle entre deux cycles |
| `WORKER_NAME` | `notification-worker` | Nom affiché |

Si un service est injoignable, le worker ne s'arrête pas : il réessaie au cycle suivant.
Utilisateur non-root `1000:1000`, n'écrit que dans `/tmp`.
