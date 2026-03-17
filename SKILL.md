---
name: github-cicd-bootstrap
description: Use when a user wants to add or standardize GitHub CI/CD for a repository, especially for Go, Node, Python, Java, Rust, Dockerized apps, or monorepos with one or more sub-services. This skill detects the project type, can generate high-performance Dockerfiles when needed, supports ci-only, docker-ssh, and docker-registry-only strategies, generates GitHub Actions workflows, creates a setup checklist, and validates the resulting CI/CD files.
---

# GitHub CI/CD Bootstrap

This skill builds a reusable GitHub Actions pipeline for a repository with as little manual setup as possible.

Use it when the user asks to:
- add GitHub Actions to a repo
- build a CI/CD pipeline for a service or app
- standardize test, build, and deploy workflows
- generate a Dockerfile or improve a Dockerfile before adding CI/CD
- generate workflow files and the required GitHub secrets checklist

## Quick Start

### Fast path

Use the bootstrap script when the user wants the skill to do the full setup in one pass.

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --app-name my-service \
  --service-path services/api
```

Language-specific fast examples:

```bash
python3 scripts/bootstrap_repo.py --project-root . --generate-dockerfile --deploy-strategy docker-registry-only --force
python3 scripts/bootstrap_repo.py --project-root . --service-path services/python-api --generate-dockerfile --force
python3 scripts/bootstrap_repo.py --project-root . --service-path services/java-api --generate-dockerfile --force
python3 scripts/bootstrap_repo.py --project-root . --service-path services/rust-worker --generate-dockerfile --force
```

If the skill is installed into the default Codex skills directory:
```bash
python3 ~/.codex/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
  --project-root . \
  --service-path services/api
```

This command:
- detects the project type
- chooses the deploy strategy
- can generate a high-performance Dockerfile first when requested
- reads `.github/cicd-bootstrap.json` automatically when present
- writes workflow files to `.github/workflows`
- writes `scripts/remote_deploy.sh` automatically for `docker-ssh`
- generates a setup checklist at `.github/cicd-bootstrap-checklist.md`
- validates the generated workflows

### Step-by-step path

1. Detect the project type:
   ```bash
   python3 scripts/detect_project.py --project-root . --service-path services/api
   ```
2. Render workflows:
   ```bash
   python3 scripts/render_workflow.py --project-root . --service-path services/api --output-dir .github/workflows
   ```
3. Generate the setup checklist:
   ```bash
   python3 scripts/generate_checklist.py \
     --project-root . \
     --service-path services/api \
     --output-file .github/cicd-bootstrap-checklist.md
   ```
4. Validate the generated files:
   ```bash
   python3 scripts/validate_workflow.py --workflow-dir .github/workflows
   ```

### Dockerfile-first path

If the repository does not yet have a `Dockerfile`, generate one first:

```bash
python3 scripts/generate_dockerfile.py \
  --project-root . \
  --service-path services/api
```

Or let bootstrap do it in one shot:

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --service-path services/api \
  --generate-dockerfile \
  --deploy-strategy docker-registry-only \
  --force
```

### Optional repo config

If the repo has repeated CI/CD conventions, create:

```text
.github/cicd-bootstrap.json
```

Example:
```json
{
  "app_name": "my-service",
  "deploy_strategy": "docker-registry-only",
  "service_paths": ["services/api", "services/worker"],
  "default_branch": "main",
  "test_branches": ["develop", "release/*"],
  "image_registry": "ghcr.io/acme-platform",
  "healthcheck_url_test": "http://127.0.0.1:8080/healthz",
  "healthcheck_url_prod": "http://127.0.0.1:8080/healthz",
  "healthcheck_timeout_seconds": 40,
  "rollback_on_failure": true,
  "remote_image_retention": 3,
  "runner": "ubuntu-latest",
  "default_shell": "bash --noprofile --norc -euo pipefail {0}",
  "default_job_timeout_minutes": 20,
  "deploy_job_timeout_minutes": 30,
  "enable_security_scan": true,
  "security_scan_blocking": false,
  "action_pin_mode": "tag",
  "allow_actions": ["actions/checkout", "docker/build-push-action"],
  "enable_cache": true
}
```

