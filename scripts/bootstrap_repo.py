#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from detect_project import detect_project
from generate_checklist import build_checklist
from render_workflow import (
    choose_ci_template,
    choose_deploy_templates,
    load_template,
    normalize,
    render_template,
    write_file,
)
from validate_workflow import validate_file


WORKFLOW_FILES = ("ci.yml", "deploy-test.yml", "deploy-prod.yml")


def read_repo_config(project_root: Path):
    config_path = project_root / ".github" / "cicd-bootstrap.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def ensure_can_write(workflow_dir: Path, checklist_file: Path, force: bool) -> None:
    files_to_check = [workflow_dir / name for name in WORKFLOW_FILES] + [checklist_file]
    existing = [path for path in files_to_check if path.exists()]
    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise SystemExit(f"refusing to overwrite existing files without --force: {joined}")


def render_all(
    workflow_dir: Path,
    app_name: str,
    deploy_mode: str,
    project_type: str,
    test_target: str,
    prod_target: str,
    test_branch: str,
    service_path: str,
) -> None:
    replacements = {
        "APP_NAME": app_name,
        "TEST_BRANCH": test_branch,
        "TEST_TARGET": test_target,
        "PROD_TARGET": prod_target,
        "SERVICE_PATH": service_path,
        "DOCKER_CONTEXT": service_path,
    }
    ci_template = load_template(choose_ci_template(project_type))
    deploy_test_template, deploy_prod_template = choose_deploy_templates(deploy_mode)

    write_file(workflow_dir / "ci.yml", render_template(ci_template, replacements))
    write_file(workflow_dir / "deploy-test.yml", render_template(load_template(deploy_test_template), replacements))
    write_file(workflow_dir / "deploy-prod.yml", render_template(load_template(deploy_prod_template), replacements))


def validate_all(workflow_dir: Path) -> list:
    errors = []
    for file_name in WORKFLOW_FILES:
        errors.extend(validate_file(workflow_dir / file_name))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap GitHub CI/CD files for a repository.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for monorepo service")
    parser.add_argument("--app-name", default="", help="App/service name")
    parser.add_argument("--project-type", default="auto", help="go-service|node-service|docker-service|auto")
    parser.add_argument("--deploy-mode", default="auto", help="ci-only|docker-ssh|auto")
    parser.add_argument("--test-target", default="", help="Optional test deploy target label")
    parser.add_argument("--prod-target", default="", help="Optional production deploy target label")
    parser.add_argument("--test-branch", default="develop", help="Test branch name")
    parser.add_argument("--workflow-dir", default=".github/workflows", help="Workflow output dir")
    parser.add_argument("--checklist-file", default=".github/cicd-bootstrap-checklist.md", help="Checklist output file")
    parser.add_argument("--force", action="store_true", help="Allow overwriting generated files")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    repo_config = read_repo_config(project_root)
    service_path = args.service_path or repo_config.get("service_path", ".")
    service_root = (project_root / service_path).resolve() if service_path and service_path != "." else project_root
    detected = detect_project(service_root)
    project_type = repo_config.get("project_type", detected["project_type"]) if args.project_type == "auto" else args.project_type
    deploy_mode = repo_config.get("deploy_mode", detected["deploy_mode"]) if args.deploy_mode == "auto" else args.deploy_mode

    if project_type == "unknown":
        hint = ""
        candidates = detected.get("candidates") or []
        if candidates:
            hint = f"; try --service-path {candidates[0]}"
        raise SystemExit(f"could not detect project type{hint}")
    app_name = normalize(args.app_name, str(repo_config.get("app_name", detected["app_name"])))
    test_target = normalize(args.test_target, repo_config.get("test_target", app_name))
    prod_target = normalize(args.prod_target, repo_config.get("prod_target", app_name))
    test_branch = normalize(args.test_branch, repo_config.get("test_branch", args.test_branch))
    workflow_dir = (project_root / args.workflow_dir).resolve()
    checklist_file = (project_root / args.checklist_file).resolve()

    ensure_can_write(workflow_dir, checklist_file, args.force)
    render_all(workflow_dir, app_name, deploy_mode, project_type, test_target, prod_target, test_branch, service_path)
    checklist_content = build_checklist(project_root, service_path, app_name, deploy_mode, test_branch)
    write_file(checklist_file, checklist_content)

    errors = validate_all(workflow_dir)
    result = {
        "project_root": str(project_root),
        "service_root": str(service_root),
        "service_path": args.service_path or repo_config.get("service_path", "."),
        "project_type": project_type,
        "deploy_mode": deploy_mode,
        "workflow_dir": str(workflow_dir),
        "checklist_file": str(checklist_file),
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
