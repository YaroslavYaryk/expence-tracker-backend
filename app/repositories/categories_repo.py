from sqlalchemy.orm import Session
from sqlalchemy import select, update
from app.models.category import Category


class CategoriesRepo:
    def __init__(self, db: Session):
        self.db = db

    def list(self, user_id, type_int: int, include_archived: bool) -> list[Category]:
        q = select(Category).where(Category.user_id == user_id, Category.type == type_int)
        if not include_archived:
            q = q.where(Category.is_archived == False)  # noqa: E712
        q = q.order_by(Category.position.asc(), Category.name.asc())
        return list(self.db.execute(q).scalars().all())

    def get_user_category(self, user_id, category_id) -> Category | None:
        q = select(Category).where(Category.user_id == user_id, Category.id == category_id)
        return self.db.execute(q).scalar_one_or_none()

    def get_by_name(self, user_id, type_int: int, name: str) -> Category | None:
        q = select(Category).where(Category.user_id == user_id, Category.type == type_int, Category.name == name)
        return self.db.execute(q).scalar_one_or_none()

    def create(self, cat: Category) -> Category:
        self.db.add(cat)
        self.db.flush()
        return cat

    def update_fields(self, user_id, category_id, fields: dict) -> int:
        q = update(Category).where(Category.user_id == user_id, Category.id == category_id).values(**fields)
        res = self.db.execute(q)
        return res.rowcount or 0
