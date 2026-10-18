# DevOps Pipeline

A containerized Flask web application with Docker, Docker Compose, automated testing, a GitHub Actions CI/CD pipeline, GitHub Container Registry publishing, Prometheus monitoring, and a prepared (but not yet enabled) staging deployment.

> **Repository:** https://github.com/Hager-83/devops-pipeline
> **Live / staging URL:** not deployed yet — provisioned free of charge on Render
> (no credit card) via `render.yaml`; see [Staging Deployment](#staging-deployment).

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
                   └────────── gated alternative: SSH deploy ──→  staging VM
  Render (staging): blueprint auto-deploys main after CI checks pass
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
├── render.yaml                     # Render Blueprint (free staging hosting)
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
| `deploy-staging`  | **Alternative (VPS) path:** SSHs to a server, pulls the image, starts the `docker-compose.staging.yml` stack, then curls `/health` | **Gated off** until `DEPLOY_STAGING` variable is set — the primary staging path is Render (below) |

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

**Status: fully configured, waiting for the one-time Render account setup
(nothing deployed until that happens — no URL is claimed here).**

### Primary path: Render (free, $0, no credit card)

Chosen because it is one of the few container platforms that still runs
Docker **without asking for a payment method**. With no card on the account,
Render *cannot* bill you — exceeding free limits suspends services instead
of charging them.

Free-plan facts (verified October 2026):

| Aspect | Behavior |
| ------ | -------- |
| Cost | $0 — signup via GitHub, **no payment page** |
| Limits | 750 instance-hours/month (enough for one always-on app), 512 MB RAM, 5 GB bandwidth |
| Sleep | Spins down after **15 min without traffic**; first request takes ~30–60 s to wake it |
| Resets | Hours/bandwidth reset each calendar month; exhaustion = suspension, never a charge |
| Endpoint | Your URL: `https://<service-name>.onrender.com` (shown in the Render dashboard after creation) |

How it works with this repo: `render.yaml` (Render Blueprint) defines the
service — it builds the repo's own `Dockerfile`, listens on the port from
`EXPOSE 5000`, health-checks `/health`, sets `APP_ENV=staging`, and only
auto-deploys after the repository's **CI checks pass** on `main`.

One-time setup (dashboard, ~3 minutes):

1. Go to https://dashboard.render.com → sign up with GitHub (**skip/decline
   any payment step**)
2. **New → Blueprint** → connect `Hager-83/devops-pipeline` → Render reads
   `render.yaml`
3. Click **Apply** → wait for the first build
4. Open the service → copy the URL from **Settings → Ports/URL**

Verification after setup:

```bash
curl <your-staging-url>/health   # {"status":"ok"}  (allow ~60 s cold start)
curl <your-staging-url>/         # should contain "staging"
curl <your-staging-url>/metrics  # Prometheus exposition format
```

### Monitoring on staging — documented limitation

The Prometheus **container stack runs and is verified locally only**
(`docker compose up` → target `app` is UP at localhost:9090). Render's free
tier cannot host a second always-on Prometheus container (it would sleep
too, breaking scraping), so the staging URL exposes the app's `/metrics`
data directly instead of a Prometheus dashboard. The CI workflow, health
checks, and metrics endpoint all remain identical between local and staging.

### Alternative path: SSH deployment to a self-managed server

The `deploy-staging` job in `.github/workflows/ci-cd.yml` is a complete
SSH-based CD job (needs: `publish`, deploys `docker-compose.staging.yml`,
verifies `/health` afterwards). It stays **gated off** because no VPS
exists. To enable it later: provision any server with Docker, then set the
repository secrets/variables listed in that workflow's header comment
(`STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`, `STAGING_URL`,
`DEPLOY_STAGING=true`).

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
* **Live / staging URL:** `https://<service-name>.onrender.com` — paste the
  real URL here immediately after the Render setup above; until then this
  project intentionally claims no live URL
