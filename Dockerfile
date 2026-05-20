# linux/amd64 — совместимость с типичным VPS и обход SIGILL на ARM Mac
FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY index.py db.py payments.py ./

ENV DB_PATH=/data/bot.db
VOLUME /data

CMD ["python", "-u", "index.py"]
