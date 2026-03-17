#!/usr/bin/env python3
import argparse
import json
import shlex
from pathlib import Path
from typing import Dict, List, Tuple

from detect_project import detect_project
from render_workflow import parse_service_paths, read_repo_config


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
DOCKERFILE_ASSETS_DIR = SKILL_DIR / "assets" / "dockerfiles"


def load_template(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def normalize(value, fallback: str) -> str:
    return value.strip() if value and value.strip() else fallback


def bool_from_config(repo_config: Dict[str, object], key: str, default: bool) -> bool:
    value = repo_config.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def read_package_json(service_root: Path) -> Dict[str, object]:
    package_json = service_root / "package.json"
    if not package_json.exists():
        return {}
    return json.loads(package_json.read_text(encoding="utf-8"))


def package_manager_prefix(package_manager: str) -> str:
    if package_manager == "pnpm":
        return "pnpm"
    if package_manager == "yarn":
        return "yarn"
    return "npm"


def detect_build_dir(service_root: Path, package_json: Dict[str, object], configured: str) -> str:
    if configured.strip():
        return configured.strip()
    deps = {}
    deps.update(package_json.get("dependencies") or {})
    deps.update(package_json.get("devDependencies") or {})
    if "react-scripts" in deps:
        return "build"
    return "dist"


def infer_dockerfile_kind(
    service_root: Path,
    detected: Dict[str, object],
    package_json: Dict[str, object],
    configured_kind: str,
    cli_kind: str,
) -> str:
    if cli_kind != "auto":
        return cli_kind
    if configured_kind and configured_kind != "auto":
        return configured_kind
    project_type = str(detected["project_type"])
    if project_type == "go-service":
        return "go-service"
    if project_type == "node-service":
        scripts = package_json.get("scripts") or {}
        deps = {}
        deps.update(package_json.get("dependencies") or {})
        deps.update(package_json.get("devDependencies") or {})
        frontend_markers = {
            "vite",
            "react-scripts",
            "astro",
            "parcel",
            "@angular/cli",
            "@sveltejs/kit",
        }
        if "build" in scripts and ("start" not in scripts) and any(marker in deps for marker in frontend_markers):
            return "static-web"
        return "node-service"
    return "docker-service"


def detect_start_command(service_root: Path, package_manager: str, package_json: Dict[str, object], configured: str) -> str:
    if configured.strip():
        return json.dumps(shlex.split(configured.strip()))
    scripts = package_json.get("scripts") or {}
    pm = package_manager_prefix(package_manager)
    if "start" in scripts:
        if pm == "npm":
            return json.dumps(["npm", "run", "start"])
        return json.dumps([pm, "start"])
    if "serve" in scripts:
        if pm == "npm":
            return json.dumps(["npm", "run", "serve"])
        return json.dumps([pm, "serve"])
    for candidate in ("server.js", "app.js", "index.js"):
        if (service_root / candidate).exists():
            return json.dumps(["node", candidate])
    return json.dumps(["npm", "run", "start"])


def package_copy_files(service_root: Path, package_manager: str) -> str:
    files = ["package.json"]
    if package_manager == "pnpm" and (service_root / "pnpm-lock.yaml").exists():
        files.append("pnpm-lock.yaml")
    elif package_manager == "yarn" and (service_root / "yarn.lock").exists():
        files.append("yarn.lock")
    elif (service_root / "package-lock.json").exists():
        files.append("package-lock.json")
    elif (service_root / "npm-shrinkwrap.json").exists():
        files.append("npm-shrinkwrap.json")
    return " ".join(files)


def install_command(service_root: Path, package_manager: str) -> str:
    if package_manager == "pnpm":
        return "corepack enable && pnpm install --frozen-lockfile"
    if package_manager == "yarn":
        return "corepack enable && yarn install --frozen-lockfile"
    if (service_root / "package-lock.json").exists() or (service_root / "npm-shrinkwrap.json").exists():
        return "npm ci"
    return "npm install"


def prune_command(package_manager: str) -> str:
    if package_manager == "pnpm":
        return "pnpm prune --prod && pnpm store prune || true"
    if package_manager == "yarn":
        return "yarn install --production --frozen-lockfile && yarn cache clean || true"
    return "npm prune --omit=dev && npm cache clean --force"


def build_command(detected: Dict[str, object]) -> str:
    return str(detected.get("build_command") or "npm run build --if-present")


def go_sum_copy(service_root: Path) -> str:
    return "COPY go.sum ./\n" if (service_root / "go.sum").exists() else ""


def dockerignore_template_path(kind: str) -> Path:
    if kind == "go-service":
        return DOCKERFILE_ASSETS_DIR / "go.dockerignore.tmpl"
    if kind == "static-web":
        return DOCKERFILE_ASSETS_DIR / "static-web.dockerignore.tmpl"
    return DOCKERFILE_ASSETS_DIR / "node.dockerignore.tmpl"


def dockerfile_template_path(kind: str) -> Path:
    if kind == "go-service":
        return DOCKERFILE_ASSETS_DIR / "go.Dockerfile.tmpl"
    if kind == "node-service":
        return DOCKERFILE_ASSETS_DIR / "node.Dockerfile.tmpl"
    if kind == "static-web":
        return DOCKERFILE_ASSETS_DIR / "static-web.Dockerfile.tmpl"
    raise ValueError(f"unsupported dockerfile kind: {kind}")


def render_template(template: str, replacements: Dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"__{key}__", value)
    return rendered


def generate_for_service(
    service_root: Path,
    service_path: str,
    repo_config: Dict[str, object],
    args,
) -> Dict[str, object]:
    detected = detect_project(service_root)
    package_json = read_package_json(service_root)
    package_manager = str(detected.get("package_manager") or "npm")
    kind = infer_dockerfile_kind(
        service_root,
        detected,
        package_json,
        str(repo_config.get("dockerfile_kind", "auto")),
        args.dockerfile_kind,
    )
    if kind == "docker-service":
        raise SystemExit(f"cannot infer Dockerfile template for {service_path}; choose --dockerfile-kind explicitly")

    dockerfile_path = service_root / "Dockerfile"
    dockerignore_path = service_root / ".dockerignore"
    dockerfile_exists = dockerfile_path.exists()
    dockerignore_exists = dockerignore_path.exists()
    should_generate = not dockerfile_exists or args.overwrite_dockerfile
    should_generate_dockerignore = (not dockerignore_exists) or args.overwrite_dockerfile
    if should_generate:
        replacements = {
            "BINARY_NAME": normalize(args.binary_name, str(repo_config.get("binary_name", service_root.name.replace("-", "_")))),
            "GO_SUM_COPY": go_sum_copy(service_root),
            "PACKAGE_FILES": package_copy_files(service_root, package_manager),
            "INSTALL_COMMAND": install_command(service_root, package_manager),
            "BUILD_COMMAND": build_command(detected),
            "PRUNE_COMMAND": prune_command(package_manager),
            "START_COMMAND": detect_start_command(service_root, package_manager, package_json, str(repo_config.get("docker_start_command", args.start_command))),
            "BUILD_DIR": detect_build_dir(service_root, package_json, str(repo_config.get("docker_build_dir", args.build_dir))),
        }
        dockerfile_template = load_template(dockerfile_template_path(kind))
        write_file(dockerfile_path, render_template(dockerfile_template, replacements))
        if args.generate_dockerignore and should_generate_dockerignore:
            write_file(dockerignore_path, load_template(dockerignore_template_path(kind)))

    return {
        "service_path": service_path,
        "service_root": str(service_root),
        "dockerfile_kind": kind,
        "dockerfile_path": str(dockerfile_path),
        "dockerfile_generated": should_generate,
        "dockerfile_overwritten": dockerfile_exists and args.overwrite_dockerfile,
        "dockerignore_path": str(dockerignore_path),
        "dockerignore_generated": args.generate_dockerignore and should_generate_dockerignore,
    }


def generate_service_dockerfiles(project_root: Path, repo_config: Dict[str, object], args) -> List[Dict[str, object]]:
    service_paths = parse_service_paths(args.service_path, getattr(args, "service_paths", ""), repo_config)
    generated = []
    for service_path in service_paths:
        service_root = (project_root / service_path).resolve() if service_path != "." else project_root
        generated.append(generate_for_service(service_root, service_path, repo_config, args))
    return generated


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate high-performance Dockerfiles for supported project types.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for a single monorepo service")
    parser.add_argument("--service-paths", default="", help="Comma-separated subdirectories for multi-service generation")
    parser.add_argument("--dockerfile-kind", default="auto", help="auto|go-service|node-service|static-web")
    parser.add_argument("--binary-name", default="", help="Go binary name override")
    parser.add_argument("--start-command", default="", help="Node start command override, for example 'npm run start'")
    parser.add_argument("--build-dir", default="", help="Static-web build output directory override")
    parser.add_argument("--overwrite-dockerfile", action="store_true", help="Overwrite an existing Dockerfile")
    parser.add_argument("--no-dockerignore", action="store_true", help="Skip generating .dockerignore")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    repo_config = read_repo_config(project_root)
    args.generate_dockerignore = not args.no_dockerignore
    results = generate_service_dockerfiles(project_root, repo_config, args)
    print(json.dumps({"project_root": str(project_root), "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
