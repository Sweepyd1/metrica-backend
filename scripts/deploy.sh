#!/usr/bin/env bash
# Обновление Метрики до последней версии из git.
# Запуск:  sudo /opt/metrica/deploy.sh
set -euo pipefail

BACKEND=/opt/metrica/backend
FRONTEND=/opt/metrica/frontend
WEBROOT=/var/www/metrica

echo "─── Бэкенд ────────────────────────────────"
cd "$BACKEND"
git pull --ff-only
docker compose build
docker compose up -d
echo "→ миграции"
docker compose run --rm api alembic upgrade head

echo "─── Фронтенд ──────────────────────────────"
cd "$FRONTEND"
git pull --ff-only
npm ci --no-audit --no-fund
npm run build
rm -rf "$WEBROOT".old
[ -d "$WEBROOT" ] && mv "$WEBROOT" "$WEBROOT".old
mkdir -p "$WEBROOT"
cp -r dist/* "$WEBROOT"/
chown -R www-data:www-data "$WEBROOT"

echo "─── nginx ─────────────────────────────────"
nginx -t && systemctl reload nginx

echo "─── Проверка ──────────────────────────────"
sleep 3
curl -s -o /dev/null -w "API  /api/openapi.json -> %{http_code}\n" http://127.0.0.1/api/openapi.json
curl -s -o /dev/null -w "SPA  /                 -> %{http_code}\n" http://127.0.0.1/
echo "Готово."
