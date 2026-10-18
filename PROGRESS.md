# Progress Report — devops-pipeline

A phase-by-phase log of what changed, why, which files were involved, what was
tested, and what to understand from each phase.

---

## Pre-phase: Assessment (read-only)

* Full inspection written to `report.md`.
* **Key discovery:** `Dockerfile` had been accidentally overwritten with
  GitHub Actions YAML (commit `e16b4dd`); the real Dockerfile survived in the
  initial commit `ae4c3e3`. CI was green only because it never used Docker.

---

## Phase 1 — Docker and local application

### What changed
* `Dockerfile` — restored from commit `ae4c3e3` (the known-good version).
  Inspection showed it was already correct and already used Gunicorn, so no
  adaptation was needed.
* `.dockerignore` — **created**. Excludes `.git`, `.venv`, tests, docs,
  compose files, and `.env` from the build context.

### Why it was needed
* Without a valid Dockerfile, `docker build`, `docker compose up`, and every
  later phase were impossible.
* `.dockerignore` prevents secrets/junk (`.env`, `.venv`) from entering the
  image and makes builds faster.

### Files involved
`Dockerfile` (restored), `.dockerignore` (new)

### What was tested (all passed)
* `docker build -t devops-pipeline:local .` → success
* Container run → `GET /` → `{"env":"dev","message":"Hello from devops-pipeline"}`
* `GET /health` → `{"status":"ok"}` (HTTP 200)
* `GET /metrics` → Prometheus exposition format returned
* `docker top` → Gunicorn master + worker running `app:app`
* `docker inspect` → health status **healthy**

### What you should understand
* Dockerfile layer caching: copy `requirements.txt` and `pip install` **before**
  copying code, so dependency layers aren't rebuilt on every code change.
* `CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]`:
  `0.0.0.0` = reachable from outside the container; `app:app` =
  module `app.py`, Flask object `app`.
* `HEALTHCHECK` makes Docker itself track app liveness (`healthy`/`unhealthy`).

---

## Phase 2 — Compose, health checks, monitoring, logging

### What changed
No files changed — this phase was pure verification of existing files.

### What was tested (all passed)
* `docker compose up -d --build` → both services started
* `docker compose ps` → `app` reported **(healthy)**, `prometheus` up
* Prometheus API ` /api/v1/targets` → job `devops-app` health **up**, no errors
* Prometheus query `up` → `1`; query `flask_http_request_total` → live series
* App logs → structured JSON line confirmed:
  `{"time":"...","level":"INFO","msg":"index requested"}`

### What you should understand
* Compose service names are DNS names on a private network: Prometheus
  reaches the app as `app:5000`, never `localhost`.
* `docker-compose.yml` healthcheck duplicates the Dockerfile HEALTHCHECK for
  explicitness (`depends_on` + health states drive startup ordering).
* Two log streams: Gunicorn's plain-text boot messages vs. the app's JSON
  lines. JSON is what log aggregators want.

---

## Phase 3 — Automated testing and CI

### What changed
* `tests/test_app.py` — preserved the original 2 tests, **added 2**:
  * `test_home_body_contains_message_and_env` (response body content,
    robust against a pre-set `APP_ENV`)
  * `test_metrics_exposed` (`/metrics` returns Prometheus `# HELP` format)
* `.github/workflows/ci-cd.yml` — rewritten from tests-only into a real
  pipeline: `test` job + `docker` job (build image → run container → curl
  `/health`, `/metrics`, `/` → print logs → `if: always()` cleanup).

### Why it was needed
* The old workflow never touched Docker, so a broken image would still pass CI.
* The stranded build/health steps (living in the misnamed `Dockerfile`) were
  moved into the real workflow file.
* Actions kept to maintained majors: `actions/checkout@v4`,
  `actions/setup-python@v5`.

### Files involved
`tests/test_app.py`, `.github/workflows/ci-cd.yml`

### What was tested (all passed locally)
* `pytest -v` → **4 passed**
* Workflow YAML parsed with PyYAML → valid; jobs: `test`, `docker`
* CI steps simulated locally (container on port 5001 to avoid a conflict with
  the running compose stack): health 200, body grep matched, metrics returned,
  cleanup removed the container

### What you should understand
* `needs: docker` makes the docker job wait for tests — failures block
  downstream jobs automatically.
* `if: always()` on the cleanup step so containers are removed **even when
  the job fails** — leftover containers waste runner resources.
* `--retry-connrefused` lets curl wait for a booting app instead of failing
  instantly.
* Local simulation ≠ GitHub run: the workflow will only be truly verified
  after the first push (external action, needs your permission).

---

## Phase 4 — Container registry (GHCR)

### What changed
* `.github/workflows/ci-cd.yml` — added the `publish` job:
  * `needs: docker` + `if: push to main` (never runs on PRs)
  * `permissions: contents: read, packages: write` — minimum required;
    the built-in `GITHUB_TOKEN` is used, **no credentials stored anywhere**
  * `docker/login-action@v3` → login to `ghcr.io`
  * Tags: `:latest` and `:sha-<commit>` (immutable, traceable tag)

