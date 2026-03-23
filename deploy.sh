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

echo "[1/6] Pulling image..."
docker pull "${DOCKER_IMAGE}"

echo "[2/6] Updating compose..."
export DOCKER_IMAGE="${DOCKER_IMAGE}"

echo "[3/6] Running migrations..."
docker compose run --rm app python manage.py migrate --noinput

echo "[4/6] Creating superuser (skips if already exists)..."
docker compose run --rm app python manage.py createsuperuser --noinput 2>/dev/null || echo "  Superuser already exists, skipping."

echo "[5/6] Collecting static files..."
docker compose run --rm app python manage.py collectstatic --noinput

echo "[6/6] Starting services..."
docker compose up -d --remove-orphans

echo ""
echo "=== Deploy complete ==="
docker compose ps
