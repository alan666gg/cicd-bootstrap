# GitHub CI/CD Bootstrap

`github-cicd-bootstrap` 是一个通用 skill，用来帮 AI 给仓库快速补齐 GitHub Actions CI/CD。

适合这些场景：
- 给一个新仓库搭 CI
- 给已有服务补测试环境 / 生产环境工作流
- 给 monorepo 的某个子服务单独生成 workflow
- 给团队统一一套可维护的 GitHub Actions 模板

当前支持：
- `go-service`
- `node-service`
- `python-service`
- `java-service`
- `rust-service`
- `docker-service`

部署模式：
- `docker-ssh`
- `docker-registry-only`
- `ci-only`

Dockerfile 生成：
- `go-service`
- `node-service`
- `python-service`
- `java-service`
- `rust-service`
- `static-web`

## 安装

这个仓库本身就是一个单独 skill。

优先试这个：

```bash
npx skills add https://github.com/alan666gg/cicd-bootstrap.git
```

如果你的环境要求显式指定 skill 名称，再用：

```bash
npx skills add https://github.com/alan666gg/cicd-bootstrap.git --skill github-cicd-bootstrap
```

安装完成后，重启你的 agent / Codex 会话。

## 让 AI 直接使用

安装后，可以直接对 AI 说：

- `帮我给这个仓库搭 GitHub CI/CD`
- `给这个 Go 服务补 GitHub Actions`
- `给这个 monorepo 里的 api 服务生成 workflow`
- `用 github-cicd-bootstrap 给这个项目补一套 CI/CD`

这个 skill 会自动做这些事：
- 识别项目类型
- 在需要时生成高性能 Dockerfile
- 选择 `docker-ssh`、`docker-registry-only` 或 `ci-only`
- 生成 `ci.yml`
- 生成 `deploy-test.yml`
- 生成 `deploy-prod.yml`
- 在 `docker-ssh` 模式下生成 `scripts/remote_deploy.sh`
- 生成 GitHub Secrets / Variables 清单
- 对输出做基础校验

## 30秒上手

最短命令：

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --generate-dockerfile \
  --deploy-strategy docker-registry-only \
  --force
```

如果 skill 已安装到默认目录：

```bash
python3 ~/.codex/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py \
  --project-root . \
  --generate-dockerfile \
  --deploy-strategy docker-registry-only \
  --force
```

## 5分钟落地

### 1. 生成 workflow / checklist / Dockerfile

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --generate-dockerfile \
  --deploy-strategy docker-registry-only \
  --force
```

### 2. 到 GitHub 配置 Secrets / Variables

最常见的是：
- `REGISTRY_USERNAME`
- `REGISTRY_PASSWORD`
- 可选 `IMAGE_REGISTRY`

如果 key 比较多，可以先 dry-run：

```bash
python3 scripts/apply_github_config.py \
  --project-root . \
  --var IMAGE_REGISTRY=ghcr.io/acme-team \
  --secret-env REGISTRY_USERNAME=REGISTRY_USERNAME \
  --secret-env REGISTRY_PASSWORD=REGISTRY_PASSWORD \
  --mode upsert \
  --dry-run
```

### 3. 提交并观察 Actions

```bash
git add .
git commit -m "chore: bootstrap ci/cd"
git push
```

看这几个 workflow：
- `CI`
- `Deploy Test`
- `Deploy Prod`

### 4. 单服务 / Monorepo 常用命令

普通单仓：

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --app-name my-service \
  --force
```

Monorepo 子服务：

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --service-path services/api \
  --app-name api-service \
  --force
```

多语言服务：

```bash
python3 scripts/bootstrap_repo.py --project-root . --service-path services/python-api --generate-dockerfile --force
python3 scripts/bootstrap_repo.py --project-root . --service-path services/java-api --generate-dockerfile --force
python3 scripts/bootstrap_repo.py --project-root . --service-path services/rust-worker --generate-dockerfile --force
```

Monorepo 批量：

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --service-paths services/api,services/web \
  --deploy-strategy docker-registry-only \
  --force
