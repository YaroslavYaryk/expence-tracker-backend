from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete, and_, or_
from app.models.transaction import Transaction


class TransactionsRepo:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id, tx_id):
        q = select(Transaction).where(Transaction.user_id == user_id, Transaction.id == tx_id)
        return self.db.execute(q).scalar_one_or_none()

    def get_by_client_ref(self, user_id, client_ref: str):
        q = select(Transaction).where(Transaction.user_id == user_id, Transaction.client_ref == client_ref)
        return self.db.execute(q).scalar_one_or_none()

    def create(self, tx: Transaction) -> Transaction:
        self.db.add(tx)
        self.db.flush()
        return tx

    def update_fields(self, user_id, tx_id, fields: dict) -> int:
        q = update(Transaction).where(Transaction.user_id == user_id, Transaction.id == tx_id).values(**fields)
        res = self.db.execute(q)
        return res.rowcount or 0

    def delete(self, user_id, tx_id) -> int:
        q = delete(Transaction).where(Transaction.user_id == user_id, Transaction.id == tx_id)
        res = self.db.execute(q)
        return res.rowcount or 0

    def list_cursor(
        self,
        user_id,
        from_ts,
        to_ts,
        type_int: int | None,
        category_id,
        payment_method_int: int | None,
        q_text: str | None,
        limit: int,
        cursor_occurred_at,
        cursor_id,
    ):
        q = select(Transaction).where(
            Transaction.user_id == user_id,
            Transaction.occurred_at >= from_ts,
            Transaction.occurred_at < to_ts,
        )

        if type_int is not None:
            q = q.where(Transaction.type == type_int)
        if category_id is not None:
            q = q.where(Transaction.category_id == category_id)
        if payment_method_int is not None:
            q = q.where(Transaction.payment_method == payment_method_int)
        if q_text:
            q = q.where(Transaction.note.ilike(f"%{q_text}%"))

        # cursor condition
        if cursor_occurred_at and cursor_id:
            q = q.where(
                or_(
                    Transaction.occurred_at < cursor_occurred_at,
                    and_(Transaction.occurred_at == cursor_occurred_at, Transaction.id < cursor_id),
                )
            )

        q = q.order_by(Transaction.occurred_at.desc(), Transaction.id.desc()).limit(limit)
        return list(self.db.execute(q).scalars().all())
