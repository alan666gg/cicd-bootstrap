#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

from config import SAFE_BASH_SHELL, load_repo_config
from naming import normalize_name


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"
REMOTE_DEPLOY_SCRIPT_RELATIVE_PATH = "scripts/remote_deploy.sh"
DEFAULT_ACTION_REFS = {
    "actions/checkout": "v4",
    "actions/setup-go": "v5",
    "actions/setup-node": "v4",
    "actions/setup-python": "v5",
    "actions/setup-java": "v4",
    "actions/cache": "v4",
    "aquasecurity/trivy-action": "0.28.0",
    "webfactory/ssh-agent": "v0.9.0",
    "docker/setup-buildx-action": "v3",
    "docker/login-action": "v3",
    "docker/build-push-action": "v6",
    "dtolnay/rust-toolchain": "stable",
}


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
    if project_type == "python-service":
        return ASSETS_DIR / "python-service" / "ci.yml.tmpl"
    if project_type == "java-service":
        return ASSETS_DIR / "java-service" / "ci.yml.tmpl"
    if project_type == "rust-service":
        return ASSETS_DIR / "rust-service" / "ci.yml.tmpl"
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


def coalesce(value, fallback: str) -> str:
    return value.strip() if value and value.strip() else fallback


def join_name(prefix: str, suffix: str) -> str:
    if prefix == suffix or prefix.endswith(f"-{suffix}"):
        return prefix
    return f"{prefix}-{suffix}"


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def support_file_paths(project_root: Path, specs: List[Dict[str, object]]) -> List[Path]:
    if any(str(spec["deploy_mode"]) == "docker-ssh" for spec in specs):
        return [project_root / REMOTE_DEPLOY_SCRIPT_RELATIVE_PATH]
    return []


def read_repo_config(project_root: Path) -> Dict[str, object]:
    return load_repo_config(project_root)


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


def repo_relative_path(service_path: str, filename: str) -> str:
    return filename if service_path == "." else f"{service_path}/{filename}"


def resolve_action_ref(repo_config: Dict[str, object], action_name: str) -> str:
    allow_actions = set(ensure_list(repo_config.get("allow_actions")))
    if allow_actions and action_name not in allow_actions:
        raise SystemExit(f"action '{action_name}' is not allowed by allow_actions")
    pin_mode = str(repo_config.get("action_pin_mode", "tag"))
    if pin_mode == "sha":
        pinned_actions = repo_config.get("pinned_actions") or {}
        action_ref = str(pinned_actions.get(action_name, "")).strip()
        if not action_ref:
            raise SystemExit(f"action_pin_mode=sha requires pinned_actions['{action_name}']")
    else:
        action_ref = DEFAULT_ACTION_REFS[action_name]
    return f"{action_name}@{action_ref}"


def build_action_replacements(repo_config: Dict[str, object], required_actions: List[str]) -> Dict[str, str]:
    mapping = {
        "actions/checkout": "ACTION_CHECKOUT",
        "actions/setup-go": "ACTION_SETUP_GO",
        "actions/setup-node": "ACTION_SETUP_NODE",
        "actions/setup-python": "ACTION_SETUP_PYTHON",
        "actions/setup-java": "ACTION_SETUP_JAVA",
        "actions/cache": "ACTION_CACHE",
        "aquasecurity/trivy-action": "ACTION_TRIVY",
        "webfactory/ssh-agent": "ACTION_SSH_AGENT",
        "docker/setup-buildx-action": "ACTION_SETUP_BUILDX",
        "docker/login-action": "ACTION_DOCKER_LOGIN",
        "docker/build-push-action": "ACTION_DOCKER_BUILD_PUSH",
        "dtolnay/rust-toolchain": "ACTION_RUST_TOOLCHAIN",
    }
    replacements: Dict[str, str] = {}
    for action_name in required_actions:
        placeholder = mapping[action_name]
        replacements[placeholder] = resolve_action_ref(repo_config, action_name)
    return replacements


def build_go_cache_steps(enable_cache: bool, action_cache_ref: str) -> str:
    if not enable_cache:
        return ""
    return """      - name: Cache Go modules
        uses: __ACTION_CACHE__
        with:
          path: |
            ~/.cache/go-build
            ~/go/pkg/mod
          key: ${{ runner.os }}-go-${{ hashFiles('**/go.sum') }}
          restore-keys: |
            ${{ runner.os }}-go-

""".replace("__ACTION_CACHE__", action_cache_ref)


