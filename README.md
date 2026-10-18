# DevOps Pipeline

A containerized Flask web application with Docker, Docker Compose, automated testing, a GitHub Actions CI/CD pipeline, GitHub Container Registry publishing, Prometheus monitoring, and a prepared (but not yet enabled) staging deployment.

> **Repository:** https://github.com/Hager-83/devops-pipeline
> **Live / staging URL:** *not yet deployed* — the staging deployment workflow is implemented but gated off until a staging server is configured (see [Staging Deployment](#staging-deployment)).

## Architecture

```text
                    DevOps Pipeline
                         │
             ┌───────────┴───────────┐
             │                       │
        Flask App                Prometheus
       Container                 Container
        Port 5000                 Port 9090
             │                       │
             │ /metrics              │ scrape every 15s
             └───────────────────────┘
                    Docker Network

  GitHub Actions:  pytest  →  docker build + health check  →  push to GHCR
                   └────────── gated off until configured ──→  deploy staging
```

![Project Architecture](image.png)

## Project Structure

```text
devops-pipeline/
├── app/
│   ├── app.py                      # Flask app: /, /health, /metrics
│   └── requirements.txt            # Flask, Gunicorn, Prometheus exporter, pytest
├── tests/
│   └── test_app.py                 # 4 pytest tests
├── monitoring/
│   └── prometheus.yml              # Prometheus scrape configuration
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # CI: test → docker verify → publish → (gated) deploy
├── .dockerignore                   # Keeps build context clean
├── .env.example                    # Environment variable template
├── Dockerfile                      # python:3.12-slim + Gunicorn
├── docker-compose.yml              # Local stack: app + Prometheus
├── docker-compose.staging.yml      # Staging stack (prebuilt GHCR image)
├── pytest.ini
├── report.md                       # Initial project assessment
├── PROGRESS.md                     # Phase-by-phase development log
├── image.png
└── README.md
```

## Application Endpoints

| Endpoint   | Description                                  |
| ---------- | -------------------------------------------- |
| `/`        | Returns JSON: greeting + current `APP_ENV`   |
| `/health`  | Returns `{"status": "ok"}` — used by Docker, CI, and deploy checks |
| `/metrics` | Prometheus metrics (exposed by prometheus-flask-exporter) |

## Prerequisites

* Git, Docker, Docker Compose, Python 3.12+

```bash
git --version
docker --version
docker compose version
python3 --version
```

## Local Setup

```bash
git clone https://github.com/Hager-83/devops-pipeline.git
cd devops-pipeline
```

## Environment Configuration

| Variable   | Description               | Default | Example     |
| ---------- | ------------------------- | ------- | ----------- |
| `APP_ENV`  | Application environment   | `dev`   | `staging`   |
| `LOG_LEVEL`| Application logging level | `INFO`  | `DEBUG`     |

Copy the template and adjust if needed (`.env` is git-ignored and must never be committed):

```bash
cp .env.example .env
```

Docker Compose reads these variables and passes them into the container.

## Testing

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r app/requirements.txt
pytest -v
```

Four tests cover: the home endpoint, the health endpoint, response body
content, and Prometheus metrics exposure. The same tests run in CI.

## Docker

Build and run manually:

```bash
docker build -t devops-pipeline:local .
docker run -d --name devops-app -p 5000:5000 devops-pipeline:local
curl http://localhost:5000/health     # {"status":"ok"}
curl http://localhost:5000/metrics    # Prometheus exposition format
docker stop devops-app && docker rm devops-app
```

Notes on the Dockerfile:

* Base image `python:3.12-slim` (small, official)
* Dependencies installed before copying code (better layer caching)
* `HEALTHCHECK` probes `/health` every 30s — Docker reports the container as `healthy`/`unhealthy`
* The app is served by **Gunicorn** (`--bind 0.0.0.0:5000 app:app`), not the Flask dev server
* `.dockerignore` keeps `.venv`, `.git`, tests, and docs out of the build context

## Docker Compose (local stack)

```bash
docker compose up -d --build
docker compose ps          # app should report (healthy)
```

* App: http://localhost:5000
* Prometheus: http://localhost:9090

Stop everything:

```bash
docker compose down
```

## Monitoring

Prometheus scrapes the app every 15 seconds via the Docker network
(`monitoring/prometheus.yml` targets `app:5000/metrics`).

Verify:

1. Open http://localhost:9090 → **Status → Targets**
2. Job `devops-app` should be **UP**
3. Query `flask_http_request_total` to see live request counts

## Logging

The application writes structured **JSON** logs, one object per line:

```json
{"time": "2026-10-18 05:58:34,563", "level": "INFO", "msg": "index requested"}
```

The log level is controlled by `LOG_LEVEL`. View logs with:

```bash
docker compose logs app
```

(Gunicorn's own startup messages use a plain-text format; application log lines are the JSON ones.)

## CI/CD Pipeline (GitHub Actions)

Workflow: `.github/workflows/ci-cd.yml`, triggered on every push/PR to `main`.

| Job               | What it does | When it runs |
| ----------------- | ------------ | ------------ |
| `test`            | Installs dependencies, runs `pytest -v` | Every push / PR |
| `docker`          | Builds the image, starts a container, curls `/health`, `/metrics`, and `/`, prints logs, removes the container (`if: always()` so cleanup happens even on failure) | After `test` passes |
| `publish`         | Logs into GHCR with the built-in `GITHUB_TOKEN` (permission `packages: write` only), builds and pushes `:latest` and `:sha-<commit>` tags | Pushes to `main` only |
| `deploy-staging`  | SSHs to the staging server, copies the staging compose files, pulls the new image, starts the stack, then curls the staging `/health` | **Gated off** until `DEPLOY_STAGING` variable is set (see below) |

A failure in any required job fails the workflow, which blocks the jobs that depend on it (`needs:` chain: test → docker → publish → deploy-staging).

## Using the GHCR image

After the `publish` job has run at least once:

```bash
docker pull ghcr.io/hager-83/devops-pipeline:latest
# or pin to a commit
docker pull ghcr.io/hager-83/devops-pipeline:sha-<commit-sha>
```

Public packages need no login; if the package is private, log in first:
`docker login ghcr.io -u <username> -p <token>`.

## Staging Deployment

**Status: implemented in the workflow, not yet activated.** Nothing has been
deployed and no live URL exists yet.

The pieces that already exist:

* `docker-compose.staging.yml` — runs the prebuilt image
  `ghcr.io/hager-83/devops-pipeline:latest` with `APP_ENV=staging`,
  `restart: unless-stopped`, and the same health check
* The `deploy-staging` job in the workflow — SSH deploy + post-deploy health
  verification (a failed health check fails the job)

To activate it you need a staging server and must configure
**Settings → Secrets and variables → Actions** on the repository:

| Type     | Name              | Value                                   |
| -------- | ----------------- | --------------------------------------- |
| Secret   | `STAGING_HOST`    | Server IP or hostname                    |
| Secret   | `STAGING_USER`    | SSH username                             |
| Secret   | `STAGING_SSH_KEY` | Private key (the matching public key must be in the server's `authorized_keys`) |
| Secret   | `GHCR_PULL_TOKEN` | Optional — only if the GHCR package is private |
| Variable | `STAGING_URL`     | e.g. `http://staging.example.com`        |
| Variable | `DEPLOY_STAGING`  | `true` (enables the deploy job)          |

The server needs Docker + Docker Compose installed; the workflow deploys to
`~/devops-pipeline/` on the server.

## Troubleshooting

```bash
docker compose logs app          # application logs
docker compose logs prometheus   # Prometheus logs
docker compose ps                # container states (healthy/unhealthy)
curl http://localhost:5000/health
curl http://localhost:5000/metrics
```

## Submission Links

* **GitHub repository:** https://github.com/Hager-83/devops-pipeline
* **Live / staging URL:** pending staging server configuration (no URL is claimed until a real deployment has been verified)
