from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy import Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import inspect
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weekreports.db")

# 根据数据库类型设置引擎参数（SQLite 需要 check_same_thread，其他如 PostgreSQL 不需要）
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    start_date = Column(Date, nullable=True)
    expected_end_date = Column(Date, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Member(Base):
    __tablename__ = "members"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
    phone = Column(String(20), nullable=True)
    is_active = Column(Integer, default=1)  # 1=active, 0=inactive
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    reports = relationship("Report", back_populates="member")

class Report(Base):
    __tablename__ = "reports"
    
    id = Column(Integer, primary_key=True, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    member_name = Column(String(100), nullable=False)  # 保留兼容性
    project = Column(String(100), nullable=False)
    work_desc = Column(Text, nullable=False)
    progress = Column(Float, nullable=False)
    next_week_plan = Column(Text, nullable=False)
    risks = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # 关系
    member = relationship("Member", back_populates="reports")

def init_db():
    Base.metadata.create_all(bind=engine)
    # 轻量级迁移：确保 members 表存在 phone 字段（跨数据库）
    try:
        insp = inspect(engine)
        cols = [c.get("name") for c in insp.get_columns("members")]
        if "phone" not in cols:
            from sqlalchemy import text
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE members ADD COLUMN phone VARCHAR(20)"))
    except Exception as e:
        print(f"检查/添加 phone 字段失败: {e}")
    
    # 初始化默认成员数据
    db = SessionLocal()
    try:
        # 检查是否已有成员数据
        if db.query(Member).count() == 0:
            default_members = [
                Member(name="张三", department="研发部", position="高级工程师", email="zhangsan@company.com"),
                Member(name="李四", department="产品部", position="产品经理", email="lisi@company.com"),
                Member(name="王五", department="研发部", position="前端工程师", email="wangwu@company.com"),
                Member(name="赵六", department="测试部", position="测试工程师", email="zhaoliu@company.com"),
                Member(name="钱七", department="运维部", position="运维工程师", email="qianqi@company.com"),
            ]
            for member in default_members:
                db.add(member)
            db.commit()

        # 初始化默认项目数据
        if db.query(Project).count() == 0:
            default_projects = [
                Project(name="支付系统升级", description="支付通道整合与性能优化"),
                Project(name="核心平台", description="核心服务平台建设"),
                Project(name="移动端App", description="移动客户端迭代"),
                Project(name="数据治理", description="数据质量与标准化治理"),
                Project(name="运营后台", description="运营支撑后台优化"),
            ]
            for proj in default_projects:
                db.add(proj)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"初始化成员数据失败: {e}")
    finally:
        db.close()