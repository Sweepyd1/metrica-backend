#!/usr/bin/env bash
# Ежедневный бэкап базы и загруженных файлов.
# Ставится в cron:  0 3 * * * /opt/metrica/backup-db.sh >> /var/log/metrica-backup.log 2>&1
set -euo pipefail

BACKEND=/opt/metrica/backend
DEST=/var/backups/metrica
KEEP_DAYS=14
STAMP=$(date +%F_%H%M)

mkdir -p "$DEST"
cd "$BACKEND"

# shellcheck disable=SC1091
set -a; source .env; set +a

echo "[$(date +%F\ %T)] dump базы $DATABASE_DATABASE"
docker compose exec -T db pg_dump -U "$DATABASE_USER" -d "$DATABASE_DATABASE" -Fc \
    > "$DEST/db_$STAMP.dump"

echo "[$(date +%F\ %T)] архив uploads"
tar czf "$DEST/uploads_$STAMP.tar.gz" -C "$BACKEND" uploads

find "$DEST" -type f -mtime +$KEEP_DAYS -delete
echo "[$(date +%F\ %T)] готово: $(du -sh "$DEST" | cut -f1) в $DEST"

# ВАЖНО: бэкап на том же диске, что и база, спасает от кривой миграции,
# но не от смерти сервера. Раз в неделю копируй $DEST к себе на компьютер:
#   scp -r metrica@<IP>:/var/backups/metrica ./backups
# или настрой rclone на Яндекс.Диск / S3.