### What was tested
* Workflow YAML → valid; job chain: `test → docker → publish`.
* **Not yet verified end-to-end** — publishing only happens on a real push to
  main (requires your permission to push).

### What you should understand
* GHCR image names must be **lowercase** — hence
  `ghcr.io/hager-83/devops-pipeline` (not `Hager-83`).
* Always pull `:sha-<commit>` in production-style deploys; `:latest` is a
  moving target.
* `GITHUB_TOKEN` is automatically issued per-workflow-run and expires —
  much safer than a personal access token in a secret.

---

## Phase 5 — Staging deployment (prepared, gated)

### What changed
* `docker-compose.staging.yml` — inspected and **preserved unchanged**
  (prebuilt GHCR image, `APP_ENV=staging`, healthcheck, restart policy).
* `.github/workflows/ci-cd.yml` — added the `deploy-staging` job:
  * `needs: publish` — runs only after tests, health checks, **and** image
    publishing succeed
  * `if: vars.DEPLOY_STAGING == 'true'` — **skipped by default**, so CI stays
    green until you configure a real server
  * SSH deploy using GitHub Secrets (`STAGING_HOST`, `STAGING_USER`,
    `STAGING_SSH_KEY`), copies compose + Prometheus config to
    `~/devops-pipeline/`, pulls the image, starts the stack
  * **Health verification after deploy** — curls `$STAGING_URL/health`;
    failure fails the job
  * Optional `GHCR_PULL_TOKEN` login only if the package is private

### What is blocked (needs your input)
* No staging host exists. Options are listed in the main report/response:
  (a) VPS/cloud VM you control, (b) PaaS (Railway/Render/Fly.io), or
  (c) a local machine reachable via a tunnel — plus which one you choose and
  the access details.
* **No deployment has happened; no URL exists.** Nothing will be claimed
  until a health check passes against a real server.

### What you should understand
* Secrets vs. variables: secrets are encrypted and masked in logs
  (keys, passwords); variables are plain settings (`STAGING_URL`,
  `DEPLOY_STAGING` gate).
* The `needs` chain is your delivery safety net:
  test → docker health → publish → deploy. Nothing deploys from a broken build.
* Deploy scripts never echo secrets; the SSH key is written to a
  permissions-restricted file inside the runner's temporary filesystem.

---

## Phase 6 — Documentation and submission

### What changed
* `README.md` — rewritten so every claim matches the implementation:
  real repository URL, honest "not yet deployed" staging status, full docs
  for testing/Docker/Compose/CI/GHCR/monitoring/logging, GHCR pull
  instructions, staging activation checklist.
* `PROGRESS.md` — this file.

### What was tested
* Cross-checked README claims against the actual files and local test
  results (endpoints, job names, image names, ports).

### What you should understand
* Documentation is part of the deliverable: a reviewer will follow your
  README as the first impression. Placeholder URLs and unimplemented claims
  cost more trust than honest gaps.

---

## CI incident (post-push): docker job failed on GitHub

### What happened
First real CI run (`39103434197`) failed at **Verify health endpoint**:
`curl: (56) Connection reset by peer`.

### Root cause
* Race condition: curl fired ~390ms after `docker run`, while Gunicorn was
  still booting (it logged "Listening" 80ms *after* curl already failed).
* Docker's port proxy accepts the TCP connection even when the container
  process isn't listening yet → curl saw **exit 56 (reset)**, not exit 7
  (refused).
* `--retry-connrefused` only retries exit 7, so there was no retry at all.
* The image, build, and container were all healthy — only the check was wrong.

### Fix (`.github/workflows/ci-cd.yml`)
* Replaced `--retry-connrefused` curl flags with an explicit wait loop:
  15 attempts × 2s (up to 30s), retrying **any** failure until `/health`
  answers, then fail with a clear message.

### Verified
* Workflow YAML valid.
* Failure reproduced locally: attempt 1 → exit 56 (same as CI), attempt 2 →
  `{"status":"ok"}` — the loop recovers exactly as intended.

### What you should understand
* Never trust "connection refused" as the only startup failure mode behind
  Docker port mappings — resets happen too.
* Retrying specific error codes is brittle; a simple loop that retries until
  a deadline is easier to reason about and covers everything.
* CI failures are data: the log timeline (`docker run` → curl → gunicorn's
  "Listening" line) made the race obvious.

---

## Phase 5 decision: hosting research → Render (free, no card)

> **Superseded:** Render's signup demanded a credit card for identity
> verification — abandoned under the no-card constraint. See "Phase 5 final"
> below for the Railway deployment that actually shipped.

### What changed
* Research pass comparing all currently free container hosts (Oct 2026):
  excluded Koyeb ($29 card hold since Feb 2026), Fly.io (no free tier since
  Oct 2024), Oracle/AWS/GCP/Azure (card required), Heroku (free tier gone).
  Selected **Render**: card-free signup (GitHub OAuth), 750 free
  instance-hours/month, and — because no card exists on the account —
  over-limit usage *suspends* the service instead of ever charging it.
