# 智能周报助手（FastAPI + SQLite）

轻量化的周报自动化系统：结构化提交、自动汇总、钉钉提醒、邮件分发。

## 功能
- 结构化表单提交：姓名、项目、本周工作、进度、下周计划、风险问题。
- 周报汇总视图：按项目聚合，生成美观HTML。
- 定时任务：周五10:00钉钉提醒，周五18:00邮件发送汇总。
- SQLite持久化存储，支持本地快速部署。

## 快速开始
0) 创建虚拟环境
python -m venv .venv 
.venv\Scripts\activate

1) 安装依赖
```bash
pip install -r requirements.txt
```

2) 配置环境变量（可选）
- 复制 `.env.example` 为 `.env` 并填写：
  - `DINGTALK_WEBHOOK` / `DINGTALK_SECRET`
  - `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASS` / `MAIL_TO`
  - 数据库（PostgreSQL 推荐）：设置 `DATABASE_URL`
    - 例：`postgresql+psycopg2://user:pass@localhost:5432/weekreport`
    - 未设置时默认使用 `sqlite:///./weekreports.db`
  - 可选：启用大模型摘要（硅基流动）
    - `LLM_SUMMARY_ENABLED=true`
    - `SILICONFLOW_API_KEY=你的API密钥`
    - `SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1`（如默认可省略）
    - `SILICONFLOW_MODEL=Qwen2.5-14B-Instruct`（可替换为可用模型）
    - `SILICONFLOW_TEMPERATURE=0.2` / `SILICONFLOW_MAX_TOKENS=1024`

3) 启动开发服务器
```bash
uvicorn app.main:app --reload
# 所有人都能访问
uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips='*'
```
访问 `http://localhost:8000/` 提交周报，`/admin/summary` 查看汇总。

### 启用大模型摘要（硅基流动）
- 在 `.env` 设置 `LLM_SUMMARY_ENABLED=true` 并填写 `SILICONFLOW_API_KEY`。
- 系统会在“周五18:00 邮件任务”或通过 `/admin/email/schedule` 测试接口触发时，先用大模型生成本周摘要，再将摘要卡片插入到邮件正文顶部。
- 如摘要接口失败或未启用，系统回退为原始汇总邮件，不影响发送。

## 部署建议
- 可用 Docker 或系统服务化运行，确保 APScheduler 持续执行。
- SMTP 与钉钉配置放入安全的环境变量或密钥管理。

## 容器化部署
- 构建镜像：`docker build -t weekreportflow:latest .`
- 使用 SQLite（开发/个人用）：`docker compose up -d`
  - 默认将宿主机 `./data` 挂载到容器 `/data`，应用使用 `sqlite:////data/weekreports.db` 持久化。
- 使用 PostgreSQL（推荐生产）：`docker compose -f docker-compose.pg.yml up -d`
  - 如自建 PG，将 `web.environment.DATABASE_URL` 替换为你的连接串。
- 停止与日志：
  - 停止：`docker compose down` 或 `docker compose -f docker-compose.pg.yml down`
  - 查看应用日志：`docker compose logs -f web`
  - 查看数据库日志（PG）：`docker compose -f docker-compose.pg.yml logs -f db`

## 说明
- 首次运行（SQLite）会在项目根目录创建 `weekreports.db`；使用 PostgreSQL 时请确保目标库已创建并账号具备建表权限。
- 未配置钉钉/邮件时，相关功能会自动跳过（不报错）。

### 从 SQLite 迁移到 PostgreSQL
- 设置 `DATABASE_URL` 指向 PostgreSQL 后端并安装依赖 `psycopg2-binary`（已在 `requirements.txt`）。
- 首次连接会按当前模型创建表结构，但不会自动迁移旧库数据。如需迁移，请导出原有数据并导入 Postgres（可使用 `sqlite3` 导出 + `psql` 导入，或借助 `alembic` 编写迁移脚本）。

## 完成功能
- 添加所属项目可以实时添加，支持删除，但是已经使用的项目不能删除。
- 更新人员和项目
- 钉钉发消息时可以指定 @ 某个用户
- 添加周报总结使用大模型总结内容，并且按照模板格式输出
## 待办
- 将数据库换成 MySQL 或 PostgreSQL 等关系型数据库。
- 添加项目维护，项目周期-填写周报时提供项目状况预览
- 代码提交情况，bug 情况
- 添加自动登录功能-微信，gmail，github
- 每月自动发送周报总结邮件到各个角色
- 添加多租户功能