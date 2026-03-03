# 微信小程序云托管部署指引

适用于本项目（FastAPI + Uvicorn，容器化）。包含本地验证、镜像推送、GitHub Actions 部署和云托管端配置要点。

## 1. 前置条件
- 开通云托管（TCB）并创建环境，获得 `TCB_ENV_ID`、`TCB_REGION`。
- 在腾讯云访问管理获取 API 密钥：`TCB_SECRET_ID`、`TCB_SECRET_KEY`。
- 创建 TCR 个人/企业版实例并获得：`TCR_SERVER`、`TCR_NAMESPACE`、`TCR_USERNAME`、`TCR_PASSWORD`。
- 小程序 AppID/Secret（如需调用微信接口）：`WX_APPID`、`WX_APP_SECRET`。

## 2. 环境变量（.env / GitHub Secrets）
核心运行变量（云托管会自动注入 `PORT`）：
- `PORT`（可留空以使用平台注入）、`ROOT_PATH`（若网关配置了路径前缀时设置）
- `LOG_LEVEL`、`RATE_LIMIT_DEFAULT`、`RATE_LIMIT_EXPORT`、`UVICORN_WORKERS`
- `API_KEY`（如需接口鉴权）

云托管/TCR Secrets（在 GitHub → Settings → Secrets and variables → Actions 添加）：
```
TCB_ENV_ID, TCB_REGION, TCB_SECRET_ID, TCB_SECRET_KEY
TCR_SERVER, TCR_NAMESPACE, TCR_USERNAME, TCR_PASSWORD
LOG_LEVEL (可选), RATE_LIMIT_DEFAULT (可选), RATE_LIMIT_EXPORT (可选), ROOT_PATH (可选), UVICORN_WORKERS (可选)
WX_APPID (可选), WX_APP_SECRET (可选)
```

## 3. 本地验证
```bash
# 可选：本地运行（确保 Docker 已安装）
docker build -t mortgage-agent:test .
docker run --rm -p 8000:8000 mortgage-agent:test
# 验证健康检查
curl http://127.0.0.1:8000/health
```

## 4. GitHub Actions 部署流程
仓库已提供 `.github/workflows/deploy-wechat.yml`：
1) 登录 GitHub → Actions → 选择 **Deploy to WeChat Cloud Hosting** → Run workflow。
2) 可填写 `image_tag`（留空则使用当前 commit SHA）。
3) 工作流会：
   - 构建镜像并推送到 TCR（使用 TCR_* Secrets）。
   - 用 `cloudbaserc.json` 渲染部署配置（包含 `containerPort`、`envVariables`）。
   - 调用 `TencentCloudBase/cloudbase-action@v2` 发布到云托管。

## 5. cloudbaserc.json 说明
- `imageInfo.imageUrl`: 来自 TCR 的镜像地址，例如 `ccr.ccs.tencentyun.com/your-namespace/mortgage-agent:<tag>`
- `containerPort`: 8000（FastAPI 容器监听），云托管会将外部流量转发至该端口。
- `envVariables`: 会下发到容器内（包含 `PORT`, `ROOT_PATH` 等）。
- 扩缩容：默认 CPU=1、内存=2GiB，副本 0-2，按 CPU 60% 触发，可在文件或工作流中调整。

## 6. 云托管控制台检查项
- 发布后在云托管「版本管理」查看镜像版本、访问域名。
- 若使用路径前缀网关，确保前缀与 `ROOT_PATH` 一致；健康检查路径 `/health`。
- 日志：可在云托管日志服务查看容器 stdout/stderr。

## 7. 常见问题
- **无法访问 /404**：确认网关路径前缀与 `ROOT_PATH` 对齐；确认容器端口为 8000。
- **部署失败（权限/鉴权）**：检查 TCR_* 与 TCB_* Secrets 是否正确；TCR 实例区域需与 TCB 环境匹配或可互通。
- **导出/写文件失败**：云托管仅保证临时可写目录，输出已写入容器内 `/app/output`，建议改为对象存储（COS）持久化（如需可再扩展）。

## 8. 快速回滚
- 在 Actions 重新运行工作流并指定上一个可用的 `image_tag`（历史 commit SHA）。

## 9. 后续可选优化
- 接入 COS 存储导出文件；
- 配置自定义域名与 HTTPS；
- 使用更细粒度的自动扩缩容策略或定时弹性策略。

