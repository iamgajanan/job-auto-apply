from sqlalchemy.orm import Session

from app.features.audit.model import SearchLog


class AuditRepository:

    def __init__(self, db: Session):
        self.db = db

    def create(self, log: SearchLog):

        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)

        return log