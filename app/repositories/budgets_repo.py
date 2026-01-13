from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete
from app.models.budget import Budget


class BudgetsRepo:
    def __init__(self, db: Session):
        self.db = db

    def list_for_month(self, user_id, month_date):
        q = select(Budget).where(Budget.user_id == user_id, Budget.month == month_date)
        return list(self.db.execute(q).scalars().all())

    def get_by_id(self, user_id, budget_id):
        q = select(Budget).where(Budget.user_id == user_id, Budget.id == budget_id)
        return self.db.execute(q).scalar_one_or_none()

    def create(self, b: Budget) -> Budget:
        self.db.add(b)
        self.db.flush()
        return b

    def update_fields(self, user_id, budget_id, fields: dict) -> int:
        q = update(Budget).where(Budget.user_id == user_id, Budget.id == budget_id).values(**fields)
        res = self.db.execute(q)
        return res.rowcount or 0

    def delete(self, user_id, budget_id) -> int:
        q = delete(Budget).where(Budget.user_id == user_id, Budget.id == budget_id)
        res = self.db.execute(q)
        return res.rowcount or 0
