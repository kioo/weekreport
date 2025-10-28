from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from collections import defaultdict
from ..db import Report, Member


def get_week_range(dt: datetime) -> tuple[datetime, datetime]:
    # ISO week: Monday=0 ... Sunday=6
    start = dt - timedelta(days=dt.weekday())
    start = datetime(start.year, start.month, start.day)
    end = start + timedelta(days=6, hours=23, minutes=59, seconds=59)
    return start, end


def generate_weekly_summary(db: Session) -> str:
    now = datetime.utcnow()
    start, end = get_week_range(now)
    
    # 联表查询获取报告和成员信息
    reports_with_members = (
        db.query(Report, Member)
        .outerjoin(Member, Report.member_id == Member.id)
        .filter(Report.created_at >= start, Report.created_at <= end)
        .order_by(Report.project, Report.member_name)
        .all()
    )

    grouped: dict[str, list[tuple[Report, Member]]] = defaultdict(list)
    for report, member in reports_with_members:
        grouped[report.project].append((report, member))

    # Build HTML summary
    head = f"""
    <html><head><meta charset='utf-8'>
    <title>本周周报汇总</title>
    <style>
    body {{ font-family: system-ui, -apple-system, Segoe UI, Helvetica, Arial; background:#f7f9fc; color:#1f2937; }}
    .wrap {{ max-width: 960px; margin: 20px auto; }}
    .card {{ background:#fff; border-radius:12px; box-shadow:0 6px 18px rgba(0,0,0,0.06); padding:18px; margin-bottom:16px; }}
    h1 {{ font-size:22px; margin:10px 0 16px; }}
    h2 {{ font-size:18px; margin:0 0 12px; }}
    table {{ width:100%; border-collapse: collapse; }}
    th, td {{ border-bottom:1px solid #e5e7eb; padding:10px; text-align:left; vertical-align:top; }}
    th {{ background:#f3f4f6; font-weight:600; }}
    .muted {{ color:#6b7280; }}
    </style></head><body>
    <div class='wrap'>
    <h1>本周周报汇总（{start:%Y-%m-%d} ~ {end:%Y-%m-%d}）</h1>
    """

    if not grouped:
        head += "<p class='card muted'>暂无数据，本周尚未提交。</p>"

    for project, items in grouped.items():
        head += f"<div class='card'><h2>项目：{project}</h2>"
        head += "<table><thead><tr><th>成员</th><th>部门/职位</th><th>本周工作</th><th>进度</th><th>下周计划</th><th>风险与问题</th></tr></thead><tbody>"
        for report, member in items:
            # 构建成员信息显示
            member_info = ""
            if member:
                dept_pos = []
                if member.department:
                    dept_pos.append(member.department)
                if member.position:
                    dept_pos.append(member.position)
                member_info = " / ".join(dept_pos) if dept_pos else "-"
            else:
                member_info = "-"
            
            head += (
                f"<tr>"
                f"<td>{report.member_name}</td>"
                f"<td class='muted'>{member_info}</td>"
                f"<td>{escape_html(report.work_desc)}</td>"
                f"<td>{report.progress}%</td>"
                f"<td>{escape_html(report.next_week_plan)}</td>"
                f"<td>{escape_html(report.risks or '')}</td>"
                f"</tr>"
            )
        head += "</tbody></table></div>"

    head += "</div></body></html>"
    return head


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br>")
    )