#!/usr/bin/env python3
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_json(args: List[str]) -> Dict[str, object]:
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(args)}\n{proc.stderr}\n{proc.stdout}")
    return json.loads(proc.stdout)


def create_python_project(root: Path) -> None:
    write_file(
        root / "pyproject.toml",
        """[project]
name = "python-smoke"
version = "0.1.0"
requires-python = ">=3.12"
""",
    )
    write_file(root / "main.py", "print('python smoke')\n")
    write_file(root / "tests" / "test_smoke.py", "def test_smoke():\n    assert True\n")


def create_go_project(root: Path) -> None:
    write_file(
        root / "go.mod",
        """module github.com/example/go-smoke

go 1.22
""",
    )
    write_file(
        root / "main.go",
        """package main

import "fmt"

func main() {
    fmt.Println("go smoke")
}
""",
    )


def create_node_project(root: Path) -> None:
    write_file(
        root / "package.json",
        """{
  "name": "node-smoke",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "test": "node -e \\"console.log('node smoke test')\\"",
    "build": "node -e \\"console.log('node smoke build')\\"",
    "start": "node index.js"
  }
}
""",
    )
    write_file(root / "index.js", "console.log('node smoke')\n")


def create_java_project(root: Path) -> None:
    write_file(
        root / "pom.xml",
        """<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>java-smoke</artifactId>
  <version>0.0.1</version>
  <properties>
    <maven.compiler.source>21</maven.compiler.source>
    <maven.compiler.target>21</maven.compiler.target>
  </properties>
</project>
""",
    )
    write_file(
        root / "src" / "main" / "java" / "com" / "example" / "App.java",
        """package com.example;

public class App {
    public static void main(String[] args) {
        System.out.println("java smoke");
    }
}
""",
    )
    write_file(
        root / "src" / "test" / "java" / "com" / "example" / "AppTest.java",
        """package com.example;

public class AppTest {
}
""",
    )


def create_rust_project(root: Path) -> None:
    write_file(
        root / "Cargo.toml",
        """[package]
name = "rust-smoke"
version = "0.1.0"
edition = "2021"
""",
    )
    write_file(root / "src" / "main.rs", 'fn main() { println!("rust smoke"); }\n')


def detect_project_type(project_root: Path, service_path: str = "") -> str:
    args = ["python3", str(SCRIPT_DIR / "detect_project.py"), "--project-root", str(project_root)]
    if service_path:
        args.extend(["--service-path", service_path])
    result = run_json(args)
    return str(result["project_type"])


def bootstrap_and_validate(project_root: Path, service_paths: str = "", deploy_mode: str = "docker-registry-only") -> Dict[str, object]:
    bootstrap_args = [
        "python3",
        str(SCRIPT_DIR / "bootstrap_repo.py"),
        "--project-root",
        str(project_root),
        "--deploy-mode",
        deploy_mode,
        "--generate-dockerfile",
        "--force",
    ]
    if service_paths:
        bootstrap_args.extend(["--service-paths", service_paths])
    bootstrap_result = run_json(bootstrap_args)

    validate_args = [
        "python3",
        str(SCRIPT_DIR / "validate_workflow.py"),
        "--workflow-dir",
        str(project_root / ".github" / "workflows"),
        "--checklist-file",
        str(project_root / ".github" / "cicd-bootstrap-checklist.md"),
    ]
    validate_result = run_json(validate_args)
    return {"bootstrap": bootstrap_result, "validate": validate_result}


def assert_contains(path: Path, expected: List[str]) -> None:
    content = path.read_text(encoding="utf-8")
    for item in expected:
        if item not in content:
            raise AssertionError(f"{path} missing expected text: {item}")


def assert_security_scan_block_style(path: Path) -> None:
    assert_contains(
        path,
        [
            "- name: Explain security scan mode",
            "run: |",
            'echo "Security scan mode: ${{ steps.scan_mode.outputs.mode }}"',
        ],
    )


