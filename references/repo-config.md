# Repo Config

The bootstrap flow can read an optional repository config file:

```text
.github/cicd-bootstrap.json
```

## Supported fields

Core:
- `app_name`
- `project_type`
- `deploy_strategy` or `deploy_mode`
- `service_path`
- `service_paths`

`app_name` is normalized to lowercase kebab-case before it is used in workflow output, image names, and generated artifact names. For example, `seers-sourceBinance` becomes `seers-source-binance`.
For `docker-registry-only`, `image_registry` is also trimmed and the workflow lowercases the final registry prefix at runtime before login and push.
If `app_name` is omitted for a monorepo service, the generator falls back to `<repo-name>-<service-slug>` to reduce image-name collisions in shared registries.

Branch defaults:
- `default_branch`
- `default_branches`
- `test_branch`
- `test_branches`

Organization defaults:
- `image_registry`
- `healthcheck_url_test`
- `healthcheck_url_prod`
- `healthcheck_timeout_seconds`
- `rollback_on_failure`
- `remote_image_retention`
- `dependency_checks_test`
- `dependency_checks_prod`
- `dependency_checks_blocking`
- `runner`
- `default_shell`
- `default_job_timeout_minutes`
- `deploy_job_timeout_minutes`
- `enable_security_scan`
- `security_scan_blocking`
- `action_pin_mode`
- `allow_actions`
- `pinned_actions`
- `enable_cache`
- `test_environment`
- `staging_environment`
- `prod_environment`

Dockerfile generation:
- `generate_dockerfile`
- `dockerfile_kind`
- `docker_build_dir`
- `docker_start_command`
- `binary_name`

Detected project types:
- `go-service`
- `node-service`
- `python-service`
- `java-service`
- `rust-service`
- `docker-service`

## Example

```json
{
  "app_name": "kairos-api",
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
  "dependency_checks_test": ["tcp://127.0.0.1:6379", "cmd:docker ps --format '{{.Names}}' | grep -q '^redis$'"],
  "dependency_checks_prod": ["tcp://10.0.0.12:6379", "http://10.0.0.20:8080/readyz"],
  "dependency_checks_blocking": false,
  "runner": "ubuntu-latest",
  "default_shell": "bash --noprofile --norc -euo pipefail {0}",
  "default_job_timeout_minutes": 20,
  "deploy_job_timeout_minutes": 30,
  "enable_security_scan": true,
  "security_scan_blocking": false,
  "action_pin_mode": "tag",
  "allow_actions": ["actions/checkout", "docker/build-push-action"],
  "enable_cache": true,
  "test_environment": "test",
  "prod_environment": "prod",
  "generate_dockerfile": true,
  "dockerfile_kind": "static-web",
  "docker_build_dir": "dist"
}
```

`dockerfile_kind` also accepts `python-service`, `java-service`, and `rust-service`.

## Precedence

1. Explicit CLI flags
2. `.github/cicd-bootstrap.json`
3. Auto detection

## Security Scan Defaults

- `enable_security_scan` defaults to `true`.
- `security_scan_blocking` defaults to `false` so bootstrap output is resilient to transient scanner/network failures.
- When `security_scan_blocking` is `true`, CI remains non-blocking for pull requests and non-release test branches such as `develop`.
- When `security_scan_blocking` is `true`, pushes to the default branch and `release` / `release/*` branches block on `HIGH` / `CRITICAL` findings.

## Action Supply Chain Defaults

- `action_pin_mode` defaults to `tag` for maintainability.
- Set `action_pin_mode` to `sha` when you want stricter supply-chain control.
- When `action_pin_mode` is `sha`, define `pinned_actions` for every action actually used by the rendered workflow.
- `allow_actions` lets teams keep generated workflows inside an approved action whitelist.

## Docker-SSH Deploy Defaults

- `docker-ssh` workflows create the remote directory with `mkdir -p` before upload.
- The remote switch logic is generated into `scripts/remote_deploy.sh`.
- `healthcheck_url_test` and `healthcheck_url_prod` let you define environment-specific HTTP checks.
- `healthcheck_timeout_seconds` defaults to `40`.
- `rollback_on_failure` defaults to `true`, so a failed healthcheck attempts to start the previous image again.
- `remote_image_retention` defaults to `3`, so old images are pruned after successful deploys.
- `dependency_checks_test` and `dependency_checks_prod` let you declare runtime dependency checks before deploy.
- Supported dependency check formats are:
  - `tcp://host:port`
  - `http://host/path` or `https://host/path`
  - `cmd:<shell command>`
- `dependency_checks_blocking` defaults to `false`, so failed checks raise warnings and reminders before the team decides to make them blocking.

## Language Notes

- Python repositories cache best when a lock-like dependency file is present; without one, `pip` caches still work but miss more often.
- Java repositories should commit the Gradle wrapper when using Gradle; the generated CI will restore execute permission automatically.
- Rust repositories should prefer checking in `Cargo.lock` for reproducible CI and better cache keys.
