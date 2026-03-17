# Repo Config

The bootstrap flow can read an optional repository config file:

```text
.github/cicd-bootstrap.json
```

## Supported fields

- `app_name`
- `project_type`
- `deploy_mode`
- `test_target`
- `prod_target`
- `test_branch`

## Example

```json
{
  "app_name": "walletpd",
  "project_type": "go-service",
  "deploy_mode": "docker-ssh",
  "test_target": "site",
  "prod_target": "site",
  "test_branch": "develop"
}
```

## Precedence

1. Explicit CLI flags
2. `.github/cicd-bootstrap.json`
3. Auto detection
