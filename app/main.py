from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .db import SessionLocal, Report, Member, Project, init_db
from .utils.summary import generate_weekly_summary
from .services.scheduler import start_scheduler, schedule_dingtalk_once, schedule_email_once
from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv

api_logger = logging.getLogger("weekreport.api")
import os
load_dotenv()

app = FastAPI(title="智能周报助手")

# 静态文件和模板
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# 简易管理权限校验：从查询参数 token 或请求头 X-Admin-Token 中校验
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "admin")

def require_admin(request: Request):
    token_q = request.query_params.get("token")
    token_h = request.headers.get("X-Admin-Token")
    token_c = request.cookies.get("ADMIN_TOKEN")
    token = token_q or token_h or token_c
    if ADMIN_TOKEN and token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")
    # 返回 None 表示通过

# 数据库依赖
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    # 运行时检查钉钉配置是否已加载
    webhook = os.getenv("DINGTALK_WEBHOOK")
    secret = os.getenv("DINGTALK_SECRET")
    api_logger.warning(
        "Startup env check: webhook_present=%s secret_present=%s",
        bool(webhook), bool(secret)
    )
    init_db()
    start_scheduler()

@app.get("/", response_class=HTMLResponse)
async def read_form(request: Request, db: Session = Depends(get_db)):
    # 获取活跃成员列表
    members = db.query(Member).filter(Member.is_active == 1).order_by(Member.name).all()
    return templates.TemplateResponse("index.html", {"request": request, "members": members})

@app.get("/api/members")
async def get_members(db: Session = Depends(get_db)):
    """获取成员列表API"""
    members = db.query(Member).filter(Member.is_active == 1).order_by(Member.name).all()
    return [{"id": m.id, "name": m.name, "department": m.department, "position": m.position} for m in members]

@app.get("/api/projects")
async def get_projects(db: Session = Depends(get_db)):
    """获取项目列表API"""
    projects = db.query(Project).order_by(Project.name).all()
    return [{
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "start_date": p.start_date.isoformat() if p.start_date else None,
        "expected_end_date": p.expected_end_date.isoformat() if p.expected_end_date else None
    } for p in projects]

@app.post("/submit")
async def submit_report(
    member_id: int = Form(...),
    member_name: str = Form(...),
    project: str = Form(...),
    work_desc: str = Form(...),
    progress: float = Form(...),
    next_week_plan: str = Form(...),
    risks: str = Form(""),
    db: Session = Depends(get_db)
):
    report = Report(
        member_id=member_id,
        member_name=member_name,
        project=project,
        work_desc=work_desc,
        progress=progress,
        next_week_plan=next_week_plan,
        risks=risks
    )
    db.add(report)
    db.commit()
    return RedirectResponse(url="/success", status_code=303)

@app.get("/success", response_class=HTMLResponse)
async def success_page(request: Request):
    return templates.TemplateResponse("success.html", {"request": request})

@app.get("/admin", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_dashboard(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})

@app.post("/admin/login")
async def admin_login(token: str = Form(...)):
    if token != ADMIN_TOKEN:
        return JSONResponse(content={"error": "密码错误"}, status_code=403)
    # 设置 Cookie 并重定向到 /admin
    resp = RedirectResponse(url="/admin", status_code=303)
    # Cookie 作用域设置为根路径，方便所有管理接口读取；生产可加 secure、samesite
    resp.set_cookie(key="ADMIN_TOKEN", value=token, httponly=True, max_age=3600, path="/")
    return resp

