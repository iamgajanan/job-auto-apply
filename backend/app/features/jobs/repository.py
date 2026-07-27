from sqlalchemy.orm import Session

from app.features.jobs.model import Job


class JobRepository:

    def __init__(self, db: Session):
        self.db = db

    def save(self, job_data):

        existing = (
            self.db.query(Job)
            .filter(
                Job.job_id == job_data["job_id"]
            )
            .first()
        )

        if existing:

            existing.title = job_data["title"]
            existing.company = job_data["company"]
            existing.location = job_data["location"]
            existing.salary = job_data["salary"]
            existing.experience = job_data["experience"]
            existing.work_mode = job_data["work_mode"]
            existing.easy_apply = job_data["easy_apply"]
            existing.job_url = job_data["job_url"]
            existing.company_logo = job_data["company_logo"]
            existing.posted_at = job_data["posted_at"]

            self.db.commit()
            self.db.refresh(existing)

            return existing

        job = Job(**job_data)

        self.db.add(job)

        self.db.commit()

        self.db.refresh(job)

        return job

    def save_many(self, jobs):

        saved = []

        for job in jobs:
            saved.append(self.save(job))

        return saved

    def get_all(self):

        return (
            self.db.query(Job)
            .order_by(Job.created_at.desc())
            .all()
        )