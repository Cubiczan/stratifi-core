# Stratifi Core — CockroachDB Persistence Layer
"""
SQLAlchemy ORM for distributed storage of stratification, risk scoring,
and consensus-hardened analysis results.
"""
from __future__ import annotations
import os, logging
from sqlalchemy import create_engine, Column, String, Integer, Numeric, DateTime, Text, Boolean, Index, JSON, func, select, desc
from sqlalchemy.orm import declarative_base, relationship, Session, sessionmaker
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger("stratifi_core.db")

COCKROACH_URL = "cockroachdb+psycopg2://REDACTED@vortex-giraffe-15678.jxf.gcp-us-east1.cockroachlabs.cloud:26257/stratifi_core?sslmode=require"
DATABASE_URL = os.getenv("STRATIFI_DATABASE_URL", COCKROACH_URL)
engine = create_engine(DATABASE_URL, pool_size=8, max_overflow=4, pool_timeout=30, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False)

def get_session() -> Session: return SessionLocal()

Base = declarative_base()

class TimestampMixin:
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AnalysisModel(TimestampMixin, Base):
    __tablename__ = "analyses"
    analysis_id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    title = Column(String, nullable=False)
    domain = Column(String, default="")
    company = Column(String, default="")
    status = Column(String, default="draft", index=True)  # draft, in_review, locked, archived
    high_stakes = Column(Boolean, default=False)
    origin_system = Column(String, default="Claude")
    foundation_score = Column(Integer, nullable=True)
    brief_data = Column(JSONB, default={})
    artifact_data = Column(JSONB, default={})
    audit_data = Column(JSONB, default={})
    dossier_data = Column(JSONB, default={})

    decision_cases = relationship("DecisionCaseModel", back_populates="analysis_rel", cascade="all, delete-orphan")


class DecisionCaseModel(TimestampMixin, Base):
    __tablename__ = "decision_cases"
    decision_id = Column(String, primary_key=True)
    title = Column(String, nullable=False)
    domain = Column(String, default="")
    analysis_id = Column(String, nullable=False, index=True)
    status = Column(String, default="EXPLORING", index=True)
    foundation_score = Column(Integer, nullable=True)
    current_phase = Column(String, default="FOUNDATION")
    current_round = Column(Integer, default=0)
    dossier = Column(JSONB, default={})
    locked_decisions = Column(JSONB, default=[])
    analysis_rel = relationship("AnalysisModel", back_populates="decision_cases")
    rounds = relationship("RoundRecordModel", back_populates="case_rel", cascade="all, delete-orphan")


class RoundRecordModel(TimestampMixin, Base):
    __tablename__ = "round_records"
    round_id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    decision_id = Column(String, nullable=False, index=True)
    phase = Column(String, default="FOUNDATION")
    round_number = Column(Integer, default=0)
    verdict = Column(String, default="")
    state_snapshot = Column(JSONB, default={})
    case_rel = relationship("DecisionCaseModel", back_populates="rounds")


class RiskSignalModel(TimestampMixin, Base):
    __tablename__ = "risk_signals"
    signal_id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(String, nullable=False, index=True)
    category = Column(String, default="")  # structural, blind_spot, failure_mode, flip_criterion
    description = Column(Text, default="")
    severity = Column(String, default="medium")  # low, medium, high, critical
    probability = Column(Numeric(5, 2), default=0)
    impact = Column(Numeric(5, 2), default=0)
    mitigation = Column(Text, default="")
    metadata_json = Column(JSONB, default={})


class ConsensusLogModel(TimestampMixin, Base):
    __tablename__ = "consensus_logs"
    log_id = Column(String, primary_key=True, server_default=func.gen_random_uuid())
    analysis_id = Column(String, nullable=False, index=True)
    decision_id = Column(String, default="")
    agent = Column(String, default="")
    claim = Column(Text, default="")
    grounding_source = Column(String, default="")
    grounding_confidence = Column(String, default="")
    risk_flag = Column(String, default="")
    validated = Column(Boolean, default=False)
    validator = Column(String, default="")


def health_check() -> dict:
    session = get_session()
    try:
        row = session.execute(func.current_timestamp()).scalar()
        analyses = session.execute(select(func.count()).select_from(AnalysisModel)).scalar()
        decisions = session.execute(select(func.count()).select_from(DecisionCaseModel)).scalar()
        signals = session.execute(select(func.count()).select_from(RiskSignalModel)).scalar()
        return {"status": "ok", "connected": True, "server_time": str(row), "analyses": analyses, "decision_cases": decisions, "risk_signals": signals, "backend": "CockroachDB"}
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)}
    finally:
        session.close()

def create_tables():
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created successfully")

if __name__ == "__main__":
    create_tables()
    print(health_check())
