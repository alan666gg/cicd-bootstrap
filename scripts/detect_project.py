#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from naming import normalize_name


PYTHON_MARKERS = ("pyproject.toml", "requirements.txt")
JAVA_MAVEN_MARKER = "pom.xml"
JAVA_GRADLE_MARKERS = ("build.gradle", "build.gradle.kts", "gradlew")
RUST_MARKER = "Cargo.toml"


def detect_package_manager(root: Path) -> Optional[str]:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "package-lock.json").exists():
        return "npm"
    if (root / "package.json").exists():
        return "npm"
    return None


def detect_python_dependency_files(root: Path) -> List[str]:
    files = []
    for name in ("requirements.txt", "pyproject.toml", "poetry.lock", "uv.lock", "Pipfile.lock", "setup.py", "setup.cfg"):
        if (root / name).exists():
            files.append(name)
    return files


def detect_java_build_tool(root: Path) -> Optional[str]:
    if (root / JAVA_MAVEN_MARKER).exists():
        return "maven"
    if any((root / marker).exists() for marker in JAVA_GRADLE_MARKERS):
        return "gradle"
    return None


def has_gradle_wrapper(root: Path) -> bool:
    return (root / "gradlew").exists()


def detect_rust_binary_name(root: Path) -> str:
    cargo_toml = root / RUST_MARKER
    if cargo_toml.exists():
        content = cargo_toml.read_text(encoding="utf-8")
        match = re.search(r'^\s*name\s*=\s*"([^"]+)"', content, flags=re.MULTILINE)
        if match:
            return match.group(1)
    return normalize_name(root.name, "app")


def detect_test_command(root: Path, project_type: str, package_manager: Optional[str]) -> str:
    if project_type == "go-service":
        return "go test ./..."
    if project_type == "node-service":
        if package_manager == "pnpm":
            return "pnpm test --if-present"
        if package_manager == "yarn":
            return "yarn test --if-present"
        return "npm test --if-present"
    if project_type == "python-service":
        return "python -m pytest -q"
    if project_type == "java-service":
        if detect_java_build_tool(root) == "maven":
            return "mvn -B test"
        if has_gradle_wrapper(root):
            return "./gradlew test"
        return "gradle test"
    if project_type == "rust-service":
        return "cargo test --all"
    return "docker build -f Dockerfile ."


def detect_build_command(root: Path, project_type: str, package_manager: Optional[str]) -> str:
    if project_type == "go-service":
        return "go build ./..."
    if project_type == "node-service":
        if package_manager == "pnpm":
            return "pnpm build --if-present"
        if package_manager == "yarn":
            return "yarn build --if-present"
        return "npm run build --if-present"
    if project_type == "python-service":
        return "python -m compileall ."
    if project_type == "java-service":
        if detect_java_build_tool(root) == "maven":
            return "mvn -B -DskipTests package"
        if has_gradle_wrapper(root):
            return "./gradlew build -x test"
        return "gradle build -x test"
    if project_type == "rust-service":
        return "cargo build --release"
    return "docker build -f Dockerfile ."


def detect_install_command(root: Path, project_type: str, package_manager: Optional[str]) -> str:
    if project_type == "node-service":
        if package_manager == "pnpm":
            return "pnpm install --frozen-lockfile"
        if package_manager == "yarn":
            return "yarn install --frozen-lockfile"
        return "npm ci"
    if project_type == "python-service":
        commands = ["python -m pip install --upgrade pip"]
        if (root / "requirements.txt").exists():
            commands.append("python -m pip install -r requirements.txt")
        elif (root / "pyproject.toml").exists():
            commands.append("python -m pip install .")
        commands.append("python -m pip install pytest")
        return " && ".join(commands)
    return ""


def find_candidates(project_root: Path) -> List[str]:
    candidates = []
    ignore_names = {".git", ".github", "node_modules", "vendor", "__pycache__"}
    for child in sorted(project_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in ignore_names:
            continue
        if (
            (child / "go.mod").exists()
            or (child / "package.json").exists()
            or any((child / marker).exists() for marker in PYTHON_MARKERS)
            or (child / JAVA_MAVEN_MARKER).exists()
            or any((child / marker).exists() for marker in JAVA_GRADLE_MARKERS)
            or (child / RUST_MARKER).exists()
            or (child / "Dockerfile").exists()
        ):
            candidates.append(child.name)
    return candidates


def detect_project(root: Path) -> Dict[str, object]:
    has_go_mod = (root / "go.mod").exists()
    has_package_json = (root / "package.json").exists()
    has_python = any((root / marker).exists() for marker in PYTHON_MARKERS)
    java_build_tool = detect_java_build_tool(root)
    has_java = java_build_tool is not None
    has_rust = (root / RUST_MARKER).exists()
    has_dockerfile = (root / "Dockerfile").exists()

    if has_go_mod:
        project_type = "go-service"
    elif has_package_json:
        project_type = "node-service"
    elif has_python:
        project_type = "python-service"
    elif has_java:
        project_type = "java-service"
    elif has_rust:
        project_type = "rust-service"
    elif has_dockerfile:
        project_type = "docker-service"
    else:
        project_type = "unknown"

    package_manager = detect_package_manager(root)
    deploy_mode = "docker-ssh" if has_dockerfile else "ci-only"
    app_name = normalize_name(root.name, "app")

    return {
        "project_type": project_type,
        "package_manager": package_manager,
        "has_dockerfile": has_dockerfile,
        "deploy_mode": deploy_mode,
        "app_name": app_name,
        "install_command": detect_install_command(root, project_type, package_manager),
        "test_command": detect_test_command(root, project_type, package_manager),
        "build_command": detect_build_command(root, project_type, package_manager),
        "python_dependency_files": detect_python_dependency_files(root),
        "java_build_tool": java_build_tool,
        "has_gradle_wrapper": has_gradle_wrapper(root),
        "rust_binary_name": detect_rust_binary_name(root),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect repository shape for GitHub CI/CD generation.")
    parser.add_argument("--project-root", default=".", help="Path to the repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for monorepo service")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    if not project_root.exists():
        raise SystemExit(f"project root does not exist: {project_root}")

    service_root = (project_root / args.service_path).resolve() if args.service_path else project_root
    if not service_root.exists():
        raise SystemExit(f"service root does not exist: {service_root}")

    result = detect_project(service_root)
    result["project_root"] = str(project_root)
    result["service_root"] = str(service_root)
    result["service_path"] = args.service_path or "."
    result["candidates"] = []
    if result["project_type"] == "unknown" and not args.service_path:
        result["candidates"] = find_candidates(project_root)

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
