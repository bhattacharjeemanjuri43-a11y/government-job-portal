from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

import jwt
from dotenv import load_dotenv
from fastapi import (
    FastAPI, Depends, HTTPException, Query
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import (
    HTTPBearer, HTTPAuthorizationCredentials
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.database import Base, engine, get_db
from app.models import User, Job, Application
from app.agent import run_agent

load_dotenv()

JWT_SECRET = os.getenv(
    "JWT_SECRET_KEY",
    "development-only-change-this-secret"
)
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = int(
    os.getenv("ACCESS_TOKEN_MINUTES", "60")
)

security = HTTPBearer(auto_error=False)


# ---------------------------
# Request and response schemas
# ---------------------------

class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)
    education: str = ""
    skills: list[str] = []


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class JobRequest(BaseModel):
    title: str
    department: str
    location: str = "India"
    description: str
    qualification: str
    required_skills: list[str] = []
    vacancies: int = Field(default=1, ge=1)
    deadline: datetime | None = None
    official_url: str = ""


class ApplicationRequest(BaseModel):
    job_id: int
    cover_note: str = ""


class AgentRequest(BaseModel):
    message: str = Field(min_length=2, max_length=2000)


# ---------------------------
# Password and JWT functions
# ---------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=2**14,
        r=8,
        p=1
    )
    return (
        salt.hex() + "$" + derived.hex()
    )


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, expected_hex = stored.split("$", 1)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=2**14,
            r=8,
            p=1
        )
        return hmac.compare_digest(
            actual.hex(), expected_hex
        )
    except (ValueError, TypeError):
        return False


def create_token(user: User) -> str:
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user.id),
        "iat": now,
        "exp": now + timedelta(minutes=TOKEN_MINUTES)
    }

    return jwt.encode(
        payload,
        JWT_SECRET,
        algorithm=JWT_ALGORITHM
    )


# ---------------------------
# Authentication dependencies
# ---------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials | None =
        Depends(security),
    db: Session = Depends(get_db)
) -> User:

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Please log in first"
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET,
            algorithms=[JWT_ALGORITHM]
        )
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token"
        )

    user = db.get(User, user_id)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="User not found"
        )

    return user


def require_admin(
    user: User = Depends(get_current_user)
) -> User:
    if user.role != "admin":
        raise HTTPException(
            status_code=403,
            detail="Administrator access required"
        )
    return user


# ---------------------------
# Application startup
# ---------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Government Job Available Portal",
    description=(
        "Government job search, applications, "
        "authentication and Agentic AI assistant"
    ),
    version="1.0.0",
    lifespan=lifespan
)

origins = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip() for origin in origins
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"]
)


@app.get("/")
def home():
    return {
        "message": "Government Job Available Portal API",
        "status": "running",
        "documentation": "/docs"
    }


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------
# Candidate registration
# ---------------------------

@app.post("/api/auth/register", status_code=201)
def register(
    data: RegisterRequest,
    db: Session = Depends(get_db)
):
    email = str(data.email).lower()

    if db.query(User).filter(
        User.email == email
    ).first():
        raise HTTPException(
            status_code=409,
            detail="Email already registered"
        )

    user = User(
        name=data.name.strip(),
        email=email,
        password_hash=hash_password(data.password),
        role="candidate",
        education=data.education,
        skills=", ".join(
            skill.strip()
            for skill in data.skills
            if skill.strip()
        )
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return {
        "message": "Registration successful",
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "role": user.role
        }
    }


# ---------------------------
# Login
# ---------------------------

