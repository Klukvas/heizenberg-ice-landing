#!/bin/bash
set -euo pipefail

# Usage: ./deploy.sh [image_tag]
# Example: ./deploy.sh latest
#          ./deploy.sh sha-abc1234

IMAGE_TAG="${1:-latest}"
DOCKER_IMAGE="${DOCKER_IMAGE:-heizenberg/ice}:${IMAGE_TAG}"

echo "=== Heizenberg Ice Deploy ==="
echo "Image: ${DOCKER_IMAGE}"

# Pre-flight checks
if [[ ! -f .env ]]; then
    echo "ERROR: .env file not found. Copy .env.example and fill in values." >&2
    exit 1
fi

for var in SECRET_KEY DB_PASSWORD DB_NAME DB_USER ALLOWED_HOSTS CELERY_BROKER_URL; do
    value=$(grep -E "^${var}=.+" .env | head -1 | cut -d= -f2-)
    if [[ -z "${value}" ]]; then
        echo "ERROR: Required variable ${var} is missing or empty in .env" >&2
        exit 1
    fi
done

echo "[1/5] Pulling image..."
docker pull "${DOCKER_IMAGE}"

echo "[2/5] Updating compose..."
export DOCKER_IMAGE="${DOCKER_IMAGE}"

echo "[3/5] Running migrations..."
docker compose run --rm app python manage.py migrate --noinput

echo "[4/5] Collecting static files..."
docker compose run --rm app python manage.py collectstatic --noinput

echo "[5/5] Starting services..."
docker compose up -d --remove-orphans

echo ""
echo "=== Deploy complete ==="
docker compose ps
