from datetime import datetime
from sqlalchemy.orm import Session
from app.models.category import Category
from app.repositories.categories_repo import CategoriesRepo
from app.core.errors import AppError

DEFAULT_EXPENSE = [
    ("Їжа", "🍔"),
    ("Транспорт", "🚗"),
    ("Житло", "🏠"),
    ("Комунальні", "💡"),
    ("Здоровʼя", "🏥"),
    ("Одяг", "👕"),
    ("Розваги", "🎮"),
    ("Покупки", "🛍"),
    ("Підписки", "📦"),
    ("Освіта", "📚"),
    ("Подарунки", "🎁"),
    ("Інше", "❓"),
]

DEFAULT_INCOME = [
    ("Зарплата", "💼"),
    ("Фриланс", "💻"),
    ("Бонуси", "🎉"),
    ("Інше", "❓"),
]


def type_to_int(t: str) -> int:
    return 0 if t == "expense" else 1


class CategoriesService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CategoriesRepo(db)

    def seed_default_categories(self, user_id):
        now = datetime.utcnow()
        # expense
        for i, (name, icon) in enumerate(DEFAULT_EXPENSE):
            existing = self.repo.get_by_name(user_id, 0, name)
            if existing:
                continue
            self.repo.create(
                Category(
                    user_id=user_id,
                    type=0,
                    name=name,
                    icon=icon,
                    is_default=True,
                    is_archived=False,
                    position=i,
                    created_at=now,
                    updated_at=now,
                )
            )
        # income
        for i, (name, icon) in enumerate(DEFAULT_INCOME):
            existing = self.repo.get_by_name(user_id, 1, name)
            if existing:
                continue
            self.repo.create(
                Category(
                    user_id=user_id,
                    type=1,
                    name=name,
                    icon=icon,
                    is_default=True,
                    is_archived=False,
                    position=i,
                    created_at=now,
                    updated_at=now,
                )
            )

    def list(self, user_id, type_str: str, include_archived: bool):
        return self.repo.list(user_id, type_to_int(type_str), include_archived)

    def create(self, user_id, type_str: str, name: str, icon: str | None, color: str | None, position: int):
        now = datetime.utcnow()
        t = type_to_int(type_str)
        if self.repo.get_by_name(user_id, t, name):
            raise AppError("CONFLICT", "Category already exists", status_code=409)
        cat = Category(
            user_id=user_id,
            type=t,
            name=name.strip(),
            icon=icon,
            color=color,
            is_default=False,
            is_archived=False,
            position=position,
            created_at=now,
            updated_at=now,
        )
        self.repo.create(cat)
        self.db.commit()
        return cat

    def update(self, user_id, category_id, fields: dict):
        fields["updated_at"] = datetime.utcnow()
        count = self.repo.update_fields(user_id, category_id, fields)
        if count == 0:
            raise AppError("NOT_FOUND", "Category not found", status_code=404)
        self.db.commit()
