# Assessment Report: `devops-pipeline`

> Date of inspection: 2026-10-18
> Scope: read-only inspection of `/home/hager/DevOps-Projects/AppRO8/devops-pipeline`
> GitHub repo: https://github.com/Hager-83/devops-pipeline (public)

---

## Executive Summary

**~60% complete.** The Flask app, automated tests, environment configuration, GitHub repository, and README skeleton are solid and verified. However, there is one **critical break**: the `Dockerfile` was accidentally overwritten with GitHub Actions YAML content, which blocks Docker builds, docker-compose, and monitoring verification. CI currently runs tests only (no Docker build, no image push, no deployment), and no staging environment or deployment URL exists yet.

---

## Step 1 & 2: Project Inspection — What Exists and What It Does

### Project structure

```
devops-pipeline/
├── app/
│   ├── app.py                      # Flask application
│   └── requirements.txt            # Python dependencies
├── tests/
│   └── test_app.py                 # Pytest tests
├── monitoring/
│   └── prometheus.yml              # Prometheus scrape configuration
├── .github/
│   └── workflows/
│       └── ci-cd.yml               # GitHub Actions CI workflow
├── .env.example                    # Environment variable template
├── .gitignore
├── Dockerfile                      # ⚠️ BROKEN — contains CI YAML, not build instructions
├── docker-compose.yml              # Local/dev multi-container stack
├── docker-compose.staging.yml      # Staging stack (⚠️ untracked in git)
├── image.png                       # Architecture diagram
├── pytest.ini                      # Pytest configuration
└── README.md                       # Documentation
```

### File-by-file assessment

| File | What it is / does | Status |
|---|---|---|
| `app/app.py` | Flask app with 3 endpoints: `/` (JSON greeting + env name), `/health` (returns `{"status":"ok"}`), `/metrics` (auto-added by `prometheus_flask_exporter`). JSON-structured logging driven by `LOG_LEVEL`. | ✅ Complete and working — tests pass |
| `app/requirements.txt` | Flask 3.0.3, Gunicorn 22.0.0, prometheus-flask-exporter 0.23.1, pytest 8.3.2 | ⚠️ Gunicorn is listed but **never used** — nothing runs it |
| `tests/test_app.py` + `pytest.ini` | 2 pytest tests hitting `/` and `/health` via Flask test client | ✅ **Verified**: `2 passed` (ran locally during inspection) |
| `docker-compose.yml` | Two services: `app` (builds from `.`) + `prometheus` (scrapes `app:5000/metrics`), healthcheck on `/health` via Python urllib | ⚠️ Written correctly but **cannot run** — `build: .` requires a valid Dockerfile |
| `docker-compose.staging.yml` | Same stack using `image: ghcr.io/hager-83/devops-pipeline:latest`, `APP_ENV=staging`, `restart: unless-stopped` | ⚠️ **Untracked in git** (local only), and the GHCR image it references **does not exist** (verified: pull denied) |
| `Dockerfile` | **Not a Dockerfile.** Contains GitHub Actions YAML (`name: CI…` with docker build/run/health-check steps) | ❌ **Broken** — details in Git history section below |
| `.github/workflows/ci-cd.yml` | Real CI workflow: checkout → Python 3.12 → pip install → `pytest`. Triggers on push/PR to `main`. | ✅ **Verified green on GitHub** (3 successful runs), but tests-only — no Docker build/push/deploy |
| `monitoring/prometheus.yml` | Scrapes `app:5000/metrics` every 15s | ✅ Correct config, but **not verified end-to-end** (needs working Dockerfile to run) |
| `.env.example` | Template with `APP_ENV` and `LOG_LEVEL` (names only, no secrets) | ✅ Complete |
| `README.md` | 351-line documentation (architecture, setup, testing, troubleshooting) | ⚠️ Overstates reality — claims deploy-to-staging steps that don't exist in the workflow; submission URLs are still `YOUR-USERNAME` placeholders |
| `image.png` | Architecture diagram referenced by the README | ✅ Present |

### Git history — how the Dockerfile got broken

```
ae4c3e3 Initial DevOps pipeline project  → Dockerfile was REAL (FROM python:3.12-slim…)
5ab1066 Fix GitHub Actions workflow directory  → renamed .github/workflos → workflows
e16b4dd "Add Docker build to CI"  → ⚠️ OVERWROTE Dockerfile with workflow YAML
5affad1 "Add Docker runtime health check to CI"  → added more steps to the wrong file
```

**What happened:** when Docker build steps were added to CI, the new workflow content was pasted into `Dockerfile` instead of `.github/workflows/ci-cd.yml`.

