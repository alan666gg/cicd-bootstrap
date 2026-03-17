#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"


def detect_project(root: Path) -> Dict[str, object]:
    from detect_project import detect_project as detect

    return detect(root)


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def choose_ci_template(project_type: str) -> Path:
    if project_type == "go-service":
        return ASSETS_DIR / "go-service" / "ci.yml.tmpl"
    if project_type == "node-service":
        return ASSETS_DIR / "node-service" / "ci.yml.tmpl"
    if project_type == "docker-service":
        return ASSETS_DIR / "docker-service" / "ci.yml.tmpl"
    raise ValueError(f"unsupported project type: {project_type}")


def choose_deploy_templates(deploy_mode: str) -> Tuple[Path, Path]:
    if deploy_mode == "ci-only":
        return (
            ASSETS_DIR / "shared" / "deploy-test-ci-only.yml.tmpl",
            ASSETS_DIR / "shared" / "deploy-prod-ci-only.yml.tmpl",
        )
    if deploy_mode == "docker-ssh":
        return (
            ASSETS_DIR / "shared" / "deploy-test-docker-ssh.yml.tmpl",
            ASSETS_DIR / "shared" / "deploy-prod-docker-ssh.yml.tmpl",
        )
    raise ValueError(f"unsupported deploy mode: {deploy_mode}")


def render_template(template: str, replacements: Dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"__{key}__", value)
    return rendered


def normalize(value, fallback: str) -> str:
    return value.strip() if value and value.strip() else fallback


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def read_repo_config(project_root: Path) -> Dict[str, str]:
    config_path = project_root / ".github" / "cicd-bootstrap.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Render GitHub Actions workflows from templates.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for monorepo service")
    parser.add_argument("--output-dir", default=".github/workflows", help="Workflow output directory")
    parser.add_argument("--project-type", default="auto", help="go-service|node-service|docker-service|auto")
    parser.add_argument("--deploy-mode", default="auto", help="ci-only|docker-ssh|auto")
    parser.add_argument("--app-name", default="", help="Workflow app/service name")
    parser.add_argument("--test-target", default="", help="Optional test deploy target label")
    parser.add_argument("--prod-target", default="", help="Optional production deploy target label")
    parser.add_argument("--test-branch", default="develop", help="Branch name for test deploy")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    repo_config = read_repo_config(project_root)
    service_path = args.service_path or repo_config.get("service_path", ".")
    service_root = (project_root / service_path).resolve() if service_path and service_path != "." else project_root
    output_dir = (project_root / args.output_dir).resolve()

    detected = detect_project(service_root)
    project_type = repo_config.get("project_type", detected["project_type"]) if args.project_type == "auto" else args.project_type
    deploy_mode = repo_config.get("deploy_mode", detected["deploy_mode"]) if args.deploy_mode == "auto" else args.deploy_mode

    if project_type == "unknown":
        hint = ""
        candidates = detected.get("candidates") or []
        if candidates:
            hint = f"; try --service-path {candidates[0]}"
        raise SystemExit(f"could not detect project type{hint}")
    app_name = normalize(args.app_name, repo_config.get("app_name", detected["app_name"]))
    test_target = normalize(args.test_target, repo_config.get("test_target", app_name))
    prod_target = normalize(args.prod_target, repo_config.get("prod_target", app_name))
    test_branch = normalize(args.test_branch, repo_config.get("test_branch", args.test_branch))

    ci_template = load_template(choose_ci_template(project_type))
    deploy_test_template, deploy_prod_template = choose_deploy_templates(deploy_mode)

    replacements = {
        "APP_NAME": app_name,
        "TEST_BRANCH": test_branch,
        "TEST_TARGET": test_target,
        "PROD_TARGET": prod_target,
        "SERVICE_PATH": service_path,
        "DOCKER_CONTEXT": service_path,
    }

    write_file(output_dir / "ci.yml", render_template(ci_template, replacements))
    write_file(output_dir / "deploy-test.yml", render_template(load_template(deploy_test_template), replacements))
    write_file(output_dir / "deploy-prod.yml", render_template(load_template(deploy_prod_template), replacements))

    summary = {
        "project_root": str(project_root),
        "service_root": str(service_root),
        "service_path": service_path,
        "project_type": project_type,
        "deploy_mode": deploy_mode,
        "output_dir": str(output_dir),
        "files": [
            str(output_dir / "ci.yml"),
            str(output_dir / "deploy-test.yml"),
            str(output_dir / "deploy-prod.yml"),
        ],
        "required_secrets_reference": str(SKILL_DIR / "references" / "secrets-checklist.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
