#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import List

from render_workflow import read_repo_config, resolve_service_specs


def build_checklist(project_root: Path, service_paths: List[str], app_name: str, deploy_mode: str, test_branch: str) -> str:
    service_lines = "\n".join(f"  - `{service_path}`" for service_path in service_paths)
    lines = [
        "# GitHub CI/CD Setup Checklist",
        "",
        f"- 项目目录：`{project_root}`",
        f"- 服务数量：`{len(service_paths)}`",
        "- 服务路径：",
        service_lines,
        f"- 应用名称：`{app_name}`",
        f"- 部署策略：`{deploy_mode}`",
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
                "- `TEST_REMOTE_DIR`",
                "- `TEST_CONTAINER_NAME`",
                "- `TEST_DOCKER_RUN_ARGS`",
                "- `PROD_REMOTE_DIR`",
                "- `PROD_CONTAINER_NAME`",
                "- `PROD_DOCKER_RUN_ARGS`",
                "",
                "## 可选 Variables",
                "",
                "- `TEST_PORT`",
                "- `PROD_PORT`",
            ]
        )
    elif deploy_mode == "docker-registry-only":
        lines.extend(
            [
                "## 必填 Secrets",
                "",
                "- `REGISTRY_USERNAME`",
                "- `REGISTRY_PASSWORD`",
                "",
                "## 必填 Variables",
                "",
                "- 无（默认使用 repo config 里的 `image_registry`）",
                "",
                "## 可选 Variables",
                "",
                "- `IMAGE_REGISTRY`（覆盖 repo config 里的 registry 前缀，workflow 会自动转成小写）",
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
            "## 组织级推荐配置",
            "",
            "建议在 `.github/cicd-bootstrap.json` 里统一这些字段：",
            "",
            "- `default_branch` / `default_branches`",
            "- `test_branch` / `test_branches`",
            "- `deploy_strategy`",
            "- `service_path` / `service_paths`",
            "- `image_registry`",
            "- `runner`",
            "- `enable_security_scan`",
            "- `enable_cache`",
            "- `test_environment`",
            "- `prod_environment`",
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
    elif deploy_mode == "docker-registry-only":
        lines.extend(
            [
                "1. 先确认镜像仓库前缀是否正确，例如 `ghcr.io/acme-team`。",
                "2. 如果 registry 前缀放在 `IMAGE_REGISTRY` 变量里，workflow 会自动把前缀转成小写并复用对应 host 登录。",
                "3. 配置 `REGISTRY_USERNAME` 和 `REGISTRY_PASSWORD`。",
                "4. 推送到测试分支，确认测试镜像已经成功推送。",
                "5. 再手动触发生产 workflow，推送生产标签。",
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
            "- 如果 workflow 文件需要覆盖已有文件，请在执行 bootstrap 时加 `--force`。",
            "- 如果是 monorepo，建议优先使用 `--service-path` 或 `--service-paths`。",
            "- 如果是团队统一模板，优先把默认值写进 `.github/cicd-bootstrap.json`，减少每次手输参数。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a GitHub CI/CD setup checklist.")
    parser.add_argument("--project-root", default=".", help="Repository root")
    parser.add_argument("--service-path", default="", help="Subdirectory of project root for a single monorepo service")
    parser.add_argument("--service-paths", default="", help="Comma-separated subdirectories for multi-service generation")
    parser.add_argument("--output-file", default=".github/cicd-bootstrap-checklist.md", help="Checklist output file")
    parser.add_argument("--app-name", default="", help="Override app name")
    parser.add_argument("--deploy-mode", "--deploy-strategy", dest="deploy_mode", default="auto", help="ci-only|docker-ssh|docker-registry-only|auto")
    parser.add_argument("--test-branch", default="", help="Test branch name")
    parser.add_argument("--project-type", default="auto", help="go-service|node-service|docker-service|auto")
    parser.add_argument("--test-target", default="", help="Optional test deploy target label")
    parser.add_argument("--prod-target", default="", help="Optional production deploy target label")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    repo_config = read_repo_config(project_root)
    specs = resolve_service_specs(project_root, repo_config, args)

    service_paths = [str(spec["service_path"]) for spec in specs]
    app_name = str(specs[0]["app_name"]) if len(specs) == 1 else ", ".join(str(spec["app_name"]) for spec in specs)
    deploy_mode = str(specs[0]["deploy_mode"]) if len({str(spec["deploy_mode"]) for spec in specs}) == 1 else "mixed"
    test_branch = str(specs[0]["test_branches"][0]) if specs else "develop"
    content = build_checklist(project_root, service_paths, app_name, deploy_mode, test_branch)

    output_file = Path(args.output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    print(output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
