---
name: github-cicd-bootstrap
description: Use when a user wants to add or standardize GitHub CI/CD for a repository, especially for Go services, Node services, or Dockerized apps. This skill detects the project type, generates generic GitHub Actions workflows, creates a setup checklist, and validates the resulting CI/CD files.
---

# GitHub CI/CD Bootstrap

This skill builds a reusable GitHub Actions pipeline for a repository with as little manual setup as possible.

Use it when the user asks to:
- add GitHub Actions to a repo
- build a CI/CD pipeline for a service or app
- standardize test, build, and deploy workflows
- generate workflow files and the required GitHub secrets checklist

## Quick Start

### Fast path

Use the bootstrap script when the user wants the skill to do the full setup in one pass.

```bash
python3 skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
  --project-root . \
  --app-name my-service \
  --test-target my-service \
  --prod-target my-service
```

This command:
- detects the project type
- chooses the deploy mode
- reads `.github/cicd-bootstrap.json` automatically when present
- writes workflow files to `.github/workflows`
- generates a setup checklist at `.github/cicd-bootstrap-checklist.md`
- validates the generated workflows

### Step-by-step path

1. Detect the project type:
   ```bash
   python3 skills/github-cicd-bootstrap/scripts/detect_project.py --project-root .
   ```
2. Render workflows:
   ```bash
   python3 skills/github-cicd-bootstrap/scripts/render_workflow.py --project-root . --output-dir .github/workflows
   ```
3. Generate the setup checklist:
   ```bash
   python3 skills/github-cicd-bootstrap/scripts/generate_checklist.py \
     --project-root . \
     --output-file .github/cicd-bootstrap-checklist.md
   ```
4. Validate the generated files:
   ```bash
   python3 skills/github-cicd-bootstrap/scripts/validate_workflow.py --workflow-dir .github/workflows
   ```

### Optional repo config

If the repo has repeated CI/CD conventions, create:

```text
.github/cicd-bootstrap.json
```

Example:
```json
{
  "app_name": "deposit",
  "project_type": "go-service",
  "deploy_mode": "tool-script",
  "test_target": "deposit",
  "prod_target": "deposit",
  "test_branch": "develop"
}
```

When this file exists, `bootstrap_repo.py` will load it automatically. CLI flags still override the config file.

## What This Skill Generates

- `ci.yml`
  - repository-level CI for test and build validation
- `deploy-test.yml`
  - test environment deployment workflow
- `deploy-prod.yml`
  - production deployment workflow

The generator supports two deploy patterns:

1. `docker-ssh`
   - use when the repo is already Dockerized
   - builds an image in GitHub Actions and switches the container on a remote host over SSH

2. `ci-only`
   - use when the repo does not yet have a Docker-based deploy target
   - generates CI plus placeholder deploy workflows that guide the team to choose a release strategy later

## Workflow

### 1. Detect the repository shape

Run `scripts/detect_project.py` first. It decides:
- project type: `go-service`, `node-service`, or `docker-service`
- package manager when relevant
- whether the repo already has a `Dockerfile`

If detection is wrong, rerun the render step with explicit flags instead of editing the detector.

### 2. Choose the deploy mode

Use this decision order:

- If the repo has a `Dockerfile`, prefer `docker-ssh`
- Else use `ci-only`
- If the user wants deployment but the repo is not yet Dockerized, generate CI first and explain that deployment still needs a runtime target

### 3. Render the workflows

Use `scripts/render_workflow.py`. It fills templates and writes workflow files.

Recommended command for a Dockerized service:
```bash
python3 skills/github-cicd-bootstrap/scripts/render_workflow.py \
  --project-root . \
  --output-dir .github/workflows \
  --deploy-mode docker-ssh \
  --app-name my-service
```

Recommended command for a non-Docker repo that still needs CI scaffolding:
```bash
python3 skills/github-cicd-bootstrap/scripts/render_workflow.py \
  --project-root . \
  --output-dir .github/workflows \
  --deploy-mode ci-only \
  --app-name my-service
```

### 4. Validate before presenting the result

Always run:
```bash
python3 skills/github-cicd-bootstrap/scripts/validate_workflow.py --workflow-dir .github/workflows
```

Validation checks:
- required workflow files exist
- unresolved placeholders are not left behind
- each workflow has `name`, `on`, and `jobs`

### 5. Tell the user what still needs manual input

Always summarize:
- which deploy mode was chosen
- which secrets are required
- which repository variables are required
- whether branch names need adjusting

Use [references/secrets-checklist.md](references/secrets-checklist.md) when summarizing setup requirements.
Use [references/deploy-patterns.md](references/deploy-patterns.md) when deciding between internal scripts and generic SSH deployment.
If the user wants direct output in one shot, prefer `scripts/bootstrap_repo.py`.

## Guardrails

- Do not overwrite an existing workflow unless the user clearly wants replacement.
- Prefer generating to `.github/workflows` and then showing a concise diff summary.
- If the repository already has bespoke CI/CD, preserve the established pattern rather than forcing the templates here.
- Prefer `docker-ssh` only if the repo is already Dockerized or the user explicitly wants Docker-based delivery.
- Prefer `ci-only` when the release target is still undecided.

## Resources

### scripts/

- `detect_project.py`
  - identifies project type and deploy affordances
- `render_workflow.py`
  - renders workflow files from templates
- `generate_checklist.py`
  - generates the secrets and variables setup checklist
- `bootstrap_repo.py`
  - performs detect -> render -> checklist -> validate in one run
- `validate_workflow.py`
  - runs lightweight validation on generated workflows

### references/

- `deploy-patterns.md`
  - when to choose `docker-ssh` vs `ci-only`
- `secrets-checklist.md`
  - required GitHub Secrets and Variables by deploy mode

### assets/

- CI templates by project type:
  - `go-service`
  - `node-service`
  - `docker-service`
- shared deploy templates:
  - internal script based
  - generic SSH Docker switch