```

## 深度配置

### 1. 只生成高性能 Dockerfile

```bash
python3 scripts/generate_dockerfile.py \
  --project-root . \
  --service-path services/api
```

如果你想显式指定模板：

```bash
python3 scripts/generate_dockerfile.py \
  --project-root . \
  --dockerfile-kind static-web
```

也可以显式指定多语言模板：

```bash
python3 scripts/generate_dockerfile.py --project-root . --dockerfile-kind python-service
python3 scripts/generate_dockerfile.py --project-root . --dockerfile-kind java-service
python3 scripts/generate_dockerfile.py --project-root . --dockerfile-kind rust-service
```

### 2. 只做识别，不生成文件

```bash
python3 scripts/detect_project.py --project-root .
```

如果仓库根目录识别不出来，它会返回候选服务目录。  
这时直接补：

```bash
python3 scripts/detect_project.py --project-root . --service-path services/api
```

### 3. 校验 repo config / workflow / snapshots

```bash
python3 scripts/validate_repo_config.py --project-root .
python3 scripts/validate_workflow.py --workflow-dir .github/workflows
python3 scripts/smoke_test_templates.py
python3 scripts/verify_template_snapshots.py
```

## 输出内容

默认会生成到：

```text
.github/workflows/ci.yml
.github/workflows/deploy-test.yml
.github/workflows/deploy-prod.yml
.github/cicd-bootstrap-checklist.md
```

如果是批量模式，会生成：

```text
.github/workflows/ci-services-api.yml
.github/workflows/deploy-test-services-api.yml
.github/workflows/deploy-prod-services-api.yml
...
```

## 使用仓库配置文件

如果团队有固定规范，建议在仓库里放：

```text
.github/cicd-bootstrap.json
```

示例：

```json
{
  "app_name": "my-service",
  "deploy_strategy": "docker-registry-only",
  "service_paths": ["services/api", "services/worker"],
  "default_branch": "main",
  "test_branches": ["develop", "release/*"],
  "image_registry": "ghcr.io/acme-platform",
  "healthcheck_url_test": "http://127.0.0.1:8080/healthz",
  "healthcheck_url_prod": "http://127.0.0.1:8080/healthz",
  "healthcheck_timeout_seconds": 40,
  "rollback_on_failure": true,
  "runner": "ubuntu-latest",
  "enable_security_scan": true,
  "security_scan_blocking": false,
  "enable_cache": true,
  "test_environment": "test",
  "prod_environment": "prod"
}
```

有了这份文件后，可以直接跑：

```bash
python3 scripts/bootstrap_repo.py --project-root . --force
```

说明：
- `app_name` 和自动生成的 service slug 会统一归一化成 `lowercase + kebab-case`
- 例如 `sourceBinance` 会变成 `source-binance`
- 这样生成的 GHCR / Docker image name 会更稳，避免大小写导致推送失败
- `docker-registry-only` workflow 也会在运行时把 `image_registry` 或可选的 `IMAGE_REGISTRY` 变量自动转成小写，并按最终 host 登录镜像仓库
- monorepo 子服务如果没显式传 `app_name`，会默认生成 `repo-name + service-slug`，降低在 owner 级镜像仓库里撞名的概率
- 安全扫描默认开启，但 bootstrap 输出里默认是 non-blocking，避免 Trivy 下载波动把第一次接入 CI 的团队直接卡死
- 把 `security_scan_blocking` 设成 `true` 后，PR / develop 仍然只告警；默认分支和 `release` 分支才会对 `HIGH` / `CRITICAL` 问题阻断
- `action_pin_mode` 默认是 `tag`；切到 `sha` 后，需要在 `pinned_actions` 里为实际用到的 actions 填 commit SHA
- `allow_actions` 可以把生成出来的 workflow 限在团队批准的 action 白名单内
- workflow 默认 shell 现在是 `bash --noprofile --norc -euo pipefail {0}`
- `default_job_timeout_minutes` / `deploy_job_timeout_minutes` 可以统一治理超时策略
- `docker-ssh` workflow 会自动创建远端目录，并把切换逻辑下沉到 `scripts/remote_deploy.sh`
- 如果配置了 healthcheck URL，部署成功前会自动探活，失败时默认回滚到旧镜像
- `remote_image_retention` 默认保留最近 3 个镜像，避免远端历史镜像越积越多
- 如果服务依赖 Redis / MySQL / MQ，可以在 repo config 里声明 `dependency_checks_test` / `dependency_checks_prod`
- 支持 `tcp://host:port`、`http(s)://...`、`cmd:<shell command>` 三种依赖检查格式
- `dependency_checks_blocking=false` 时默认只提醒不阻断；切成 `true` 后依赖不通会直接阻止部署
- skill 仓库自己也带了 `.github/workflows/ci.yml`，会跑 smoke test 和 snapshot test

