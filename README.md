# 电商分析 Agent

Vue 3 前端 + FastAPI 后端的电商分析演示项目，包含登录、商品/订单/评价管理、自然语言查询和语义搜索功能。

## 本地开发

1. 在 `backend/` 创建 `.env`，填写数据库、JWT 和模型服务配置（字段见 `.env.production.example`）。
2. 安装后端依赖并从 `backend/` 启动：`uvicorn app.main:app --reload`。
3. 在 `frontend/` 执行 `npm ci`，再运行 `npm run dev`。

## Docker 部署

需要一台安装 Docker Engine 与 Docker Compose 的 Linux 主机，以及可从该主机访问的 MySQL 数据库、模型服务 API Key 和域名。生产入口由 Nginx 提供，`/api` 和 `/uploads` 转发到 FastAPI。

1. 将项目复制到服务器，在项目根目录执行：

   ```sh
   cp .env.production.example .env.production
   ```

2. 编辑 `.env.production`：配置数据库 URL、只读查询账号、JWT 随机密钥、LLM 凭证，以及 `CORS_ORIGINS` 的实际 HTTPS 域名。数据库需预先创建，应用账号需有业务库所需权限；查询账号应仅授予只读权限。URL 中的特殊字符需要百分号编码。
3. 配置域名 DNS 指向服务器，并在云防火墙开放 80/443。为生产流量配置 HTTPS（建议在主机前使用 Caddy、Traefik 或云负载均衡器终止 TLS）。
4. 启动服务：

   ```sh
   docker compose up -d --build
   docker compose ps
   ```

   默认通过 80 端口访问。若前方 HTTPS 代理或其他服务占用了 80，可在启动时设置 `WEB_PORT`，例如 `WEB_PORT=8080 docker compose up -d --build`。
5. 更新版本：拉取/复制新代码后执行 `docker compose up -d --build`。备份 MySQL，以及 `app_uploads`、`chroma_data` 两个 Docker 卷。

生产密钥不要提交到代码库。当前应用启动时通过 SQLAlchemy `create_all()` 创建缺失的表；正式升级表结构前应改用数据库迁移流程。Chroma 向量库与上传文件保存在持久化卷中。