def build_node_cache_block(enable_cache: bool, package_manager: str, service_path: str) -> str:
    if not enable_cache:
        return ""
    dependency_path = lockfile_for_package_manager(package_manager)
    if service_path != ".":
        dependency_path = f"{service_path}/{dependency_path}"
    return f"""          cache: {package_manager or 'npm'}
          cache-dependency-path: {dependency_path}
"""


def build_python_cache_block(enable_cache: bool, dependency_files: List[str], service_path: str) -> str:
    if not enable_cache:
        return ""
    lines = ["          cache: pip"]
    if dependency_files:
        lines.append("          cache-dependency-path: |")
        for filename in dependency_files:
            lines.append(f"            {repo_relative_path(service_path, filename)}")
    return "\n".join(lines) + "\n"


def build_java_wrapper_step(has_gradle_wrapper: bool) -> str:
    if not has_gradle_wrapper:
        return ""
    return """      - name: Ensure Gradle wrapper is executable
        run: chmod +x ./gradlew

"""


def build_rust_cache_steps(enable_cache: bool, service_path: str, action_cache_ref: str) -> str:
    if not enable_cache:
        return ""
    target_path = "target" if service_path == "." else f"{service_path}/target"
    if service_path == ".":
        hash_args = "'Cargo.lock', '**/Cargo.lock'"
    else:
        hash_args = f"'Cargo.lock', '{service_path}/Cargo.lock'"
    return f"""      - name: Cache Cargo dependencies
        uses: {action_cache_ref}
        with:
          path: |
            ~/.cargo/registry/index
            ~/.cargo/registry/cache
            ~/.cargo/git/db
            {target_path}
          key: ${{{{ runner.os }}}}-cargo-${{{{ hashFiles({hash_args}) }}}}
          restore-keys: |
            ${{{{ runner.os }}}}-cargo-

"""


def build_security_scan_job(
    enable_security_scan: bool,
    security_scan_blocking: bool,
    runner: str,
    build_job_name: str,
    scan_ref: str,
    default_branch: str,
    default_shell: str,
    action_checkout_ref: str,
    action_trivy_ref: str,
    timeout_minutes: str,
) -> str:
    if not enable_security_scan:
        return ""
    blocking_literal = "true" if security_scan_blocking else "false"
    return f"""
  security-scan:
    runs-on: {runner}
    timeout-minutes: {timeout_minutes}
    needs: {build_job_name}
    permissions:
      contents: read
    defaults:
      run:
        shell: "{default_shell}"
    env:
      SECURITY_SCAN_BLOCKING: "{blocking_literal}"
      SECURITY_SCAN_DEFAULT_BRANCH: "{default_branch}"
    steps:
      - name: Checkout
        uses: {action_checkout_ref}

      - name: Decide security scan mode
        id: scan_mode
        run: |
          blocking="false"
          if [[ "$SECURITY_SCAN_BLOCKING" == "true" && "$GITHUB_EVENT_NAME" != "pull_request" ]]; then
            if [[ "$GITHUB_REF_NAME" == "$SECURITY_SCAN_DEFAULT_BRANCH" || "$GITHUB_REF_NAME" == release || "$GITHUB_REF_NAME" == release/* || "$GITHUB_REF_NAME" == release-* ]]; then
              blocking="true"
            fi
          fi
          if [[ "$blocking" == "true" ]]; then
            echo "mode=blocking" >> "$GITHUB_OUTPUT"
            echo "continue_on_error=false" >> "$GITHUB_OUTPUT"
            echo "exit_code=1" >> "$GITHUB_OUTPUT"
          else
            echo "mode=non-blocking" >> "$GITHUB_OUTPUT"
            echo "continue_on_error=true" >> "$GITHUB_OUTPUT"
            echo "exit_code=0" >> "$GITHUB_OUTPUT"
          fi

      - name: Explain security scan mode
        run: |
          echo "Security scan mode: ${{{{ steps.scan_mode.outputs.mode }}}}"

      - name: Run Trivy filesystem scan
        continue-on-error: ${{{{ steps.scan_mode.outputs.continue_on_error == 'true' }}}}
        uses: {action_trivy_ref}
        with:
          scan-type: fs
          scan-ref: {scan_ref}
          format: table
          exit-code: ${{{{ steps.scan_mode.outputs.exit_code }}}}
          ignore-unfixed: true
          severity: CRITICAL,HIGH
"""


def image_registry(repo_config: Dict[str, object]) -> str:
    return str(repo_config.get("image_registry", "ghcr.io/${{ github.repository_owner }}")).strip().rstrip("/")


