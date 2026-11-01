# notification-worker : Python 3.12, bibliothèque standard uniquement. AUCUN port exposé.
FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ORDERS_URL=http://order-service:8002 \
    CATALOG_URL=http://catalog-service:8001 \
    POLL_SECONDS=5
WORKDIR /app
COPY worker.py healthcheck.py ./

# Non-root numérique ; seule écriture : le heartbeat dans /tmp
USER 1000:1000

HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 CMD ["python", "healthcheck.py"]

CMD ["python", "worker.py"]