* `render.yaml` — **created**: Render Blueprint defining a free web service
  that builds the existing `Dockerfile`, health-checks `/health`, sets
  `APP_ENV=staging`, and auto-deploys only after repo CI checks pass
  (`autoDeployTrigger: checksPass`).
* `README.md` — staging section rewritten: Render setup steps, free-tier
  facts (15-min sleep / ~60 s cold start / suspension-not-billing), the
  honest Prometheus-on-staging limitation, SSH job documented as the
  alternative VPS path; submission-links section updated.

### What you should understand
* **Charge-proof by construction:** billing requires a payment method.
  No card → the worst possible outcome is suspension, never a bill.
* **Why Prometheus stays local:** a second free container would sleep too,
  so remote scraping would flap. The compose stack proves monitoring locally;
  staging still exposes `/metrics` directly.
* **Sleep/cold-start trade-off:** free tiers fund themselves with idle time —
  a ~60 s first response after idle is normal, not an outage.

### Still pending (requires your account — nothing faked)
1. You: Render signup → New → Blueprint → connect repo → Apply (~3 min).
2. You: paste the real `onrender.com` URL into the README submission links.
3. Verify: `curl <url>/health`, `curl <url>/` (contains `"staging"`),
   `curl <url>/metrics`.

---

## Phase 5 final: Render blocked by card wall → Railway (LIVE, verified)

### What happened
* Render signup demanded a **credit card "to verify identity"** → cancelled,
  no card added. Re-ran the free-hosting screen (Oct 2026):
  * Hugging Face Docker Spaces — **paid since July 2026** (research caught
    this before we committed to it)
  * Northflank — card required to create any resource
  * Back4App free container — stops after 60 minutes per deploy (dead demo)
  * Koyeb ($29 card hold), Fly.io, Heroku, Oracle/AWS/GCP/Azure — card or no
    free tier
  * Zeabur — free-plan docs conflict on container support (uncertain)
* Selected **Railway**: card-free signup, one-time **$5 / 30-day trial
  credit** (enough for this app's ~$2–3/month footprint), deploys the same
  `Dockerfile` straight from GitHub.

### What changed
* `README.md` — staging section rewritten for Railway (trial terms,
  pause-not-charge behavior after the trial, verified URL, monitoring
  limitation kept, Render/SSH paths documented as unused alternatives);
  header + architecture diagram + submission links updated with the real
  URL.
* `PROGRESS.md` — this entry; Render entry marked superseded.
* Service config (Railway dashboard): `APP_ENV=staging` (verified live).

### Verified (2026-10-18, all HTTP 200)
* `https://devops-pipeline-production.up.railway.app/health` → `{"status":"ok"}`
* `https://devops-pipeline-production.up.railway.app/` → `"env":"staging"`
  (after setting `APP_ENV=staging`; first check showed `"env":"dev"` —
  proof the fallback worked and the variable really landed)
* `https://devops-pipeline-production.up.railway.app/metrics` → Prometheus
  exposition format

### What you should understand
* **Charge-proof still holds:** no payment method → when the $5 trial credit
  ends the service **pauses**; Railway cannot bill an account with no card.
* **First `/` check said `dev`** — good catch pattern: never assume an env
  var landed; verify it through the app's own response.
* **Monitoring limitation unchanged:** the Prometheus stack stays local
  (second container wouldn't fit any $0 budget); `/metrics` is exposed on
  staging so a local Prometheus *can* scrape it if needed.
* **Render research lesson:** free-tier terms move fast (HF Docker Spaces
  went paid mid-2026; Render added a card wall) — re-verify before trusting
  any list, including this one.

---

## Current status summary

| Item | Status |
| ---- | ------ |
| Dockerfile + Gunicorn | ✅ Restored, built, verified locally |
| `.dockerignore` | ✅ Created |
| Compose stack (app + Prometheus) | ✅ Verified end-to-end locally |
| Health checks | ✅ Verified (container `healthy`, endpoint 200) |
| Prometheus scraping | ✅ Verified (`up=1`, live metric series) |
| JSON logging | ✅ Verified |
| Pytest suite | ✅ 4 tests passing locally |
| CI workflow (test → docker → publish) | ✅ Green on GitHub (run `39103889795`); includes the health-check race fix |
| GHCR publishing | ✅ Published & verified (`ghcr.io/hager-83/devops-pipeline:latest` pulls anonymously) |
| Staging deployment | ✅ **LIVE on Railway** (`APP_ENV=staging`), $0, no card — Render abandoned (card wall) |
| README | ✅ Matches implementation, real URL documented |
| Live URL | ✅ https://devops-pipeline-production.up.railway.app — verified 2026-10-18 (`/health` 200, `/` = staging, `/metrics` OK) |
