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

3) 启动开发服务器
```bash
uvicorn app.main:app --reload
```
访问 `http://localhost:8000/` 提交周报，`/admin/summary` 查看汇总。

## 部署建议
- 可用 Docker 或系统服务化运行，确保 APScheduler 持续执行。
- SMTP 与钉钉配置放入安全的环境变量或密钥管理。

## 说明
- 首次运行会在项目根目录创建 `weekreports.db`。
- 未配置钉钉/邮件时，相关功能会自动跳过（不报错）。