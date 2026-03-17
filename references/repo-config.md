# Repo Config

The bootstrap flow can read an optional repository config file:

```text
.github/cicd-bootstrap.json
```

## Supported fields

- `app_name`
- `project_type`
- `deploy_mode`
- `service_path`
- `test_branch`

## Example

```json
{
  "app_name": "my-service",
  "project_type": "go-service",
  "deploy_mode": "docker-ssh",
  "service_path": "services/api",
  "test_branch": "develop"
}
```

## Precedence

1. Explicit CLI flags
2. `.github/cicd-bootstrap.json`
3. Auto detection