**Evidence:**
- The original real Dockerfile (16 lines, starting `FROM python:3.12-slim`) is still recoverable: `git show ae4c3e3:Dockerfile`
- `.github/workflows/ci-cd.yml` still has only the 3 test steps — it never received the Docker build/deploy steps
- GitHub CI shows green only because the pipeline never uses Docker; the broken `Dockerfile` is never referenced in the real workflow

**Consequence:** `docker build`, `docker compose up`, and therefore Prometheus monitoring — all fail right now.

---

## Step 3: Requirements Classification

| # | Requirement | Evidence | Classification |
|---|---|---|---|
| 1 | Dockerfile for the web application | File exists but contains CI YAML, not build instructions. A real one existed at commit `ae4c3e3` and can be restored | **❌ Broken** (was complete once, then overwritten) |
| 2 | docker-compose.yml for multi-container setup | Valid `docker-compose.yml` with `app` + `prometheus` services | **⚠️ Implemented but not verified** (blocked by #1) |
| 3 | GitHub Actions / GitLab CI pipeline | `.github/workflows/ci-cd.yml`; 3 green runs on GitHub | **⚠️ Partially implemented** — tests only; no build/push/deploy stages |
| 4 | Automated testing in the pipeline | Workflow runs `pytest`; verified locally: **2 passed** | **✅ Complete and verified** |
| 5 | Automatic deployment to staging | `docker-compose.staging.yml` exists locally (untracked); GHCR image returns **denied/401** — never pushed. No deploy step in workflow; no staging server configured | **❌ Missing** (compose file = partial preparation only) |
| 6 | Environment variable management | `.env.example`, compose `${APP_ENV:-dev}` interpolation, app reads `APP_ENV`/`LOG_LEVEL` | **✅ Complete for this scope** |
| 7 | Container health checks | `/health` endpoint + healthcheck blocks in both compose files + curl check drafted (but stranded in the misnamed Dockerfile) | **⚠️ Implemented but not verified** |
| 8 | Monitoring and logging | Prometheus config + exporter in app; JSON logging in `app.py` | **⚠️ Implemented but not verified** — no end-to-end proof that the Prometheus target is UP |
| 9 | GitHub repository named `devops-pipeline` | https://github.com/Hager-83/devops-pipeline — public, exists | **✅ Complete and verified** |
| 10 | Deployment URL and complete README | README has `YOUR-USERNAME` / `YOUR-STAGING-URL` placeholders; no deployment exists | **❌ Missing** |

**Could not be verified from available files:** whether any staging host/server exists at all (no cloud config, SSH, or VPS references found in the project).

---

## Step 4: Architecture Explained (Beginner-Friendly)

### Current workflow (as designed)

```
Your code (app/app.py)
      │
      ▼
Dockerfile  ──build──►  Docker image  ──run──►  Container (port 5000)
      ✗ BROKEN               (missing on GHCR)       │
                                                      ├── /  /health  /metrics
                                                      │
docker-compose.yml ──starts──► 2 containers: app + prometheus
                                                      │
                              prometheus (port 9090) ─┘ scrapes /metrics every 15s

GitHub Actions (ci-cd.yml) on every push/PR:
   checkout → Python 3.12 → pip install → pytest          ✅ works today
   …intended but missing: docker build → run → health check
                          → push image to GHCR → deploy staging
```

### Concept glossary

- **Dockerfile** — a recipe that packages your app + Python + dependencies into one portable image. Ours was accidentally replaced by CI YAML.
- **Docker image / container** — the image is the packaged artifact; a container is a running instance of it.
- **docker-compose** — a file that starts several containers together (app + Prometheus) on a shared private network, so Prometheus reaches the app using the service name `app`.
- **CI (GitHub Actions)** — automatic checks that run on every push/PR. Ours currently only runs tests.
- **CD / staging deployment** — automatically publishing a fresh image to a registry (GHCR = GitHub Container Registry) and starting it on a staging server. `docker-compose.staging.yml` was written for this, but nothing ever pushes the image and nothing runs that compose file on any server.
- **Health check** — "is the app alive?" An endpoint (`/health`) that Docker and CI can poll; ours returns `{"status":"ok"}`.
- **Prometheus** — a monitoring server that periodically asks your app for metrics via the `/metrics` endpoint (request counts, latencies, etc.).
- **JSON logging** — logs emitted as one JSON object per line, easy for log-collection tools to parse.

---

## Step 5: Recommended Roadmap

Ordered, small steps. Nothing has been executed yet.

### Step 1 — Restore the real Dockerfile *(fixes the critical break)*
- **What:** Restore the working Dockerfile from `git show ae4c3e3:Dockerfile` (python:3.12-slim base), and use Gunicorn as the container command (it's already in `requirements.txt` but unused).
- **Why:** Without a valid Dockerfile, nothing else in the pipeline can be tested.
- **Files:** `Dockerfile` (replace broken content).
- **Learn:** Dockerfile anatomy (`FROM`, `COPY`, `RUN`, `CMD`, `EXPOSE`); why Gunicorn instead of the Flask dev server.
- **Verify:** `docker build -t devops-pipeline .` succeeds; `docker run -p 5000:5000 …` then `curl localhost:5000/health` returns `{"status":"ok"}`.

### Step 2 — Verify the compose stack end-to-end
- **What:** Run `docker compose up -d --build`; confirm both containers are healthy; check Prometheus at `localhost:9090` shows the `app:5000` target as **UP**; confirm `localhost:5000/metrics` returns metrics.
- **Why:** Monitoring and health checks are listed requirements but have never been proven working.
- **Files:** `docker-compose.yml`, `monitoring/prometheus.yml` (no changes expected).
- **Learn:** Compose networking (service-name DNS), healthcheck states.
- **Verify:** Prometheus target page shows UP; metrics visible in the browser.

### Step 3 — Fix the CI workflow
- **What:** Move the stranded Docker steps into `.github/workflows/ci-cd.yml`: docker build → run container → curl `/health` → cleanup. Then remove the bogus YAML from `Dockerfile` (already replaced in Step 1).
- **Why:** CI must prove the image actually builds and boots, not just that unit tests pass.
- **Files:** `.github/workflows/ci-cd.yml`.
- **Learn:** GitHub Actions job/step structure; `if: always()` cleanup; failing CI when the health check fails.
- **Verify:** Push → green GitHub Actions run that includes the Docker build and health-check steps in its log.

### Step 4 — Publish images to GHCR from CI
- **What:** Add image build-with-tag + `docker/login-action` (using the built-in `GITHUB_TOKEN`; no secret to create) + push steps to the workflow.
- **Why:** `docker-compose.staging.yml` references `ghcr.io/hager-83/devops-pipeline:latest`, but that image has never existed.
- **Files:** `.github/workflows/ci-cd.yml`.
- **Learn:** Container registries, image tagging, GitHub Actions `GITHUB_TOKEN`.
- **Verify:** Image visible at `ghcr.io/hager-83/devops-pipeline`; `docker pull` works locally.

### Step 5 — Real staging deployment
- **What:** Choose a staging host (simplest: a VPS running `docker compose -f docker-compose.staging.yml up -d`), commit the currently-untracked `docker-compose.staging.yml`, and add a deploy job to CI (SSH-based). Alternative: a PaaS.
- **Why:** "Automatic deployment to staging" is a core task requirement and is currently entirely missing.
- **Files:** `docker-compose.staging.yml` (commit it), `.github/workflows/ci-cd.yml` (deploy job).
- **Learn:** CD patterns, why `restart: unless-stopped` matters, SSH keys as GitHub secrets.
- **Verify:** Push → CI deploys → staging URL responds on `/health` with `"env": "staging"`.

### Step 6 — Documentation and hygiene
- **What:** Update `README.md`: replace `YOUR-USERNAME` and placeholder URLs with real ones, document the actual pipeline stages accurately, add `docker-compose.staging.yml` to the structure listing. Add a `.dockerignore` (keep `.venv` out of the build context). Wire Gunicorn into the container if not done in Step 1.
- **Why:** The README currently claims capabilities the project doesn't have; submission links are placeholders.
- **Files:** `README.md`, `.dockerignore` (new), possibly `Dockerfile`.
- **Learn:** Writing documentation that matches reality; build-context hygiene.
- **Verify:** Fresh-clone walkthrough: follow the README instructions verbatim and confirm every command works.

---

## Summary Table

| Area | Status |
|---|---|
| Flask app + endpoints | ✅ Complete & verified |
| Automated tests | ✅ Complete & verified (2 passing) |
| Environment variable management | ✅ Complete |
| GitHub repository | ✅ Exists, public |
| Dockerfile | ❌ Broken (recoverable from commit `ae4c3e3`) |
| docker-compose (local) | ⚠️ Written, blocked by Dockerfile |
| docker-compose (staging) | ⚠️ Untracked; references nonexistent image |
| CI pipeline | ⚠️ Tests only; Docker steps stranded in wrong file |
| GHCR image publishing | ❌ Missing |
| Staging deployment | ❌ Missing |
| Monitoring (Prometheus) | ⚠️ Config written, not verified end-to-end |
| README | ⚠️ Comprehensive but contains placeholder URLs and unimplemented claims |
| Deployment URL | ❌ Does not exist |
