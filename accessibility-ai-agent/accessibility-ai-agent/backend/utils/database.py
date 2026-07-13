"""
Database — SQLite via aiosqlite + SQLAlchemy async
"""
import os
import json
from datetime import datetime
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import Column, String, Integer, Float, Text, DateTime

from backend.utils.config import settings

os.makedirs("data", exist_ok=True)

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ScanRecord(Base):
    __tablename__ = "scans"

    id            = Column(String, primary_key=True)
    url           = Column(String, nullable=False)
    model         = Column(String, default="llama3")
    status        = Column(String, default="pending")
    step          = Column(String, default="")
    score         = Column(Float,  default=0)
    error         = Column(Text,   nullable=True)
    violations    = Column(Text,   default="[]")
    ai_analyses   = Column(Text,   default="[]")
    exec_summary  = Column(Text,   default="{}")
    metrics       = Column(Text,   default="{}")
    passed_checks     = Column(Text, default="[]")
    extra_screenshots = Column(Text, default="[]")
    rule_results      = Column(Text, default="{}")
    generated_scenarios = Column(Text, default="[]")
    created_at    = Column(DateTime, default=datetime.utcnow)
    completed_at  = Column(DateTime, nullable=True)

    def to_dict(self):
        return {
            "id":               self.id,
            "url":              self.url,
            "model":            self.model,
            "status":           self.status,
            "step":             self.step,
            "score":            self.score,
            "error":            self.error,
            "violations":       json.loads(self.violations    or "[]"),
            "ai_analyses":      json.loads(self.ai_analyses   or "[]"),
            "executive_summary":json.loads(self.exec_summary  or "{}"),
            "metrics":          json.loads(self.metrics       or "{}"),
            "passed_checks":    json.loads(self.passed_checks     or "[]"),
            "extra_screenshots":json.loads(self.extra_screenshots or "[]"),
            "rule_results":     json.loads(self.rule_results      or "{}"),
            "generated_scenarios": json.loads(self.generated_scenarios or "[]"),
            "created_at":       self.created_at.isoformat()  if self.created_at  else None,
            "completed_at":     self.completed_at.isoformat() if self.completed_at else None,
        }


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing DB if they don't exist
        for col_sql in [
            "ALTER TABLE scans ADD COLUMN passed_checks TEXT DEFAULT '[]'",
            "ALTER TABLE scans ADD COLUMN extra_screenshots TEXT DEFAULT '[]'",
            "ALTER TABLE scans ADD COLUMN rule_results TEXT DEFAULT '{}'",
            "ALTER TABLE scans ADD COLUMN generated_scenarios TEXT DEFAULT '[]'",
        ]:
            try:
                await conn.execute(__import__('sqlalchemy').text(col_sql))
            except Exception:
                pass  # Column already exists


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
