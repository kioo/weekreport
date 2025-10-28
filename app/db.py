from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./weekreports.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Member(Base):
    __tablename__ = "members"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    department = Column(String(100), nullable=True)
    position = Column(String(100), nullable=True)
    email = Column(String(200), nullable=True)
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
    except Exception as e:
        db.rollback()
        print(f"初始化成员数据失败: {e}")
    finally:
        db.close()