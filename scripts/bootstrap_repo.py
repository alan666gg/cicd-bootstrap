#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import List

from generate_dockerfile import generate_service_dockerfiles
from generate_checklist import build_checklist
from render_workflow import (
    read_repo_config,
    render_support_files,
    render_service_workflows,
    resolve_service_specs,
    support_file_paths,
    workflow_filename,
)
from validate_workflow import validate_file, validate_with_actionlint


GENERATED_WORKFLOW_RE = re.compile(r"^(ci|deploy-test|deploy-prod)(-.+)?\.yml$")


def expected_workflow_paths(project_root: Path, workflow_dir: Path, specs) -> List[Path]:
    paths: List[Path] = []
    for spec in specs:
        slug = str(spec["slug"])
        multi_service = bool(spec["multi_service"])
        for base in ("ci", "deploy-test", "deploy-prod"):
            paths.append(workflow_dir / workflow_filename(base, slug, multi_service))
    return paths


def cleanup_stale_workflows(workflow_dir: Path, expected_paths: List[Path], force: bool) -> None:
    if not force or not workflow_dir.exists():
        return
    expected_names = {path.name for path in expected_paths}
    for path in workflow_dir.glob("*.yml"):
        if path.name not in expected_names and GENERATED_WORKFLOW_RE.match(path.name):
            path.unlink()


def ensure_can_write(paths: List[Path], checklist_file: Path, force: bool) -> None:
    existing = [path for path in [*paths, checklist_file] if path.exists()]
    if existing and not force:
        joined = ", ".join(str(path) for path in existing)
        raise SystemExit(f"refusing to overwrite existing files without --force: {joined}")


def validate_all(workflow_dir: Path, paths: List[Path], checklist_file: Path) -> List[str]:
    errors: List[str] = []
    for path in paths:
        errors.extend(validate_file(path, checklist_file))
    errors.extend(validate_with_actionlint(workflow_dir))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap GitHub CI/CD files for a repository.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for a single monorepo service")
    parser.add_argument("--service-paths", default="", help="Comma-separated subdirectories for multi-service generation")
    parser.add_argument("--app-name", default="", help="App/service name or prefix for multi-service mode")
    parser.add_argument(
        "--project-type",
        default="auto",
        help="go-service|node-service|python-service|java-service|rust-service|docker-service|auto",
    )
    parser.add_argument("--deploy-mode", "--deploy-strategy", dest="deploy_mode", default="auto", help="ci-only|docker-ssh|docker-registry-only|auto")
    parser.add_argument("--generate-dockerfile", action="store_true", help="Generate a high-performance Dockerfile before rendering workflows")
    parser.add_argument("--overwrite-dockerfile", action="store_true", help="Overwrite an existing Dockerfile when generating one")
    parser.add_argument(
        "--dockerfile-kind",
        default="auto",
        help="auto|go-service|node-service|python-service|java-service|rust-service|static-web",
    )
    parser.add_argument("--binary-name", default="", help="Go or Rust binary name override for generated Dockerfiles")
    parser.add_argument("--start-command", default="", help="Runtime command override for generated Dockerfiles")
    parser.add_argument("--build-dir", default="", help="Static-web build output directory override for generated Dockerfiles")
    parser.add_argument("--no-dockerignore", action="store_true", help="Skip generating .dockerignore with generated Dockerfiles")
    parser.add_argument("--test-target", default="", help="Optional test deploy target label")
    parser.add_argument("--prod-target", default="", help="Optional production deploy target label")
    parser.add_argument("--test-branch", default="", help="Test branch name")
    parser.add_argument("--workflow-dir", default=".github/workflows", help="Workflow output dir")
    parser.add_argument("--checklist-file", default=".github/cicd-bootstrap-checklist.md", help="Checklist output file")
    parser.add_argument("--force", action="store_true", help="Allow overwriting generated files")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    workflow_dir = (project_root / args.workflow_dir).resolve()
    checklist_file = (project_root / args.checklist_file).resolve()

    repo_config = read_repo_config(project_root)
    args.generate_dockerignore = not args.no_dockerignore
    dockerfile_results = []
    if args.generate_dockerfile or bool(repo_config.get("generate_dockerfile")):
        dockerfile_results = generate_service_dockerfiles(project_root, repo_config, args)
    specs = resolve_service_specs(project_root, repo_config, args)
    workflow_paths = expected_workflow_paths(project_root, workflow_dir, specs)
    helper_paths = support_file_paths(project_root, specs)

    ensure_can_write([*workflow_paths, *helper_paths], checklist_file, args.force)
    cleanup_stale_workflows(workflow_dir, workflow_paths, args.force)

    rendered_files: List[Path] = []
    for spec in specs:
        rendered_files.extend(render_service_workflows(workflow_dir, spec))
    support_files = render_support_files(project_root, specs)

    service_paths = [str(spec["service_path"]) for spec in specs]
    app_name_label = str(specs[0]["app_name"]) if len(specs) == 1 else ", ".join(str(spec["app_name"]) for spec in specs)
    deploy_mode_label = str(specs[0]["deploy_mode"]) if len({str(spec["deploy_mode"]) for spec in specs}) == 1 else "mixed"
    test_branch_label = str(specs[0]["test_branches"][0]) if specs else "develop"
    checklist_content = build_checklist(
        project_root,
        service_paths,
        app_name_label,
        deploy_mode_label,
        test_branch_label,
        [str(spec["project_type"]) for spec in specs],
    )
    checklist_file.parent.mkdir(parents=True, exist_ok=True)
    checklist_file.write_text(checklist_content, encoding="utf-8")

    errors = validate_all(workflow_dir, rendered_files, checklist_file)
    result = {
        "project_root": str(project_root),
        "service_root": str(specs[0]["service_root"]) if len(specs) == 1 else None,
        "service_path": str(specs[0]["service_path"]) if len(specs) == 1 else None,
        "service_paths": service_paths,
        "services": [
            {
                "service_path": str(spec["service_path"]),
                "service_root": str(spec["service_root"]),
                "slug": str(spec["slug"]),
                "app_name": str(spec["app_name"]),
                "project_type": str(spec["project_type"]),
                "deploy_mode": str(spec["deploy_mode"]),
            }
            for spec in specs
        ],
        "workflow_dir": str(workflow_dir),
        "checklist_file": str(checklist_file),
        "support_files": [str(path) for path in support_files],
        "dockerfiles": dockerfile_results,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
