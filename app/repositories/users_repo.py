from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.user import User


class UsersRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_external_auth_id(self, external_auth_id: str) -> User | None:
        return self.db.execute(
            select(User).where(User.external_auth_id == external_auth_id)
        ).scalar_one_or_none()

    def create(self, user: User) -> User:
        self.db.add(user)
        self.db.flush()
        return user