def image_registry_host(registry: str) -> str:
    return registry.split("/", 1)[0].strip().lower()


def service_slug(service_path: str, fallback: str) -> str:
    raw = service_path if service_path != "." else fallback
    return normalize_name(raw.strip("./"), fallback)


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
    project_slug = normalize_name(project_root.name, "app")
    default_branches, test_branches = resolve_branches(repo_config, getattr(args, "test_branch", ""))
    runner = str(repo_config.get("runner", "ubuntu-latest"))
    test_environment = str(repo_config.get("test_environment", "test"))
    prod_environment = str(repo_config.get("prod_environment", "prod"))
    registry = image_registry(repo_config)
    enable_cache = bool_from_config(repo_config, "enable_cache", True)
    enable_security_scan = bool_from_config(repo_config, "enable_security_scan", True)
    security_scan_blocking = bool_from_config(repo_config, "security_scan_blocking", False)
    default_shell = str(repo_config.get("default_shell", SAFE_BASH_SHELL)).strip() or SAFE_BASH_SHELL
    job_timeout_minutes = str(repo_config.get("default_job_timeout_minutes", 20))
    deploy_timeout_minutes = str(repo_config.get("deploy_job_timeout_minutes", 30))
    test_healthcheck_url = str(repo_config.get("healthcheck_url_test", "")).strip()
    prod_healthcheck_url = str(repo_config.get("healthcheck_url_prod", "")).strip()
    healthcheck_timeout_seconds = str(repo_config.get("healthcheck_timeout_seconds", "40")).strip() or "40"
    rollback_on_failure = "true" if bool_from_config(repo_config, "rollback_on_failure", True) else "false"
    remote_image_retention = str(repo_config.get("remote_image_retention", 3))

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
        explicit_app_name = coalesce(args.app_name, str(repo_config.get("app_name", "")))
        if explicit_app_name:
            base_app_name = normalize_name(explicit_app_name, str(detected["app_name"]))
            app_name = join_name(base_app_name, slug) if multi_service else base_app_name
        elif current_service_path != ".":
            app_name = join_name(project_slug, slug)
        else:
            app_name = str(detected["app_name"])
        test_target = coalesce(args.test_target, str(repo_config.get("test_target", app_name)))
        prod_target = coalesce(args.prod_target, str(repo_config.get("prod_target", app_name)))

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
                "security_scan_blocking": security_scan_blocking,
                "default_shell": default_shell,
                "job_timeout_minutes": job_timeout_minutes,
                "deploy_timeout_minutes": deploy_timeout_minutes,
                "test_healthcheck_url": test_healthcheck_url,
                "prod_healthcheck_url": prod_healthcheck_url,
                "healthcheck_timeout_seconds": healthcheck_timeout_seconds,
                "rollback_on_failure": rollback_on_failure,
                "remote_image_retention": remote_image_retention,
                "repo_config": repo_config,
                "multi_service": multi_service,
            }
        )
    return specs