`app_name` and generated multi-service `slug` values are normalized to lowercase kebab-case before they are used in workflow names, Docker image names, and related artifact names. For example, `sourceBinance` becomes `source-binance`.
For `docker-registry-only`, the workflow also lowercases the final registry prefix at runtime, so defaults like `ghcr.io/${{ github.repository_owner }}` and optional `IMAGE_REGISTRY` overrides remain valid for GHCR and similar registries.
When a monorepo service does not specify `app_name`, the generator prefixes the service slug with the repository name by default so image names stay unique under owner-scoped registries.
Bootstrap output keeps security scans enabled but defaults them to non-blocking mode so transient Trivy setup failures do not fail every first-run pipeline. Setting `security_scan_blocking` to `true` switches pushes to the default branch and `release` branches into blocking mode while keeping pull requests and `develop`-style test branches non-blocking.
`action_pin_mode` defaults to `tag`; when set to `sha`, the repo config must provide `pinned_actions` for the actions actually used by the rendered workflow.
Generated jobs now default to `bash --noprofile --norc -euo pipefail {0}`, keep required permissions/concurrency/timeout fields, and can be constrained by an `allow_actions` whitelist.
For `docker-ssh`, the generated workflows create the remote directory automatically, upload a generated `scripts/remote_deploy.sh`, run an optional healthcheck, roll back to the previous image by default when the new container fails healthchecks, and prune older images using `remote_image_retention`.
When a service depends on Redis, MySQL, MQ, or internal HTTP dependencies, prefer declaring `dependency_checks_test` and `dependency_checks_prod` in repo config. Supported formats are `tcp://host:port`, `http(s)://...`, and `cmd:<shell command>`. These checks default to reminder mode unless `dependency_checks_blocking` is set to `true`.

When this file exists, `bootstrap_repo.py` will load it automatically. CLI flags still override the config file.

## What This Skill Generates

- `ci.yml`
  - repository-level CI for test and build validation
- `deploy-test.yml`
  - test environment deployment workflow
- `deploy-prod.yml`
  - production deployment workflow

The generator supports three deploy strategies:

1. `docker-ssh`
   - use when the repo is already Dockerized
   - builds an image in GitHub Actions and switches the container on a remote host over SSH

2. `docker-registry-only`
   - use when the repo is already Dockerized but another platform handles deployment
   - builds and pushes images only

3. `ci-only`
   - use when the repo does not yet have a Docker-based deploy target
   - generates CI plus placeholder deploy workflows that guide the team to choose a release strategy later

It also supports high-performance Dockerfile generation for:

- `go-service`
- `node-service`
- `python-service`
- `java-service`
- `rust-service`
- `static-web`

## Workflow

### 1. Detect the repository shape

Run `scripts/detect_project.py` first. It decides:
- project type: `go-service`, `node-service`, `python-service`, `java-service`, `rust-service`, or `docker-service`
- package manager when relevant
- whether the repo already has a `Dockerfile`
- candidate service directories when the repo root itself is not directly identifiable

If detection is wrong, rerun the render step with explicit flags instead of editing the detector.
For monorepos, prefer `--service-path`.
For batch generation, use `--service-paths services/api,services/web`.

If the repo is missing a `Dockerfile` but the user wants deployment automation, generate the Dockerfile before rendering workflows.

### 2. Choose the deploy strategy

Use this decision order:

- If the repo has a `Dockerfile`, prefer `docker-ssh`
- If the repo already deploys from a container registry, prefer `docker-registry-only`
- Else use `ci-only`
- If the user wants deployment but the repo is not yet Dockerized, generate CI first and explain that deployment still needs a runtime target

### 3. Render the workflows

Use `scripts/render_workflow.py`. It fills templates and writes workflow files.

Recommended command for a Dockerized service:
```bash
python3 scripts/render_workflow.py \
  --project-root . \
  --service-path services/api \
  --output-dir .github/workflows \
  --deploy-strategy docker-ssh \
  --app-name my-service
```