def main() -> int:
    temp_root = Path(tempfile.mkdtemp(prefix="github-cicd-bootstrap-smoke-"))
    results: List[Dict[str, object]] = []
    failures: List[str] = []

    try:
        single_projects = [
            ("go", "go-service", create_go_project),
            ("node", "node-service", create_node_project),
            ("python", "python-service", create_python_project),
            ("java", "java-service", create_java_project),
            ("rust", "rust-service", create_rust_project),
        ]

        for name, expected_type, creator in single_projects:
            project_root = temp_root / name
            creator(project_root)
            detected_type = detect_project_type(project_root)
            if detected_type != expected_type:
                raise AssertionError(f"{name}: expected {expected_type}, got {detected_type}")
            smoke = bootstrap_and_validate(project_root)
            assert_contains(
                project_root / ".github" / "cicd-bootstrap-checklist.md",
                ["REGISTRY_USERNAME", "REGISTRY_PASSWORD", "IMAGE_REGISTRY"],
            )
            assert_security_scan_block_style(project_root / ".github" / "workflows" / "ci.yml")
            results.append(
                {
                    "scenario": name,
                    "detected_type": detected_type,
                    "workflow_files": sorted(Path(project_root / ".github" / "workflows").glob("*.yml")),
                    "errors": smoke["validate"]["results"],
                }
            )

        monorepo_root = temp_root / "monorepo"
        create_python_project(monorepo_root / "services" / "api")
        create_java_project(monorepo_root / "services" / "billing")
        create_rust_project(monorepo_root / "services" / "worker")

        monorepo_specs = {
            "services/api": "python-service",
            "services/billing": "java-service",
            "services/worker": "rust-service",
        }
        for service_path, expected_type in monorepo_specs.items():
            detected_type = detect_project_type(monorepo_root, service_path)
            if detected_type != expected_type:
                raise AssertionError(f"{service_path}: expected {expected_type}, got {detected_type}")

        monorepo_smoke = bootstrap_and_validate(monorepo_root, "services/api,services/billing,services/worker")
        workflow_names = sorted(path.name for path in (monorepo_root / ".github" / "workflows").glob("*.yml"))
        if len(workflow_names) < 9:
            raise AssertionError(f"monorepo: expected at least 9 workflow files, got {len(workflow_names)}")
        assert_contains(
            monorepo_root / ".github" / "cicd-bootstrap-checklist.md",
            ["python-service", "java-service", "rust-service", "REGISTRY_USERNAME", "REGISTRY_PASSWORD"],
        )
        assert_security_scan_block_style(monorepo_root / ".github" / "workflows" / "ci-services-api.yml")
        results.append(
            {
                "scenario": "monorepo-mixed",
                "detected_type": monorepo_specs,
                "workflow_files": workflow_names,
                "errors": monorepo_smoke["validate"]["results"],
            }
        )

        dependency_root = temp_root / "dependency-checks"
        create_go_project(dependency_root)
        write_file(
            dependency_root / ".github" / "cicd-bootstrap.json",
            json.dumps(
                {
                    "deploy_strategy": "docker-ssh",
                    "dependency_checks_test": [
                        "tcp://127.0.0.1:6379",
                        "cmd:docker ps --format '{{.Names}}' | grep -q '^redis$'",
                    ],
                    "dependency_checks_prod": [
                        "tcp://10.0.0.12:6379",
                        "http://10.0.0.20:8080/readyz",
                    ],
                    "dependency_checks_blocking": False,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
        )
        dependency_smoke = bootstrap_and_validate(dependency_root, deploy_mode="auto")
        assert_contains(
            dependency_root / ".github" / "workflows" / "deploy-test.yml",
            [
                "Upload dependency check script",
                "Upload dependency check definitions",
                "Check runtime dependencies",
                "dependency_checks.txt",
            ],
        )
        assert_contains(
            dependency_root / ".github" / "cicd-bootstrap-checklist.md",
            ["dependency_checks_test", "tcp://127.0.0.1:6379", "dependency_checks_blocking"],
        )
        support_files = dependency_smoke["bootstrap"].get("support_files") or []
        if not any(str(path).endswith("scripts/check_dependencies.sh") for path in support_files):
            raise AssertionError("dependency-checks: expected generated scripts/check_dependencies.sh support file")
        results.append(
            {
                "scenario": "dependency-checks",
                "detected_type": "go-service",
                "workflow_files": sorted(path.name for path in (dependency_root / ".github" / "workflows").glob("*.yml")),
                "errors": dependency_smoke["validate"]["results"],
            }
        )
    except Exception as exc:
        failures.append(str(exc))

    output = {
        "temp_root": str(temp_root),
        "pass": not failures,
        "results": [
            {
                **result,
                "workflow_files": [str(path) for path in result["workflow_files"]] if isinstance(result.get("workflow_files"), list) else result.get("workflow_files"),
            }
            for result in results
        ],
        "failures": failures,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))

    if failures:
        return 1

    shutil.rmtree(temp_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
