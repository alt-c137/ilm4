#!/bin/sh
# Резервная копия базы и загрузок ilm4. Запуск на сервере из папки проекта:
#   sh scripts/backup.sh
# По расписанию (каждую ночь в 3:30) — `crontab -e` и строка:
#   30 3 * * * cd /root/ilm4 && sh scripts/backup.sh >> backups/backup.log 2>&1
# Копии старше 14 дней удаляются. Держите копию и вне сервера (скачать / облако).
set -e
DC="docker compose -f docker-compose.prod.yml"
DIR=backups
STAMP=$(date +%Y-%m-%d_%H%M)
mkdir -p "$DIR"

$DC exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$DIR/db_$STAMP.dump"
$DC exec -T app tar -czf - -C /app media > "$DIR/media_$STAMP.tar.gz"

find "$DIR" -name 'db_*.dump' -mtime +14 -delete
find "$DIR" -name 'media_*.tar.gz' -mtime +14 -delete
echo "$STAMP: готово — $(du -sh "$DIR" | cut -f1) в $DIR/"

# Восстановление базы из копии:
#   docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean' < backups/db_<дата>.dump
