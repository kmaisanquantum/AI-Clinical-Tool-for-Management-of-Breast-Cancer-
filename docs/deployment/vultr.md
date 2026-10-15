# GitHub + Vultr setup (run on YOUR machine/server)

## A. GitHub (local machine, after unzipping)
    cd cdsp
    git init -b main
    git add . && git commit -m "Stage 1: repository foundation"
    gh repo create clinical-decision-support --private --source=. --push
Without gh: create a private repo on github.com, then
    git remote add origin git@github.com:<you>/clinical-decision-support.git && git push -u origin main
Then protect `main` (require PR + passing CI), enable secret scanning and Dependabot.

## B. Vultr server
1. Deploy Ubuntu 24.04 with your SSH key; Vultr firewall: SSH only.
2. scp scripts/vps_bootstrap.sh root@<SERVER_IP>:/root/
3. ssh root@<SERVER_IP> "DEPLOY_USER=deploy bash /root/vps_bootstrap.sh"
4. In a NEW terminal confirm `ssh deploy@<SERVER_IP>` works before closing the root session.

## C. Run
    ssh deploy@<SERVER_IP>
    git clone git@github.com:<you>/clinical-decision-support.git && cd clinical-decision-support
    cp .env.example .env     # set strong DJANGO_SECRET_KEY and POSTGRES_PASSWORD
    python3 -c "import secrets;print(secrets.token_urlsafe(50))"
    docker compose up --build -d
    curl http://127.0.0.1:8000/api/v1/health/
    docker compose exec backend pytest -q
Docs via tunnel: ssh -L 8000:127.0.0.1:8000 deploy@<SERVER_IP>, then open http://localhost:8000/api/v1/docs/

## Verify
health = {"status":"ok","database":"ok"}; nothing public on 5432; `sudo ufw status` shows SSH only; CI green.
