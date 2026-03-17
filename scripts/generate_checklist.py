#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import List, Optional

from render_workflow import read_repo_config, resolve_service_specs


def build_checklist(
    project_root: Path,
    service_paths: List[str],
    app_name: str,
    deploy_mode: str,
    test_branch: str,
    service_types: Optional[List[str]] = None,
    dependency_checks_test: Optional[List[str]] = None,
    dependency_checks_prod: Optional[List[str]] = None,
    dependency_checks_blocking: bool = False,
) -> str:
    service_lines = "\n".join(f"  - `{service_path}`" for service_path in service_paths)
    normalized_service_types = sorted({service_type for service_type in (service_types or []) if service_type})
    service_type_label = ", ".join(f"`{service_type}`" for service_type in normalized_service_types) if normalized_service_types else "`unknown`"
    lines = [
        "# GitHub CI/CD Setup Checklist",
        "",
        f"- 项目目录：`{project_root}`",
        f"- 服务数量：`{len(service_paths)}`",
        "- 服务路径：",
        service_lines,
        f"- 服务类型：{service_type_label}",
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
                "- `TEST_HEALTHCHECK_URL`",
                "- `PROD_HEALTHCHECK_URL`",
                "- `TEST_HEALTHCHECK_TIMEOUT_SECONDS`",
                "- `PROD_HEALTHCHECK_TIMEOUT_SECONDS`",
                "- `TEST_ROLLBACK_ON_FAILURE`",
                "- `PROD_ROLLBACK_ON_FAILURE`",
                "- `TEST_REMOTE_IMAGE_RETENTION`",
                "- `PROD_REMOTE_IMAGE_RETENTION`",
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
            "- `healthcheck_url_test` / `healthcheck_url_prod`",
            "- `healthcheck_timeout_seconds`",
            "- `rollback_on_failure`",
            "- `runner`",
            "- `default_shell`",
            "- `default_job_timeout_minutes`",
            "- `deploy_job_timeout_minutes`",
            "- `enable_security_scan`",
            "- `security_scan_blocking`",
            "- `action_pin_mode`",
            "- `allow_actions`",
            "- `pinned_actions`",
            "- `enable_cache`",
            "- `remote_image_retention`",
            "- `dependency_checks_test` / `dependency_checks_prod`",
            "- `dependency_checks_blocking`",
            "- `test_environment`",
            "- `prod_environment`",
            "",
            "## 语言相关提示",
            "",
        ]
    )

    if "python-service" in normalized_service_types:
        lines.extend(
            [
                "- Python：建议仓库至少保留 `requirements.txt` 或 `pyproject.toml`，没有 lock 文件时 `pip` 缓存命中率会偏低。",
                "- Python：CI 默认会补装 `pytest`，如果测试依赖比较特殊，优先写进项目依赖文件里。",
            ]
        )
    if "java-service" in normalized_service_types:
        lines.extend(
            [
                "- Java：Gradle 项目建议提交 `gradlew` 和 `gradle/wrapper`，模板会自动执行一次 `chmod +x ./gradlew`。",
                "- Java：Maven / Gradle 首次下载依赖会偏慢，wrapper 文件和缓存键不要随手删掉。",
            ]
        )
    if "rust-service" in normalized_service_types:
        lines.extend(
            [
                "- Rust：首次 `cargo build` 往往最慢，后续依赖缓存稳定后会明显改善。",
                "- Rust：建议提交 `Cargo.lock`，这样 CI 缓存和可重复构建都更稳。",
            ]
        )
    if not normalized_service_types:
        lines.append("- 混合语言仓库建议显式传 `--service-path` 或 `--service-paths`，避免根目录识别成 `unknown`。")

    lines.extend(
        [
            "",
            "## 依赖检查",
            "",
        ]
    )

    if dependency_checks_test or dependency_checks_prod:
        if dependency_checks_test:
            lines.append("- 测试环境依赖预检：")
            lines.extend(f"  - `{item}`" for item in dependency_checks_test)
        if dependency_checks_prod:
            lines.append("- 生产环境依赖预检：")
            lines.extend(f"  - `{item}`" for item in dependency_checks_prod)
        lines.append(f"- 依赖检查阻断模式：`{'true' if dependency_checks_blocking else 'false'}`")
        lines.append("- 目前支持：`tcp://host:port`、`http(s)://...`、`cmd:<shell command>`")
    else:
        lines.append("- 当前未配置依赖预检；如果服务依赖 Redis / MySQL / MQ，建议至少补一层提醒或检查。")

    lines.extend(
        [
            "",
            "## 使用说明",
            "",
        ]
    )

    if deploy_mode == "docker-ssh":
        lines.extend(
            [
                "1. 先把 Secrets 和 Variables 配齐。",
                "2. workflow 会自动创建远端目录，并上传镜像 tarball 和 `scripts/remote_deploy.sh`。",
                "3. 如果服务依赖 Redis / MySQL / MQ，优先在 repo config 里声明 `dependency_checks_test` / `dependency_checks_prod`。",
                "4. 如果保留最近 N 个镜像，优先在 repo config 里设置 `remote_image_retention`，或在 GitHub Variables 里覆盖环境值。",
                "5. 推送到测试分支，观察 `CI` 和 `Deploy Test` 工作流。",
                "6. 确认测试环境没问题后，再手动触发 `Deploy Prod`。",
            ]
        )
    elif deploy_mode == "docker-registry-only":
        lines.extend(
            [
                "1. 先确认镜像仓库前缀是否正确，例如 `ghcr.io/acme-team`。",
                "2. 如果 registry 前缀放在 `IMAGE_REGISTRY` 变量里，workflow 会自动把前缀转成小写并复用对应 host 登录。",
                "3. 配置 `REGISTRY_USERNAME` 和 `REGISTRY_PASSWORD`。",
                "4. 如果运行时依赖很多，至少在 repo config 里声明 `dependency_checks_test` / `dependency_checks_prod`，让 workflow 和 checklist 提醒团队。",
                "5. 如果变量很多，优先用 `scripts/apply_github_config.py --dry-run` 预览，再批量写入。",
                "6. 推送到测试分支，确认测试镜像已经成功推送。",
                "7. 再手动触发生产 workflow，推送生产标签。",
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
            "## 安全扫描默认策略",
            "",
            "- 默认开启安全扫描，但 bootstrap 模式下是 non-blocking。",
            "- PR 和 `develop` 这类测试分支默认只告警，不阻断流水线。",
            "- 如果把 `.github/cicd-bootstrap.json` 里的 `security_scan_blocking` 设为 `true`，推送到默认分支和 `release` / `release/*` 分支时会对 `HIGH` / `CRITICAL` 漏洞阻断。",
            "- `action_pin_mode` 默认为 `tag`；如果切到 `sha`，需要在 `pinned_actions` 里为实际用到的 actions 提供 commit SHA。",
            "",
            "## Docker-SSH 默认部署策略",
            "",
            "- workflow 会先远端 `mkdir -p`，避免目录不存在导致 `scp` 失败。",
            "- 远端切换逻辑统一走 `scripts/remote_deploy.sh`，便于后续维护。",
            "- 如果配置了 healthcheck URL，部署后会自动探活。",
            "- `rollback_on_failure` 默认开启，healthcheck 失败时会尝试回滚到旧镜像。",
            "- `remote_image_retention` 默认保留最近 3 个镜像，避免远端 Docker 主机无限堆积历史镜像。",
            "- 如果声明了 `dependency_checks_test` / `dependency_checks_prod`，docker-ssh workflow 会在远端切换前先做依赖预检。",
            "- `dependency_checks_blocking=false` 时只提醒不阻断；设成 `true` 后依赖不通会直接拦截部署。",
            "",
            "## GitHub 批量配置",
            "",
            "- `scripts/apply_github_config.py` 支持 `--dry-run`、`--mode skip|upsert`、变量和 secrets 批量写入。",
            "- 推荐先跑 dry-run，看清楚将要写入哪些 key，再执行真实写入。",
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
    parser.add_argument(
        "--project-type",
        default="auto",
        help="go-service|node-service|python-service|java-service|rust-service|docker-service|auto",
    )
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
    service_types = [str(spec["project_type"]) for spec in specs]
    content = build_checklist(
        project_root,
        service_paths,
        app_name,
        deploy_mode,
        test_branch,
        service_types,
        list(repo_config.get("dependency_checks_test", [])),
        list(repo_config.get("dependency_checks_prod", [])),
        bool(repo_config.get("dependency_checks_blocking", False)),
    )

    output_file = Path(args.output_file).resolve()
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    print(output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
