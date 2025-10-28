from fastapi import FastAPI, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from .db import SessionLocal, Report, Member, init_db
from .utils.summary import generate_weekly_summary
from .services.scheduler import start_scheduler, schedule_dingtalk_once
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

@app.get("/admin/summary", response_class=HTMLResponse)
async def admin_summary(request: Request, db: Session = Depends(get_db)):
    summary_html = generate_weekly_summary(db)
    return HTMLResponse(content=summary_html)

@app.get("/admin/members", response_class=HTMLResponse)
async def members_management(request: Request, db: Session = Depends(get_db)):
    """成员管理页面"""
    members = db.query(Member).order_by(Member.created_at.desc()).all()
    return templates.TemplateResponse("members.html", {"request": request, "members": members})

@app.post("/admin/members/add")
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

@app.post("/admin/members/{member_id}/toggle")
async def toggle_member_status(member_id: int, db: Session = Depends(get_db)):
    """切换成员状态（激活/停用）"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if member:
        member.is_active = 1 - member.is_active  # 切换状态
        db.commit()
        return JSONResponse(content={"success": True, "is_active": member.is_active})
    return JSONResponse(content={"error": "成员不存在"}, status_code=404)


# 便于测试的钉钉定时发送接口：支持GET/POST
@app.get("/admin/dingtalk/schedule")
async def schedule_dingtalk_get(text: str = "这是一条测试钉钉消息", delay_seconds: int = 0):
    """通过浏览器访问进行快速测试：/admin/dingtalk/schedule?text=...&delay_seconds=5"""
    api_logger.info("API GET schedule dingtalk: delay=%s text_len=%s", delay_seconds, len(text or ""))
    info = schedule_dingtalk_once(text=text, delay_seconds=delay_seconds)
    return JSONResponse(content=info)


@app.post("/admin/dingtalk/schedule")
async def schedule_dingtalk_post(
    text: str = Form("这是一条测试钉钉消息"),
    delay_seconds: int = Form(0),
):
    api_logger.info("API POST schedule dingtalk: delay=%s text_len=%s", delay_seconds, len(text or ""))
    info = schedule_dingtalk_once(text=text, delay_seconds=delay_seconds)
    return JSONResponse(content=info)