Recommended command for a non-Docker repo that still needs CI scaffolding:
```bash
python3 scripts/render_workflow.py \
  --project-root . \
  --service-path services/api \
  --output-dir .github/workflows \
  --deploy-strategy ci-only \
  --app-name my-service
```

Recommended command for a multi-service monorepo:
```bash
python3 scripts/render_workflow.py \
  --project-root . \
  --service-paths services/api,services/web \
  --deploy-strategy docker-registry-only \
  --output-dir .github/workflows
```

### 4. Validate before presenting the result

Always run:
```bash
python3 scripts/validate_repo_config.py --project-root .
python3 scripts/validate_workflow.py --workflow-dir .github/workflows
```

Validation checks:
- all generated workflow files exist
- unresolved placeholders are not left behind
- each workflow has `name`, `on`, `jobs`, `permissions`, and `concurrency`
- every job declares `runs-on` and `timeout-minutes`
- language CI templates keep at least one test step and one build step
- deploy workflows include `environment`
- checklist references stay aligned with secrets / variables used by workflows
- `actionlint` runs automatically when available

### 5. Tell the user what still needs manual input

Always summarize:
- which deploy strategy was chosen
- whether a Dockerfile was generated
- which secrets are required
- which repository variables are required
- whether branch names need adjusting
- whether runner / image registry / security scan defaults came from repo config
- whether policy defaults such as shell, timeout, action pin mode, or allowlist came from repo config

Use [references/secrets-checklist.md](references/secrets-checklist.md) when summarizing setup requirements.
Use [references/deploy-patterns.md](references/deploy-patterns.md) when deciding between `docker-ssh`, `docker-registry-only`, and `ci-only`.
Use [references/repo-config.md](references/repo-config.md) when a team wants to standardize defaults across many repositories.
If the user wants direct output in one shot, prefer `scripts/bootstrap_repo.py`.

## Teammate Onboarding

When the user asks how a new teammate should use this skill, what the handoff flow should look like, or asks for a short SOP, answer with a direct operational flow instead of abstract feature descriptions.

Cover these points in order:

1. Preconditions
   - teammate has local repo checkout
   - teammate already installed `github-cicd-bootstrap`
   - teammate is in the repo root

2. First command to run
   - for a single-service repo, show:
   ```bash
   python3 ~/.agents/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
     --project-root . \
     --deploy-mode docker-registry-only \
     --generate-dockerfile \
     --force
   ```
   - if they already know the language/service path, it is good to show concrete variants:
   ```bash
   python3 ~/.agents/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
     --project-root . \
     --service-path services/python-api \
     --generate-dockerfile \
     --force
   python3 ~/.agents/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
     --project-root . \
     --service-path services/java-api \
     --generate-dockerfile \
     --force
   python3 ~/.agents/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
     --project-root . \
     --service-path services/rust-worker \
     --generate-dockerfile \
     --force
   ```
   - for a monorepo, show:
   ```bash
   python3 ~/.agents/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
     --project-root . \
     --service-paths web_api,sourceBinance \
     --deploy-mode docker-registry-only \
     --force
   ```
   - mention that some environments use `~/.codex/skills/...` instead of `~/.agents/skills/...`

3. What files get generated
   - `.github/workflows/*.yml`
   - `.github/cicd-bootstrap-checklist.md`
   - optional `Dockerfile` / `.dockerignore`

4. GitHub setup
   - send the teammate to `Settings -> Secrets and variables -> Actions`
   - for `docker-registry-only`, call out:
     - `REGISTRY_USERNAME`
     - `REGISTRY_PASSWORD`
   - mention optional `IMAGE_REGISTRY`

5. Commit and trigger flow
   - show:
   ```bash
   git add .
   git commit -m "chore: bootstrap ci/cd"
   git push
   ```
   - explain that they should then inspect `CI`, `Deploy Test`, and `Deploy Prod` in GitHub Actions

