from sqlalchemy.orm import Session

from app.features.auth.model import User

from app.common.database.base_repository import BaseRepository


class AuthRepository(BaseRepository):
    def __init__(self, db: Session):
        super().__init__(
        db=db,
        model=User,
    )

    def get_by_email(self, email: str):
        return (
            self.db.query(User)
            .filter(User.email == email)
            .first()
        )

    def create(self, user: User):
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user
    
    def get_by_email(self, email: str):
        return (
            self.db.query(User)
            .filter(User.email == email)
            .first()
        )
    def get_by_id(self, user_id: str):
        return (
            self.db.query(User)
            .filter(User.id == user_id)
            .first()
        )