@app.get("/admin/summary", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def admin_summary(request: Request, db: Session = Depends(get_db)):
    summary_html = generate_weekly_summary(db)
    return HTMLResponse(content=summary_html)

@app.get("/admin/members", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def members_management(request: Request, db: Session = Depends(get_db)):
    """成员管理页面"""
    members = db.query(Member).order_by(Member.created_at.desc()).all()
    return templates.TemplateResponse("members.html", {"request": request, "members": members})

@app.get("/admin/projects", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
async def projects_management(request: Request, db: Session = Depends(get_db)):
    """项目管理页面"""
    projects = db.query(Project).order_by(Project.created_at.desc()).all()
    return templates.TemplateResponse("projects.html", {"request": request, "projects": projects})

@app.post("/admin/projects/add", dependencies=[Depends(require_admin)])
async def add_project(
    name: str = Form(...),
    description: str = Form(""),
    start_date: str = Form("") ,
    expected_end_date: str = Form(""),
    db: Session = Depends(get_db)
):
    """添加新项目"""
    try:
        # 解析日期（可选）
        sd = None
        if start_date:
            try:
                sd = datetime.fromisoformat(start_date).date()
            except Exception:
                sd = None
        ed = None
        if expected_end_date:
            try:
                ed = datetime.fromisoformat(expected_end_date).date()
            except Exception:
                ed = None
        proj = Project(name=name.strip(), description=description.strip() or None, start_date=sd, expected_end_date=ed)
        db.add(proj)
        db.commit()
        return RedirectResponse(url="/admin/projects", status_code=303)
    except Exception as e:
        return JSONResponse(content={"error": f"添加项目失败: {str(e)}"}, status_code=400)

@app.post("/admin/members/add", dependencies=[Depends(require_admin)])
async def add_member(
    name: str = Form(...),
    department: str = Form(""),
    position: str = Form(""),
    email: str = Form(""),
    db: Session = Depends(get_db)
):
    """添加新成员"""
    try:
        member = Member(
            name=name,
            department=department,
            position=position,
            email=email
        )
        db.add(member)
        db.commit()
        return RedirectResponse(url="/admin/members", status_code=303)
    except Exception as e:
        return JSONResponse(content={"error": f"添加成员失败: {str(e)}"}, status_code=400)

@app.post("/admin/members/{member_id}/toggle", dependencies=[Depends(require_admin)])
async def toggle_member_status(member_id: int, db: Session = Depends(get_db)):
    """切换成员状态（激活/停用）"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if member:
        member.is_active = 1 - member.is_active  # 切换状态
        db.commit()
        return JSONResponse(content={"success": True, "is_active": member.is_active})
    return JSONResponse(content={"error": "成员不存在"}, status_code=404)


# 便于测试的钉钉定时发送接口：支持GET/POST
@app.get("/admin/dingtalk/schedule", dependencies=[Depends(require_admin)])
async def schedule_dingtalk_get(text: str = "这是一条测试钉钉消息", delay_seconds: int = 0):
    """通过浏览器访问进行快速测试：/admin/dingtalk/schedule?text=...&delay_seconds=5"""
    api_logger.info("API GET schedule dingtalk: delay=%s text_len=%s", delay_seconds, len(text or ""))
    info = schedule_dingtalk_once(text=text, delay_seconds=delay_seconds)
    return JSONResponse(content=info)


@app.post("/admin/dingtalk/schedule", dependencies=[Depends(require_admin)])
async def schedule_dingtalk_post(
    text: str = Form("这是一条测试钉钉消息"),
    delay_seconds: int = Form(0),
):
    api_logger.info("API POST schedule dingtalk: delay=%s text_len=%s", delay_seconds, len(text or ""))
    info = schedule_dingtalk_once(text=text, delay_seconds=delay_seconds)
    return JSONResponse(content=info)


# 便于测试的周报汇总邮件定时发送接口：支持GET/POST
@app.get("/admin/email/schedule", dependencies=[Depends(require_admin)])
async def schedule_email_get(delay_seconds: int = 0):
    """通过浏览器访问进行快速测试：/admin/email/schedule?delay_seconds=5"""
    api_logger.info("API GET schedule weekly email: delay=%s", delay_seconds)
    info = schedule_email_once(delay_seconds=delay_seconds)
    return JSONResponse(content=info)


@app.post("/admin/email/schedule", dependencies=[Depends(require_admin)])
async def schedule_email_post(delay_seconds: int = Form(0)):
    api_logger.info("API POST schedule weekly email: delay=%s", delay_seconds)
    info = schedule_email_once(delay_seconds=delay_seconds)
    return JSONResponse(content=info)