6. Team defaults
   - strongly recommend adding `.github/cicd-bootstrap.json`
   - call out these keys:
     - `deploy_mode` / `deploy_strategy`
     - `service_path` / `service_paths`
     - `test_branch` / `test_branches`
     - `image_registry`
     - `healthcheck_url_test` / `healthcheck_url_prod`
     - `healthcheck_timeout_seconds`
     - `rollback_on_failure`
     - `enable_security_scan`
     - `security_scan_blocking`

7. Common pitfalls
   - root detection returns `unknown` -> add `--service-path` or `--service-paths`
   - image push fails -> verify registry credentials first
   - Trivy scan occasionally fails -> bootstrap defaults to non-blocking; tighten later if needed
   - Python repo has no lock file -> `pip` cache may miss more often; this is expected
   - Gradle wrapper is checked in without execute bit -> workflow now runs `chmod +x ./gradlew`, but the wrapper itself still needs to exist
   - Rust first compile is slower than later runs because `cargo` dependencies and target cache need warming

8. Natural-language prompts teammates can give AI
   - `用 github-cicd-bootstrap 给这个仓库补一套 GitHub CI/CD，走 docker-registry-only，并在需要时自动生成 Dockerfile。`
   - `这是个 monorepo，请给 web_api 和 sourceBinance 生成 workflow，并告诉我还缺哪些 GitHub Secrets。`
   - `先帮我检测这个仓库该用哪种 deploy strategy，再生成 workflow 和 checklist。`

If the user asks for a very short version, give them this one-liner:

```text
进仓库根目录，先跑 bootstrap_repo.py；再按 .github/cicd-bootstrap-checklist.md 去补 GitHub Secrets / Variables；最后 git push 看 Actions。
```

## Guardrails

- Do not overwrite an existing workflow unless the user clearly wants replacement.
- Prefer generating to `.github/workflows` and then showing a concise diff summary.
- If the repository already has bespoke CI/CD, preserve the established pattern rather than forcing the templates here.
- Prefer `docker-ssh` only if the repo is already Dockerized or the user explicitly wants Docker-based delivery.
- Prefer `docker-registry-only` when the repo is Dockerized but release orchestration belongs to another platform team.
- Prefer `ci-only` when the release target is still undecided.

## Resources

### scripts/

- `detect_project.py`
  - identifies project type and deploy affordances
- `render_workflow.py`
  - renders workflow files from templates for one or many services
- `generate_checklist.py`
  - generates the secrets and variables setup checklist
- `generate_dockerfile.py`
  - generates high-performance Dockerfiles and `.dockerignore` files
- `bootstrap_repo.py`
  - can perform dockerfile generation -> detect -> render -> checklist -> validate in one run
- `validate_repo_config.py`
  - validates `.github/cicd-bootstrap.json` against the bundled compatibility rules and schema defaults
- `validate_workflow.py`
  - runs lightweight validation on generated workflows
- `smoke_test_templates.py`
  - creates temporary sample repos for Go, Node, Python, Java, Rust, and a mixed monorepo, then runs bootstrap + validate
- `verify_template_snapshots.py`
  - compares rendered CI workflows for five language fixtures against committed snapshots
- `apply_github_config.py`
  - batches GitHub Actions secrets and variables with `gh`, supports `--dry-run` and `--mode skip|upsert`

### references/

- `deploy-patterns.md`
  - when to choose `docker-ssh` vs `docker-registry-only` vs `ci-only`
- `secrets-checklist.md`
  - required GitHub Secrets and Variables by deploy mode
- `repo-config.md`
  - config keys, policy defaults, and action supply-chain options
- `cicd-bootstrap.schema.json`
  - JSON Schema for editor support and config governance

### assets/

- CI templates by project type:
  - `go-service`
  - `node-service`
  - `python-service`
  - `java-service`
  - `rust-service`
  - `docker-service`
- Dockerfile templates:
  - `go-service`
  - `node-service`
  - `python-service`
  - `java-service`
  - `rust-service`
  - `static-web`
- shared deploy templates:
  - `ci-only` placeholders
  - `docker-ssh` remote Docker deployment
  - `docker-registry-only` image publishing
