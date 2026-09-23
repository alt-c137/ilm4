# Образ приложения ilm4 для прода (ARCHITECTURE.md §8).
# Сборка: docker compose -f docker-compose.prod.yml up -d --build

# --- Слой 1: установка python-зависимостей ---
FROM python:3.12-slim AS builder
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements/base.txt requirements/base.txt
RUN pip install --no-cache-dir --prefix=/install -r requirements/base.txt

# --- Слой 2: рабочий образ ---
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
# GEOS/GDAL/PROJ — нужны Django-бэкенду PostGIS (DATABASE_URL=postgis://…), без них app не стартует
RUN apt-get update \
    && apt-get install -y --no-install-recommends gdal-bin \
    && rm -rf /var/lib/apt/lists/*
COPY --from=builder /install /usr/local
COPY . .
RUN chmod +x entrypoint.sh \
    && addgroup --system ilm4 \
    && adduser --system --ingroup ilm4 ilm4 \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R ilm4:ilm4 /app
USER ilm4
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