@app.post("/api/auth/login")
def login(
    data: LoginRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == str(data.email).lower()
    ).first()

    if (
        not user
        or not verify_password(
            data.password, user.password_hash
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid email or password"
        )

    return {
        "access_token": create_token(user),
        "token_type": "bearer",
        "expires_in": TOKEN_MINUTES * 60
    }


# ---------------------------
# Candidate profile
# ---------------------------

@app.get("/api/users/me")
def my_profile(
    user: User = Depends(get_current_user)
):
    return {
        "id": user.id,
        "name": user.name,
        "email": user.email,
        "education": user.education,
        "skills": user.skills,
        "role": user.role
    }


@app.patch("/api/users/me")
def update_profile(
    data: dict,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    allowed = {"name", "education", "skills"}

    if set(data) - allowed:
        raise HTTPException(
            status_code=400,
            detail="Unsupported profile field"
        )

    if "name" in data:
        if not isinstance(data["name"], str):
            raise HTTPException(
                status_code=422,
                detail="Name must be text"
            )
        if not 2 <= len(data["name"].strip()) <= 120:
            raise HTTPException(
                status_code=422,
                detail="Name must be 2-120 characters"
            )
        user.name = data["name"].strip()

    if "education" in data:
        if not isinstance(data["education"], str):
            raise HTTPException(
                status_code=422,
                detail="Education must be text"
            )
        user.education = data["education"][:200]

    if "skills" in data:
        skills = data["skills"]
        if isinstance(skills, list):
            user.skills = ", ".join(
                str(skill).strip()
                for skill in skills
                if str(skill).strip()
            )
        elif isinstance(skills, str):
            user.skills = skills[:3000]
        else:
            raise HTTPException(
                status_code=422,
                detail="Skills must be a list or string"
            )

    db.commit()
    db.refresh(user)

    return {"message": "Profile updated"}


# ---------------------------
# Public job search
# ---------------------------

@app.get("/api/jobs")
def list_jobs(
    q: str = "",
    location: str = "",
    department: str = "",
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    jobs = db.query(Job).filter(
        Job.published.is_(True)
    )

    if q:
        from sqlalchemy import or_
        term = f"%{q[:100]}%"
        jobs = jobs.filter(
            or_(
                Job.title.ilike(term),
                Job.description.ilike(term),
                Job.qualification.ilike(term),
                Job.required_skills.ilike(term)
            )
        )

    if location:
        jobs = jobs.filter(
            Job.location.ilike(f"%{location[:100]}%")
        )

    if department:
        jobs = jobs.filter(
            Job.department.ilike(
                f"%{department[:100]}%"
            )
        )

    result = jobs.order_by(
        Job.created_at.desc()
    ).offset(skip).limit(limit).all()

    return [
        {
            "id": j.id,
            "title": j.title,
            "department": j.department,
            "location": j.location,
            "description": j.description,
            "qualification": j.qualification,
            "required_skills": j.required_skills,
            "vacancies": j.vacancies,
            "deadline": (
                j.deadline.isoformat()
                if j.deadline else None
            ),
            "official_url": j.official_url
        }
        for j in result
    ]


@app.get("/api/jobs/{job_id}")
def job_details(
    job_id: int,
    db: Session = Depends(get_db)
):
    from app.agent import get_job_details

    result = get_job_details(db, job_id)

    if "error" in result:
        raise HTTPException(
            status_code=404,
            detail=result["error"]
        )

    return result


# ---------------------------
# Admin: create a job listing
# ---------------------------

@app.post("/api/admin/jobs", status_code=201)
def create_job(
    data: JobRequest,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    if (
        data.deadline is not None
        and data.deadline.tzinfo is not None
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Provide deadline without a timezone, "
                "using the portal's configured local time."
            )
        )

    job = Job(
        title=data.title,
        department=data.department,
        location=data.location,
        description=data.description,
        qualification=data.qualification,
        required_skills=", ".join(data.required_skills),
        vacancies=data.vacancies,
        deadline=data.deadline,
        official_url=data.official_url,
        published=True
    )

    db.add(job)
    db.commit()
    db.refresh(job)

    return {
        "message": "Job listing created",
        "job_id": job.id,
        "title": job.title
    }


# ---------------------------
# Candidate applies for a job
# ---------------------------

@app.post("/api/applications", status_code=201)
def apply_for_job(
    data: ApplicationRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if user.role != "candidate":
        raise HTTPException(
            status_code=403,
            detail="Only candidates can apply"
        )

    job = db.query(Job).filter(
        Job.id == data.job_id,
        Job.published.is_(True)
    ).first()

    if not job:
        raise HTTPException(
            status_code=404,
            detail="Published job not found"
        )

    # This is the portal's configured deadline comparison,
    # not a substitute for checking the official notice.
    if (
        job.deadline
        and job.deadline < datetime.utcnow()
    ):
        raise HTTPException(
            status_code=400,
            detail="Portal deadline has passed"
        )

    application = Application(
        candidate_id=user.id,
        job_id=job.id,
        cover_note=data.cover_note
    )

    db.add(application)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="You already applied through this portal"
        )

    db.refresh(application)

    return {
        "message": "Application recorded in this portal",
        "application_id": application.id,
        "job_id": job.id,
        "status": application.status
    }


@app.get("/api/applications/me")
def my_applications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    records = db.query(Application).filter(
        Application.candidate_id == user.id
    ).order_by(Application.submitted_at.desc()).all()

    return [
        {
            "application_id": item.id,
            "job_id": item.job_id,
            "status": item.status,
            "submitted_at": item.submitted_at.isoformat()
        }
        for item in records
    ]


# ---------------------------
# Admin: application management
# ---------------------------

@app.get("/api/admin/applications")
def admin_applications(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    records = db.query(Application).order_by(
        Application.submitted_at.desc()
    ).limit(500).all()

    return [
        {
            "id": item.id,
            "candidate_id": item.candidate_id,
            "job_id": item.job_id,
            "status": item.status,
            "submitted_at": item.submitted_at.isoformat()
        }
        for item in records
    ]


@app.patch("/api/admin/applications/{application_id}/status")
def update_application_status(
    application_id: int,
    data: dict,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    allowed = {
        "submitted",
        "under_review",
        "exam_scheduled",
        "document_verification",
        "selected",
        "not_selected",
        "withdrawn"
    }

    status = data.get("status")

    if status not in allowed:
        raise HTTPException(
            status_code=422,
            detail=f"Status must be one of {sorted(allowed)}"
        )

    application = db.get(Application, application_id)

    if not application:
        raise HTTPException(
            status_code=404,
            detail="Application not found"
        )

    application.status = status
    db.commit()

    return {
        "application_id": application.id,
        "status": application.status
    }


# ---------------------------
# Agentic AI endpoint
# ---------------------------

@app.post("/api/agent/chat")
def agent_chat(
    data: AgentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    answer, tools_used = run_agent(
        db, user, data.message
    )

    return {
        "answer": answer,
        "tools_used": tools_used,
        "disclaimer": (
            "Verify vacancies, deadlines, eligibility and "
            "application instructions in the official notice."
        )
    }