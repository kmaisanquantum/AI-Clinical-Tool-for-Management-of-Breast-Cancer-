# Clinical Decision-Support Platform (Breast Cancer, PNG)

Clinical decision SUPPORT only. Not a diagnostic device. Synthetic data only until
clinical-governance, privacy and regulatory review is complete.

## Quick start (Stage 1)
    cp .env.example .env
    docker compose up --build -d
    curl http://127.0.0.1:8000/api/v1/health/
    docker compose exec backend pytest -q

Web Interface: http://127.0.0.1:8000/
API docs: http://127.0.0.1:8000/api/v1/docs/

## Creating an Admin User
After deploying (e.g. via Coolify or Docker), create an admin user using the container terminal:

```bash
python manage.py createsuperuser
```

Or seed demo users (`oncologist`, `registrar`, `analyst` with password `DemoPass!2025`):

```bash
python manage.py seed_demo
```

See docs/architecture/architecture.md, docs/deployment/nixpacks.md and docs/deployment/vultr.md.
