# backend/database.py
from datetime import datetime
import os
from typing import Optional

from dotenv import load_dotenv
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    create_engine,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./postpartum.db")
# In Cloudflare D1 you'd use the same schema, just different hosting.

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},  # needed for SQLite + FastAPI
    )
else:
    engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class Mother(Base):
    __tablename__ = "mothers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    age = Column(Integer, nullable=True)
    country = Column(String, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    answers = relationship("Answer", back_populates="mother")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("text", name="uq_question_text"),)

    id = Column(Integer, primary_key=True, index=True)
    text = Column(Text, nullable=False)
    order_index = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, default=True)

    answers = relationship("Answer", back_populates="question")


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    mother_id = Column(Integer, ForeignKey("mothers.id"), nullable=False)
    question_id = Column(Integer, ForeignKey("questions.id"), nullable=False)
    answer_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    mother = relationship("Mother", back_populates="answers")
    question = relationship("Question", back_populates="answers")


def init_db():
    Base.metadata.create_all(bind=engine)
