#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"


def detect_project(root: Path) -> Dict[str, object]:
    from detect_project import detect_project as detect

    return detect(root)


def find_candidates(project_root: Path) -> List[str]:
    from detect_project import find_candidates as detect_candidates

    return detect_candidates(project_root)


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
    if deploy_mode == "docker-registry-only":
        return (
            ASSETS_DIR / "shared" / "deploy-test-docker-registry-only.yml.tmpl",
            ASSETS_DIR / "shared" / "deploy-prod-docker-registry-only.yml.tmpl",
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


def read_repo_config(project_root: Path) -> Dict[str, object]:
    config_path = project_root / ".github" / "cicd-bootstrap.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def get_deploy_mode(repo_config: Dict[str, object], cli_value: str, detected: Dict[str, object]) -> str:
    if cli_value != "auto":
        return cli_value
    return str(repo_config.get("deploy_strategy", repo_config.get("deploy_mode", detected["deploy_mode"])))


def ensure_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return [str(value).strip()]


def parse_service_paths(cli_service_path: str, cli_service_paths: str, repo_config: Dict[str, object]) -> List[str]:
    values: List[str] = []
    if cli_service_paths.strip():
        values.extend(ensure_list(cli_service_paths))
    elif cli_service_path.strip():
        values.append(cli_service_path.strip())
    elif repo_config.get("service_paths"):
        values.extend(ensure_list(repo_config.get("service_paths")))
    elif repo_config.get("service_path"):
        values.append(str(repo_config.get("service_path")).strip())
    else:
        values.append(".")

    normalized = []
    seen = set()
    for item in values:
        service_path = item.strip() or "."
        if service_path not in seen:
            normalized.append(service_path)
            seen.add(service_path)
    return normalized


def build_branch_lines(branches: List[str]) -> str:
    unique: List[str] = []
    seen = set()
    for branch in branches:
        if branch and branch not in seen:
            unique.append(branch)
            seen.add(branch)
    return "\n".join(f"      - {branch}" for branch in unique)


def bool_from_config(repo_config: Dict[str, object], key: str, default: bool) -> bool:
    value = repo_config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def lockfile_for_package_manager(package_manager: str) -> str:
    if package_manager == "pnpm":
        return "pnpm-lock.yaml"
    if package_manager == "yarn":
        return "yarn.lock"
    return "package-lock.json"


def build_go_cache_steps(enable_cache: bool) -> str:
    if not enable_cache:
        return ""
    return """      - name: Cache Go modules
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/go-build
            ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
          restore-keys: |
            ${{ runner.os }}-go-

"""


def build_node_cache_block(enable_cache: bool, package_manager: str, service_path: str) -> str:
    if not enable_cache:
        return ""
    dependency_path = lockfile_for_package_manager(package_manager)
    if service_path != ".":
        dependency_path = f"{service_path}/{dependency_path}"
    return f"""          cache: {package_manager or 'npm'}
          cache-dependency-path: {dependency_path}
"""


def build_security_scan_job(enable_security_scan: bool, runner: str, build_job_name: str, scan_ref: str) -> str:
    if not enable_security_scan:
        return ""
    return f"""
  security-scan:
    runs-on: {runner}
    timeout-minutes: 20
    needs: {build_job_name}
    permissions:
      contents: read
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Run Trivy filesystem scan
        uses: aquasecurity/trivy-action@0.28.0
        with:
          scan-type: fs
          scan-ref: {scan_ref}
          format: table
          exit-code: '1'
          ignore-unfixed: true
          severity: CRITICAL,HIGH
"""


def image_registry(repo_config: Dict[str, object]) -> str:
    return str(repo_config.get("image_registry", "ghcr.io/${{ github.repository_owner }}"))


def image_registry_host(registry: str) -> str:
    return registry.split("/", 1)[0]


def service_slug(service_path: str, fallback: str) -> str:
    raw = service_path if service_path != "." else fallback
    return raw.strip("./").replace("/", "-").replace("_", "-")


def workflow_filename(base_name: str, slug: str, multi_service: bool) -> str:
    return f"{base_name}-{slug}.yml" if multi_service else f"{base_name}.yml"


def workflow_display_name(base_name: str, slug: str, multi_service: bool) -> str:
    label_map = {
        "ci": "CI",
        "deploy-test": "Deploy Test",
        "deploy-prod": "Deploy Prod",
    }
    label = label_map.get(base_name, base_name)
    return f"{label} ({slug})" if multi_service else label


def resolve_branches(repo_config: Dict[str, object], cli_test_branch: str) -> Tuple[List[str], List[str]]:
    default_branches = ensure_list(repo_config.get("default_branches"))
    if not default_branches:
        default_branch = str(repo_config.get("default_branch", "main")).strip() or "main"
        default_branches = [default_branch]

    test_branches = ensure_list(repo_config.get("test_branches"))
    if not test_branches:
        fallback = str(repo_config.get("test_branch", cli_test_branch or "develop")).strip() or "develop"
        test_branches = [fallback]
    return default_branches, test_branches


def resolve_service_specs(project_root: Path, repo_config: Dict[str, object], args) -> List[Dict[str, object]]:
    service_paths = parse_service_paths(args.service_path, getattr(args, "service_paths", ""), repo_config)
    multi_service = len(service_paths) > 1
    default_branches, test_branches = resolve_branches(repo_config, getattr(args, "test_branch", ""))
    runner = str(repo_config.get("runner", "ubuntu-latest"))
    test_environment = str(repo_config.get("test_environment", "test"))
    prod_environment = str(repo_config.get("prod_environment", "prod"))
    registry = image_registry(repo_config)
    enable_cache = bool_from_config(repo_config, "enable_cache", True)
    enable_security_scan = bool_from_config(repo_config, "enable_security_scan", True)

    specs: List[Dict[str, object]] = []
    for current_service_path in service_paths:
        service_root = (project_root / current_service_path).resolve() if current_service_path != "." else project_root
        detected = detect_project(service_root)
        project_type = repo_config.get("project_type", detected["project_type"]) if args.project_type == "auto" else args.project_type
        deploy_mode = get_deploy_mode(repo_config, args.deploy_mode, detected)
        if project_type == "unknown":
            hint = ""
            candidates = find_candidates(project_root) if current_service_path == "." else []
            if candidates:
                hint = f"; try --service-path {candidates[0]}"
            raise SystemExit(f"could not detect project type for {current_service_path}{hint}")
        if deploy_mode == "docker-registry-only" and not detected.get("has_dockerfile"):
            raise SystemExit(f"docker-registry-only requires a Dockerfile in {current_service_path}")

        slug = service_slug(current_service_path, str(detected["app_name"]))
        base_app_name = normalize(args.app_name, str(repo_config.get("app_name", detected["app_name"])))
        app_name = f"{base_app_name}-{slug}" if multi_service and (args.app_name.strip() or repo_config.get("app_name")) else base_app_name
        test_target = normalize(args.test_target, str(repo_config.get("test_target", app_name)))
        prod_target = normalize(args.prod_target, str(repo_config.get("prod_target", app_name)))

        specs.append(
            {
                "service_path": current_service_path,
                "service_root": service_root,
                "project_type": project_type,
                "deploy_mode": deploy_mode,
                "detected": detected,
                "slug": slug,
                "app_name": app_name,
                "test_target": test_target,
                "prod_target": prod_target,
                "default_branches": default_branches,
                "test_branches": test_branches,
                "runner": runner,
                "test_environment": test_environment,
                "prod_environment": prod_environment,
                "image_registry": registry,
                "image_registry_host": image_registry_host(registry),
                "enable_cache": enable_cache,
                "enable_security_scan": enable_security_scan,
                "multi_service": multi_service,
            }
        )
    return specs


def build_replacements(spec: Dict[str, object], workflow_kind: str) -> Dict[str, str]:
    detected = spec["detected"]
    service_path = str(spec["service_path"])
    go_cache_steps = build_go_cache_steps(bool(spec["enable_cache"]))
    node_cache_block = build_node_cache_block(bool(spec["enable_cache"]), str(detected.get("package_manager") or "npm"), service_path)
    build_job_name = "docker-build" if spec["project_type"] == "docker-service" else "test-and-build"
    security_scan_job = build_security_scan_job(bool(spec["enable_security_scan"]), str(spec["runner"]), build_job_name, service_path)

    return {
        "APP_NAME": str(spec["app_name"]),
        "TEST_TARGET": str(spec["test_target"]),
        "PROD_TARGET": str(spec["prod_target"]),
        "SERVICE_PATH": service_path,
        "DOCKER_CONTEXT": service_path,
        "RUNNER": str(spec["runner"]),
        "WORKFLOW_NAME": workflow_display_name(workflow_kind, str(spec["slug"]), bool(spec["multi_service"])),
        "CONCURRENCY_GROUP": f"{workflow_kind}-{spec['slug']}-${{{{ github.ref }}}}",
        "CI_BRANCH_LINES": build_branch_lines([*spec["default_branches"], *spec["test_branches"]]),
        "TEST_BRANCH_LINES": build_branch_lines(list(spec["test_branches"])),
        "DEFAULT_BRANCH": str(spec["default_branches"][0]),
        "TEST_BRANCH": str(spec["test_branches"][0]),
        "TEST_ENVIRONMENT": str(spec["test_environment"]),
        "PROD_ENVIRONMENT": str(spec["prod_environment"]),
        "IMAGE_REGISTRY": str(spec["image_registry"]),
        "IMAGE_REGISTRY_HOST": str(spec["image_registry_host"]),
        "GO_CACHE_STEPS": go_cache_steps,
        "NODE_CACHE_BLOCK": node_cache_block,
        "SECURITY_SCAN_JOB": security_scan_job,
        "TEST_COMMAND": str(detected["test_command"]),
        "BUILD_COMMAND": str(detected["build_command"]),
        "INSTALL_COMMAND": str(detected.get("install_command") or "npm ci"),
    }


def render_service_workflows(output_dir: Path, spec: Dict[str, object]) -> List[Path]:
    project_type = str(spec["project_type"])
    deploy_mode = str(spec["deploy_mode"])
    slug = str(spec["slug"])
    multi_service = bool(spec["multi_service"])

    ci_template = load_template(choose_ci_template(project_type))
    deploy_test_template, deploy_prod_template = choose_deploy_templates(deploy_mode)

    files = [
        (workflow_filename("ci", slug, multi_service), render_template(ci_template, build_replacements(spec, "ci"))),
        (
            workflow_filename("deploy-test", slug, multi_service),
            render_template(load_template(deploy_test_template), build_replacements(spec, "deploy-test")),
        ),
        (
            workflow_filename("deploy-prod", slug, multi_service),
            render_template(load_template(deploy_prod_template), build_replacements(spec, "deploy-prod")),
        ),
    ]

    written: List[Path] = []
    for file_name, content in files:
        path = output_dir / file_name
        write_file(path, content)
        written.append(path)
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Render GitHub Actions workflows from templates.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for a single monorepo service")
    parser.add_argument("--service-paths", default="", help="Comma-separated subdirectories for multi-service generation")
    parser.add_argument("--output-dir", default=".github/workflows", help="Workflow output directory")
    parser.add_argument("--project-type", default="auto", help="go-service|node-service|docker-service|auto")
    parser.add_argument("--deploy-mode", "--deploy-strategy", dest="deploy_mode", default="auto", help="ci-only|docker-ssh|docker-registry-only|auto")
    parser.add_argument("--app-name", default="", help="Workflow app/service name")
    parser.add_argument("--test-target", default="", help="Optional test deploy target label")
    parser.add_argument("--prod-target", default="", help="Optional production deploy target label")
    parser.add_argument("--test-branch", default="", help="Branch name for test deploy")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    output_dir = (project_root / args.output_dir).resolve()
    repo_config = read_repo_config(project_root)
    specs = resolve_service_specs(project_root, repo_config, args)

    written_files: List[str] = []
    services = []
    for spec in specs:
        rendered = render_service_workflows(output_dir, spec)
        written_files.extend(str(path) for path in rendered)
        services.append(
            {
                "service_path": str(spec["service_path"]),
                "service_root": str(spec["service_root"]),
                "slug": str(spec["slug"]),
                "app_name": str(spec["app_name"]),
                "project_type": str(spec["project_type"]),
                "deploy_mode": str(spec["deploy_mode"]),
            }
        )

    summary = {
        "project_root": str(project_root),
        "service_root": str(specs[0]["service_root"]) if len(specs) == 1 else None,
        "service_path": str(specs[0]["service_path"]) if len(specs) == 1 else None,
        "service_paths": [str(spec["service_path"]) for spec in specs],
        "output_dir": str(output_dir),
        "files": written_files,
        "services": services,
        "required_secrets_reference": str(SKILL_DIR / "references" / "secrets-checklist.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
