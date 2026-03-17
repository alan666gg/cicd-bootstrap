#!/usr/bin/env python3
import argparse
import json
import shlex
from pathlib import Path
from typing import Dict, List

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
    if project_type == "python-service":
        return "python-service"
    if project_type == "java-service":
        return "java-service"
    if project_type == "rust-service":
        return "rust-service"
    return "docker-service"


def detect_start_command(
    service_root: Path,
    detected: Dict[str, object],
    package_manager: str,
    package_json: Dict[str, object],
    configured: str,
) -> str:
    if configured.strip():
        return json.dumps(shlex.split(configured.strip()))
    project_type = str(detected.get("project_type") or "")
    if project_type == "python-service":
        for candidate in ("main.py", "app.py", "run.py", "src/main.py"):
            if (service_root / candidate).exists():
                return json.dumps(["python", candidate])
        module_name = normalize(str(detected.get("app_name") or service_root.name), "app").replace("-", "_")
        return json.dumps(["python", "-m", module_name])
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


def python_package_files(detected: Dict[str, object]) -> str:
    files = [str(name) for name in detected.get("python_dependency_files") or []]
    if not files:
        return "requirements.txt"
    return " ".join(files)


def python_install_command(detected: Dict[str, object]) -> str:
    commands = [
        "python -m venv /opt/venv",
        "/opt/venv/bin/pip install --upgrade pip",
    ]
    if "requirements.txt" in set(detected.get("python_dependency_files") or []):
        commands.append("/opt/venv/bin/pip install -r requirements.txt")
    return " && ".join(commands)


def python_post_install_command(detected: Dict[str, object]) -> str:
    if "pyproject.toml" in set(detected.get("python_dependency_files") or []):
        return "/opt/venv/bin/pip install ."
    return "true"


def java_build_tool(detected: Dict[str, object]) -> str:
    return str(detected.get("java_build_tool") or "maven")


def java_builder_image(detected: Dict[str, object]) -> str:
    if java_build_tool(detected) == "gradle":
        return "gradle:8.11-jdk21"
    return "maven:3.9.9-eclipse-temurin-21"


def java_package_files(service_root: Path, detected: Dict[str, object]) -> str:
    files: List[str] = []
    build_tool = java_build_tool(detected)
    if build_tool == "maven":
        if (service_root / "pom.xml").exists():
            files.append("pom.xml")
        if (service_root / ".mvn").exists():
            files.append(".mvn")
        if (service_root / "mvnw").exists():
            files.append("mvnw")
    else:
        for name in ("build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts", "gradle.properties", "gradlew"):
            if (service_root / name).exists():
                files.append(name)
        if (service_root / "gradle").exists():
            files.append("gradle")
    return " ".join(files) or "."


def java_prepare_command(service_root: Path, detected: Dict[str, object]) -> str:
    build_tool = java_build_tool(detected)
    if build_tool == "gradle":
        if (service_root / "gradlew").exists():
            return "chmod +x ./gradlew && ./gradlew help --no-daemon || true"
        return "gradle help --no-daemon || true"
    return "mvn -B -q -DskipTests dependency:go-offline || true"


def java_artifact_command(detected: Dict[str, object]) -> str:
    artifact_dir = "build/libs" if java_build_tool(detected) == "gradle" else "target"
    return (
        "set -eux; "
        f"artifact=$(find {artifact_dir} -maxdepth 1 -type f -name '*.jar' "
        "! -name '*-sources.jar' ! -name '*-javadoc.jar' | head -n 1); "
        'test -n "$artifact"; cp "$artifact" /tmp/app.jar'
    )


def rust_manifest_files(service_root: Path) -> str:
    files = ["Cargo.toml"]
    if (service_root / "Cargo.lock").exists():
        files.append("Cargo.lock")
    return " ".join(files)


def rust_binary_name(detected: Dict[str, object], service_root: Path, configured: str) -> str:
    if configured.strip():
        return configured.strip()
    return normalize(str(detected.get("rust_binary_name") or service_root.name), service_root.name)


def go_sum_copy(service_root: Path) -> str:
    return "COPY go.sum ./\n" if (service_root / "go.sum").exists() else ""


def dockerignore_template_path(kind: str) -> Path:
    if kind == "go-service":
        return DOCKERFILE_ASSETS_DIR / "go.dockerignore.tmpl"
    if kind == "python-service":
        return DOCKERFILE_ASSETS_DIR / "python-service" / "dockerignore.tmpl"
    if kind == "java-service":
        return DOCKERFILE_ASSETS_DIR / "java-service" / "dockerignore.tmpl"
    if kind == "rust-service":
        return DOCKERFILE_ASSETS_DIR / "rust-service" / "dockerignore.tmpl"
    if kind == "static-web":
        return DOCKERFILE_ASSETS_DIR / "static-web.dockerignore.tmpl"
    return DOCKERFILE_ASSETS_DIR / "node.dockerignore.tmpl"


def dockerfile_template_path(kind: str) -> Path:
    if kind == "go-service":
        return DOCKERFILE_ASSETS_DIR / "go.Dockerfile.tmpl"
    if kind == "node-service":
        return DOCKERFILE_ASSETS_DIR / "node.Dockerfile.tmpl"
    if kind == "python-service":
        return DOCKERFILE_ASSETS_DIR / "python-service" / "Dockerfile.tmpl"
    if kind == "java-service":
        return DOCKERFILE_ASSETS_DIR / "java-service" / "Dockerfile.tmpl"
    if kind == "rust-service":
        return DOCKERFILE_ASSETS_DIR / "rust-service" / "Dockerfile.tmpl"
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
            "START_COMMAND": detect_start_command(
                service_root,
                detected,
                package_manager,
                package_json,
                str(repo_config.get("docker_start_command", args.start_command)),
            ),
            "BUILD_DIR": detect_build_dir(service_root, package_json, str(repo_config.get("docker_build_dir", args.build_dir))),
            "PYTHON_PACKAGE_FILES": python_package_files(detected),
            "PYTHON_INSTALL_COMMAND": python_install_command(detected),
            "PYTHON_POST_INSTALL_COMMAND": python_post_install_command(detected),
            "PYTHON_START_COMMAND": detect_start_command(
                service_root,
                detected,
                package_manager,
                package_json,
                str(repo_config.get("docker_start_command", args.start_command)),
            ),
            "JAVA_BUILDER_IMAGE": java_builder_image(detected),
            "JAVA_PACKAGE_FILES": java_package_files(service_root, detected),
            "JAVA_PREPARE_COMMAND": java_prepare_command(service_root, detected),
            "JAVA_BUILD_COMMAND": build_command(detected),
            "JAVA_ARTIFACT_COMMAND": java_artifact_command(detected),
            "RUST_MANIFEST_FILES": rust_manifest_files(service_root),
            "RUST_BUILD_COMMAND": build_command(detected),
            "RUST_BINARY_NAME": rust_binary_name(
                detected,
                service_root,
                str(repo_config.get("binary_name", args.binary_name)),
            ),
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
    parser.add_argument(
        "--dockerfile-kind",
        default="auto",
        help="auto|go-service|node-service|python-service|java-service|rust-service|static-web",
    )
    parser.add_argument("--binary-name", default="", help="Go or Rust binary name override")
    parser.add_argument("--start-command", default="", help="Runtime command override, for example 'npm run start' or 'python main.py'")
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
