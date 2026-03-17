#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from detect_project import detect_project


def build_checklist(project_root: Path, app_name: str, deploy_mode: str, test_branch: str) -> str:
    lines = [
        "# GitHub CI/CD Setup Checklist",
        "",
        f"- 项目目录：`{project_root}`",
        f"- 应用名称：`{app_name}`",
        f"- 部署模式：`{deploy_mode}`",
        f"- 测试分支：`{test_branch}`",
        "",
    ]

    if deploy_mode == "docker-ssh":
        lines.extend(
            [
                "## 必填 Secrets",
                "",
                "- `TEST_SSH_KEY`",
                "- `PROD_SSH_KEY`",
                "",
                "## 必填 Variables",
                "",
                "- `TEST_HOST`",
                "- `TEST_USER`",
                "- `PROD_HOST`",
                "- `PROD_USER`",
            ]
        )
        lines.extend(
            [
                "- `TEST_REMOTE_DIR`",
                "- `TEST_CONTAINER_NAME`",
                "- `TEST_DOCKER_RUN_ARGS`",
                "- `PROD_REMOTE_DIR`",
                "- `PROD_CONTAINER_NAME`",
                "- `PROD_DOCKER_RUN_ARGS`",
            ]
        )
    else:
        lines.extend(
            [
                "## 必填 Secrets",
                "",
                "- 无",
                "",
                "## 必填 Variables",
                "",
                "- 无",
            ]
        )

    lines.extend(
        [
            "",
            "## 可选 Variables",
            "",
            "- `TEST_PORT`",
            "- `PROD_PORT`",
            "",
            "## 使用说明",
            "",
        ]
    )
    if deploy_mode == "docker-ssh":
        lines.extend(
            [
                "1. 先把 Secrets 和 Variables 配齐。",
                "2. 推送到测试分支，观察 `CI` 和 `Deploy Test` 工作流。",
                "3. 确认测试环境没问题后，再手动触发 `Deploy Prod`。",
            ]
        )
    else:
        lines.extend(
            [
                "1. 先验证 `CI` 工作流是否符合仓库当前需求。",
                "2. 推送到测试分支，观察 `CI` 和占位 `Deploy Test` 工作流。",
                "3. 等部署目标明确后，再把占位 deploy workflow 替换成真实发布流程。",
            ]
        )
    lines.extend(
        [
            "",
            "## 备注",
            "",
            "- 如果仓库还没有明确的发布目标，先保留 `ci-only` 模式即可。",
            "- 如果 workflow 文件需要覆盖已有文件，请在执行 bootstrap 时加 `--force`。",
        ]
    )
    return "\n".join(lines) + "\n"


def read_repo_config(project_root: Path):
    config_path = project_root / ".github" / "cicd-bootstrap.json"
    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a GitHub CI/CD setup checklist.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--output-file", default=".github/cicd-bootstrap-checklist.md", help="Checklist output file")
    parser.add_argument("--app-name", default="", help="Override app name")
    parser.add_argument("--deploy-mode", default="auto", help="tool-script|ghcr-ssh|auto")
    parser.add_argument("--test-branch", default="develop", help="Test branch name")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    detected = detect_project(project_root)
    repo_config = read_repo_config(project_root)
    deploy_mode = repo_config.get("deploy_mode", detected["deploy_mode"]) if args.deploy_mode == "auto" else args.deploy_mode
    app_name = args.app_name.strip() if args.app_name.strip() else str(repo_config.get("app_name", detected["app_name"]))
    test_branch = repo_config.get("test_branch", args.test_branch)

    content = build_checklist(project_root, app_name, deploy_mode, test_branch)

    output_file = Path(args.output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    print(output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
