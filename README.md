# Rishat

Django + Stripe payments.

## Docker quick start

```bash
# 1. Copy and fill in secrets
cp .env.example .env
# Edit .env — set DJANGO_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, STRIPE_SECRET_KEY

# 2. Build and start
docker compose up --build -d

# 3. Create a superuser
docker compose run --rm -it web python manage.py createsuperuser

# 4. Run migrations again (if needed)
docker compose run --rm migrate

# 5. Watch logs
docker compose logs -f web

# 6. Stop
docker compose down
```

## Local development

```bash
cp .env.example .env
# Fill in secrets

uv sync
uv run python manage.py migrate
uv run python manage.py runserver
```