## deploy strategy 说明

### `docker-ssh`

适合已经有 `Dockerfile`、并且准备通过 SSH 在远端切容器的项目。

会生成：
- CI 工作流
- 测试环境部署工作流
- 生产环境部署工作流

### `docker-registry-only`

适合已经有 `Dockerfile`，但真正部署由 Kubernetes / Helm / ECS / Cloud Run / GitOps 平台处理的项目。

会生成：
- CI 工作流
- 测试镜像推送工作流
- 生产镜像推送工作流

### `ci-only`

适合还没定部署策略，或者当前只想先把 CI 搭起来的项目。

会生成：
- CI 工作流
- 占位的测试/生产部署工作流
- 引导团队后续补真实发布方式

## 组织级默认规范

如果你希望整个团队都走同一套约定，推荐把这些值放到 `.github/cicd-bootstrap.json`：

- 默认分支 / 测试分支
- 镜像仓库前缀
- runner 类型
- 是否启用安全扫描
- 是否只在主分支 / release 分支阻断安全扫描
- 是否启用缓存
- GitHub environment 名称

这样同事只需要运行 bootstrap，不用每次再手敲一堆参数。

## 语言相关提醒

- Python：建议至少保留 `requirements.txt` 或 `pyproject.toml`，没有 lock 文件时 `pip` cache miss 会更多。
- Java：Gradle 项目建议把 `gradlew` 和 `gradle/wrapper` 一起提交；模板会自动补一次 `chmod +x ./gradlew`。
- Rust：首次 `cargo build` 会明显更慢，后续依赖缓存热起来后会稳定很多。

## Smoke Test

仓库内置了一个最小 smoke test，用来验证多语言模板没有回退：

```bash
python3 scripts/smoke_test_templates.py
```

它会自动创建 Python / Java / Rust 单仓样例，以及一个混合语言 monorepo，然后执行：
- `detect_project.py`
- `bootstrap_repo.py`
- `validate_workflow.py`

## 自动生成高性能 Dockerfile

这版支持自动生成：

- Go 服务：多阶段构建、`go mod` / build cache、非 root 运行
- Node 服务：builder/runtime 分层、依赖裁剪、非 root 运行
- 静态前端：Node builder + Nginx runtime

同时会一起生成 `.dockerignore`，减少无效上下文上传。

可以通过 `.github/cicd-bootstrap.json` 统一这些值：

- `generate_dockerfile`
- `dockerfile_kind`
- `docker_build_dir`
- `docker_start_command`
- `binary_name`

## 默认安全基线

这版生成的 workflow 默认带：

- `permissions`
- `concurrency`
- `timeout-minutes`
- `environment`
- 可选安全扫描（Trivy）

校验阶段还会检查：

- YAML 结构
- 未替换占位符
- `permissions / concurrency / jobs` 是否存在
- deploy workflow 是否有 `environment`
- checklist 和 secrets / vars 引用是否一致
- 如果机器安装了 `actionlint`，会自动再跑一遍

## 适合给同事的最短指令

如果你只是想让同事直接拿来用，可以把这两句发给他：

```bash
npx skills add https://github.com/alan666gg/cicd-bootstrap.git
```

然后对 AI 说：

```text
帮我给这个仓库搭 GitHub CI/CD
```

如果是 monorepo：

```text
帮我给这个仓库的 services/api 搭 GitHub CI/CD
```

如果要一次给多个服务生成：

```text
帮我给这个仓库的 services/api 和 services/web 一起搭 GitHub CI/CD
```
