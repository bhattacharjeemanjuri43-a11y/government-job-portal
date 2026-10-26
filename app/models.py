from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer,
    String, Text, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    name: Mapped[str] = mapped_column(
        String(120)
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True
    )
    password_hash: Mapped[str] = mapped_column(
        String(255)
    )
    role: Mapped[str] = mapped_column(
        String(20), default="candidate"
    )
    education: Mapped[str] = mapped_column(
        String(200), default=""
    )
    skills: Mapped[str] = mapped_column(
        Text, default=""
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    title: Mapped[str] = mapped_column(
        String(200), index=True
    )
    department: Mapped[str] = mapped_column(
        String(200)
    )
    location: Mapped[str] = mapped_column(
        String(200), default="India"
    )
    description: Mapped[str] = mapped_column(
        Text
    )
    qualification: Mapped[str] = mapped_column(
        String(500)
    )
    required_skills: Mapped[str] = mapped_column(
        Text, default=""
    )
    vacancies: Mapped[int] = mapped_column(
        Integer, default=1
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )
    official_url: Mapped[str] = mapped_column(
        String(500), default=""
    )
    published: Mapped[bool] = mapped_column(
        Boolean, default=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )


class Application(Base):
    __tablename__ = "applications"

    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "job_id",
            name="unique_candidate_job"
        ),
    )

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True
    )
    candidate_id: Mapped[int] = mapped_column(
        ForeignKey("users.id")
    )
    job_id: Mapped[int] = mapped_column(
        ForeignKey("jobs.id")
    )
    status: Mapped[str] = mapped_column(
        String(30), default="submitted"
    )
    cover_note: Mapped[str] = mapped_column(
        Text, default=""
    )
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow
    )