def build_replacements(spec: Dict[str, object], workflow_kind: str) -> Dict[str, str]:
    detected = spec["detected"]
    service_path = str(spec["service_path"])
    required_actions = ["actions/checkout"]
    if workflow_kind == "ci":
        project_type = str(spec["project_type"])
        if project_type == "go-service":
            required_actions.append("actions/setup-go")
        elif project_type == "node-service":
            required_actions.append("actions/setup-node")
        elif project_type == "python-service":
            required_actions.append("actions/setup-python")
        elif project_type == "java-service":
            required_actions.append("actions/setup-java")
        elif project_type == "rust-service":
            required_actions.append("dtolnay/rust-toolchain")
        if bool(spec["enable_cache"]) and project_type in {"go-service", "rust-service"}:
            required_actions.append("actions/cache")
        if bool(spec["enable_security_scan"]):
            required_actions.append("aquasecurity/trivy-action")
    elif str(spec["deploy_mode"]) == "docker-ssh":
        required_actions.append("webfactory/ssh-agent")
    elif str(spec["deploy_mode"]) == "docker-registry-only":
        required_actions.extend(["docker/setup-buildx-action", "docker/login-action", "docker/build-push-action"])
    action_replacements = build_action_replacements(dict(spec["repo_config"]), required_actions)
    go_cache_steps = build_go_cache_steps(bool(spec["enable_cache"]), action_replacements.get("ACTION_CACHE", ""))
    node_cache_block = build_node_cache_block(bool(spec["enable_cache"]), str(detected.get("package_manager") or "npm"), service_path)
    python_cache_block = build_python_cache_block(bool(spec["enable_cache"]), list(detected.get("python_dependency_files") or []), service_path)
    java_wrapper_step = build_java_wrapper_step(bool(detected.get("has_gradle_wrapper")))
    rust_cache_steps = build_rust_cache_steps(bool(spec["enable_cache"]), service_path, action_replacements.get("ACTION_CACHE", ""))
    build_job_name = "docker-build" if spec["project_type"] == "docker-service" else "test-and-build"
    security_scan_job = build_security_scan_job(
        bool(spec["enable_security_scan"]),
        bool(spec["security_scan_blocking"]),
        str(spec["runner"]),
        build_job_name,
        service_path,
        str(spec["default_branches"][0]),
        str(spec["default_shell"]),
        action_replacements["ACTION_CHECKOUT"],
        action_replacements.get("ACTION_TRIVY", ""),
        str(spec["job_timeout_minutes"]),
    )

    replacements = {
        "APP_NAME": str(spec["app_name"]),
        "TEST_TARGET": str(spec["test_target"]),
        "PROD_TARGET": str(spec["prod_target"]),
        "SERVICE_PATH": service_path,
        "DOCKER_CONTEXT": service_path,
        "RUNNER": str(spec["runner"]),
        "DEFAULT_SHELL": str(spec["default_shell"]),
        "JOB_TIMEOUT_MINUTES": str(spec["job_timeout_minutes"]),
        "DEPLOY_TIMEOUT_MINUTES": str(spec["deploy_timeout_minutes"]),
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
        "REMOTE_DEPLOY_SCRIPT_PATH": REMOTE_DEPLOY_SCRIPT_RELATIVE_PATH,
        "TEST_HEALTHCHECK_URL": str(spec["test_healthcheck_url"]),
        "PROD_HEALTHCHECK_URL": str(spec["prod_healthcheck_url"]),
        "HEALTHCHECK_TIMEOUT_SECONDS": str(spec["healthcheck_timeout_seconds"]),
        "ROLLBACK_ON_FAILURE": str(spec["rollback_on_failure"]),
        "REMOTE_IMAGE_RETENTION": str(spec["remote_image_retention"]),
        "GO_CACHE_STEPS": go_cache_steps,
        "NODE_CACHE_BLOCK": node_cache_block,
        "PYTHON_CACHE_BLOCK": python_cache_block,
        "JAVA_CACHE": str(detected.get("java_build_tool") or "maven"),
        "JAVA_WRAPPER_STEP": java_wrapper_step,
        "RUST_CACHE_STEPS": rust_cache_steps,
        "SECURITY_SCAN_JOB": security_scan_job,
        "TEST_COMMAND": str(detected["test_command"]),
        "BUILD_COMMAND": str(detected["build_command"]),
        "INSTALL_COMMAND": str(detected.get("install_command") or "npm ci"),
    }
    replacements.update(action_replacements)
    return replacements


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


def render_support_files(project_root: Path, specs: List[Dict[str, object]]) -> List[Path]:
    paths = support_file_paths(project_root, specs)
    if not paths:
        return []
    script_template = load_template(ASSETS_DIR / "shared" / "remote_deploy.sh.tmpl")
    script_path = paths[0]
    write_file(script_path, script_template)
    return [script_path]


def main() -> int:
    parser = argparse.ArgumentParser(description="Render GitHub Actions workflows from templates.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for a single monorepo service")
    parser.add_argument("--service-paths", default="", help="Comma-separated subdirectories for multi-service generation")
    parser.add_argument("--output-dir", default=".github/workflows", help="Workflow output directory")
    parser.add_argument(
        "--project-type",
        default="auto",
        help="go-service|node-service|python-service|java-service|rust-service|docker-service|auto",
    )
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
    support_files = render_support_files(project_root, specs)
    written_files.extend(str(path) for path in support_files)

    summary = {
        "project_root": str(project_root),
        "service_root": str(specs[0]["service_root"]) if len(specs) == 1 else None,
        "service_path": str(specs[0]["service_path"]) if len(specs) == 1 else None,
        "service_paths": [str(spec["service_path"]) for spec in specs],
        "output_dir": str(output_dir),
        "files": written_files,
        "support_files": [str(path) for path in support_files],
        "services": services,
        "required_secrets_reference": str(SKILL_DIR / "references" / "secrets-checklist.md"),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
