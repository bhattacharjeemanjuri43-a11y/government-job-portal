from datetime import datetime, timedelta

from app.database import Base, engine, SessionLocal
from app.models import User, Job
from app.main import hash_password

Base.metadata.create_all(bind=engine)

db = SessionLocal()

try:
    admin_email = "admin@example.com"

    if not db.query(User).filter(
        User.email == admin_email
    ).first():
        admin = User(
            name="Portal Administrator",
            email=admin_email,
            password_hash=hash_password(
                "ChangeThisDemoPassword123!"
            ),
            role="admin",
            education="",
            skills=""
        )
        db.add(admin)

    if db.query(Job).count() == 0:
        jobs = [
            Job(
                title="Junior Software Assistant",
                department="Information Technology",
                location="Agartala, Tripura",
                description=(
                    "Assist with software systems, "
                    "data management and technical support."
                ),
                qualification=(
                    "Relevant degree as specified "
                    "in the official recruitment notice."
                ),
                required_skills="Python, SQL, communication",
                vacancies=12,
                deadline=datetime.utcnow() + timedelta(days=30),
                official_url="https://www.india.gov.in/",
                published=True
            ),
            Job(
                title="Clerical Assistant",
                department="Administration",
                location="Tripura",
                description=(
                    "Assist with office records, "
                    "documentation and clerical duties."
                ),
                qualification=(
                    "Qualification specified in the "
                    "official recruitment notice."
                ),
                required_skills="Typing, computer basics",
                vacancies=25,
                deadline=datetime.utcnow() + timedelta(days=21),
                official_url="https://www.india.gov.in/",
                published=True
            ),
            Job(
                title="Technical Support Trainee",
                department="Public Services IT",
                location="India",
                description=(
                    "Assist with IT support and "
                    "basic system troubleshooting."
                ),
                qualification=(
                    "Relevant diploma or degree, "
                    "as specified in the official notice."
                ),
                required_skills=(
                    "Networking, troubleshooting, documentation"
                ),
                vacancies=8,
                deadline=datetime.utcnow() + timedelta(days=14),
                official_url="https://www.india.gov.in/",
                published=True
            )
        ]

        db.add_all(jobs)

    db.commit()

    print("Database initialization complete.")
    print("Demo administrator:", admin_email)
    print("Change the demo password before deployment.")
    print("Sample jobs are fictional.")

finally:
    db.close()