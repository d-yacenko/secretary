# VDS deployment (phase 01)

Target path: `/opt/secretary`

## First deploy

```bash
mkdir -p /opt/secretary
cd /opt/secretary
git clone https://github.com/d-yacenko/secretary.git .
cp .env.example .env
cd infra
docker compose -f compose.yaml -f compose.deploy.yaml up -d --build
curl -s http://127.0.0.1:18080/health
```

## Update

```bash
cd /opt/secretary
git pull
cd infra
docker compose -f compose.yaml -f compose.deploy.yaml up -d --build
```

`compose.deploy.yaml` binds API to `127.0.0.1:18080` and does not publish PostgreSQL on the host.

HTTPS via nginx + Certbot on `web-itx.duckdns.org` is a later step.
