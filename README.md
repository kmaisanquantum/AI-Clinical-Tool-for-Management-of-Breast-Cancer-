# Clinical Decision-Support Platform (Breast Cancer, PNG)

Clinical decision SUPPORT only. Not a diagnostic device. Synthetic data only until
clinical-governance, privacy and regulatory review is complete.

## Quick start (Stage 1)
    cp .env.example .env
    docker compose up --build -d
    curl http://127.0.0.1:8000/api/v1/health/
    docker compose exec backend pytest -q

API docs: http://127.0.0.1:8000/api/v1/docs/
See docs/architecture/architecture.md, docs/deployment/nixpacks.md and docs/deployment/vultr.md.
