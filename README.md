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
- `docker-service`

部署模式：
- `docker-ssh`
- `docker-registry-only`
- `ci-only`

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
- 选择 `docker-ssh`、`docker-registry-only` 或 `ci-only`
- 生成 `ci.yml`
- 生成 `deploy-test.yml`
- 生成 `deploy-prod.yml`
- 生成 GitHub Secrets / Variables 清单
- 对输出做基础校验

## 直接运行脚本

如果你希望手动运行，不经过自然语言触发，可以直接执行脚本。

在 skill 根目录里：

```bash
python3 scripts/bootstrap_repo.py --project-root .
```

如果 skill 已安装到默认目录：

```bash
python3 ~/.codex/skills/github-cicd-bootstrap/scripts/bootstrap_repo.py --project-root .
```

## 常见用法

### 1. 普通单仓服务

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --app-name my-service \
  --force
```

### 2. Monorepo 子服务

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --service-path services/api \
  --app-name api-service \
  --force
```

### 3. Monorepo 批量生成

```bash
python3 scripts/bootstrap_repo.py \
  --project-root . \
  --service-paths services/api,services/web \
  --deploy-strategy docker-registry-only \
  --force
```

### 4. 只做识别，不生成文件

```bash
python3 scripts/detect_project.py --project-root .
```

如果仓库根目录识别不出来，它会返回候选服务目录。  
这时直接补：

```bash
python3 scripts/detect_project.py --project-root . --service-path services/api
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
  "runner": "ubuntu-latest",
  "enable_security_scan": true,
  "enable_cache": true,
  "test_environment": "test",
  "prod_environment": "prod"
}
```

有了这份文件后，可以直接跑：

```bash
python3 scripts/bootstrap_repo.py --project-root . --force
```

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
- 是否启用缓存
- GitHub environment 名称

这样同事只需要运行 bootstrap，不用每次再手敲一堆参数。

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
