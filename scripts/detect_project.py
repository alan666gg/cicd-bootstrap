#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional


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


def detect_test_command(root: Path, project_type: str, package_manager: Optional[str]) -> str:
    if project_type == "go-service":
        return "go test ./..."
    if project_type == "node-service":
        if package_manager == "pnpm":
            return "pnpm test --if-present"
        if package_manager == "yarn":
            return "yarn test --if-present"
        return "npm test --if-present"
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
    return "docker build -f Dockerfile ."


def detect_install_command(project_type: str, package_manager: Optional[str]) -> str:
    if project_type != "node-service":
        return ""
    if package_manager == "pnpm":
        return "pnpm install --frozen-lockfile"
    if package_manager == "yarn":
        return "yarn install --frozen-lockfile"
    return "npm ci"


def find_candidates(project_root: Path) -> List[str]:
    candidates = []
    ignore_names = {".git", ".github", "node_modules", "vendor", "__pycache__"}
    for child in sorted(project_root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in ignore_names:
            continue
        if (child / "go.mod").exists() or (child / "package.json").exists() or (child / "Dockerfile").exists():
            candidates.append(child.name)
    return candidates


def detect_project(root: Path) -> Dict[str, object]:
    has_go_mod = (root / "go.mod").exists()
    has_package_json = (root / "package.json").exists()
    has_dockerfile = (root / "Dockerfile").exists()

    if has_go_mod:
        project_type = "go-service"
    elif has_package_json:
        project_type = "node-service"
    elif has_dockerfile:
        project_type = "docker-service"
    else:
        project_type = "unknown"

    package_manager = detect_package_manager(root)

    if has_dockerfile:
        deploy_mode = "docker-ssh"
    else:
        deploy_mode = "ci-only"

    app_name = root.name.replace("_", "-")

    return {
        "project_type": project_type,
        "package_manager": package_manager,
        "has_dockerfile": has_dockerfile,
        "deploy_mode": deploy_mode,
        "app_name": app_name,
        "install_command": detect_install_command(project_type, package_manager),
        "test_command": detect_test_command(root, project_type, package_manager),
        "build_command": detect_build_command(root, project_type, package_manager),
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
