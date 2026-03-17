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

Branch defaults:
- `default_branch`
- `default_branches`
- `test_branch`
- `test_branches`

Organization defaults:
- `image_registry`
- `runner`
- `enable_security_scan`
- `enable_cache`
- `test_environment`
- `prod_environment`

## Example

```json
{
  "app_name": "kairos-api",
  "deploy_strategy": "docker-registry-only",
  "service_paths": ["services/api", "services/worker"],
  "default_branch": "main",
  "test_branches": ["develop", "release/*"],
  "image_registry": "ghcr.io/acme-platform",
  "runner": "ubuntu-latest",
  "enable_security_scan": true,
  "enable_cache": true,
  "test_environment": "test",
  "prod_environment": "prod"
}
```

## Precedence

1. Explicit CLI flags
2. `.github/cicd-bootstrap.json`
3. Auto detection
