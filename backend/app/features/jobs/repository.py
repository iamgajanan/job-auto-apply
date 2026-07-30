from sqlalchemy.orm import Session

from app.features.jobs.model import Job


class JobRepository:

    def __init__(self, db: Session):
        self.db = db

    def save_many(self, jobs):

        saved = []

        try:

            for job_data in jobs:

                job_data = job_data.copy()

                job_data.pop("posted_within", None)

                # Prevent NULL values
                job_data["salary"] = (
                    job_data.get("salary")
                    or "Not Disclosed"
                )

                job_data["experience"] = (
                    job_data.get("experience")
                    or "Not Mentioned"
                )

                job_data["work_mode"] = (
                    job_data.get("work_mode")
                    or "Unknown"
                )

                job_data["apply_url"] = (
                    job_data.get("apply_url")
                    or ""
                )

                job_data["description"] = (
                    job_data.get("description")
                    or ""
                )

                job_data["company_logo"] = (
                    job_data.get("company_logo")
                    or ""
                )

                existing = (
                    self.db.query(Job)
                    .filter(Job.job_id == job_data["job_id"])
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
                    existing.apply_url = job_data["apply_url"]
                    existing.description = job_data["description"]
                    existing.company_logo = job_data["company_logo"]
                    existing.posted_at = job_data["posted_at"]

                    saved.append(existing)

                else:

                    job = Job(**job_data)

                    self.db.add(job)

                    saved.append(job)

            self.db.commit()

            for job in saved:
                self.db.refresh(job)

            return saved

        except Exception:

            self.db.rollback()

            raise

    def get_all(self):

        return (
            self.db.query(Job)
            .order_by(Job.created_at.desc())
            .all()
        )