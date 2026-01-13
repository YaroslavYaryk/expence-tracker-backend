from datetime import datetime
from sqlalchemy.orm import Session
from app.models.user import User
from app.repositories.users_repo import UsersRepo
from app.services.categories_service import CategoriesService
from app.core.config import settings


class UsersService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = UsersRepo(db)

    def get_or_create_by_external_auth(self, external_auth_id: str, email: str, full_name: str | None):
        user = self.repo.get_by_external_auth_id(external_auth_id)
        created = False
        if not user:
            user = User(
                external_auth_id=external_auth_id,
                email=email or "",
                full_name=full_name,
                timezone=settings.default_timezone,
                currency=settings.default_currency,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            self.repo.create(user)
            created = True
        else:
            # optional: keep email/name up-to-date (safe for MVP)
            changed = False
            if email and user.email != email:
                user.email = email
                changed = True
            if full_name and user.full_name != full_name:
                user.full_name = full_name
                changed = True
            if changed:
                user.updated_at = datetime.utcnow()

        if created:
            CategoriesService(self.db).seed_default_categories(user.id)

        self.db.commit()
        self.db.refresh(user)
        return user
