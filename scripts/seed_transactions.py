#!/usr/bin/env python3
import argparse
import os
import random
import sys
from datetime import datetime, timedelta, date
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

# Make "app" importable when running from backend/
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Project models (expected paths based on your project)
from app.models.user import User
from app.models.category import Category
from app.models.transaction import Transaction


PM_MAP = {"cash": 0, "card": 1, "transfer": 2, "other": 3}


def parse_args():
    p = argparse.ArgumentParser(description="Seed many transactions for testing.")
    p.add_argument("--db-url", default=os.getenv("DATABASE_URL") or os.getenv("DB_URL") or "",
                   help="Postgres SQLAlchemy URL. If omitted, reads DATABASE_URL/DB_URL env.")
    p.add_argument("--user-email", default="", help="Seed for user by email (preferred).")
    p.add_argument("--user-id", default="", help="Seed for user by UUID (optional).")
    p.add_argument("--count", type=int, default=800, help="How many transactions to insert.")
    p.add_argument("--days", type=int, default=120, help="How many days back to spread transactions.")
    p.add_argument("--income-ratio", type=float, default=0.18, help="Share of income tx (0..1).")
    p.add_argument("--min-amount", type=float, default=10.0, help="Min amount (UAH).")
    p.add_argument("--max-amount", type=float, default=2500.0, help="Max amount (UAH).")
    p.add_argument("--currency", default="UAH", help="Currency code used in transactions.")
    p.add_argument("--commit-every", type=int, default=500, help="Commit batch size.")
    p.add_argument("--seed", type=int, default=42, help="Random seed.")
    return p.parse_args()


def money_to_cents(amount: float) -> int:
    return int(round(amount * 100))


def noon_local(dt: date) -> datetime:
    # noon to avoid timezone day-shifts
    return datetime(dt.year, dt.month, dt.day, 12, 0, 0)


def pick_user(session, user_email: str, user_id: str) -> User:
    if user_id:
        u = session.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        if not u:
            raise RuntimeError(f"User with id={user_id} not found")
        return u

    if user_email:
        u = session.execute(select(User).where(User.email == user_email)).scalar_one_or_none()
        if not u:
            raise RuntimeError(f"User with email={user_email} not found")
        return u

    # fallback: first user
    u = session.execute(select(User).order_by(User.created_at.asc())).scalars().first()
    if not u:
        raise RuntimeError("No users found in DB. Register a user first, then run seed.")
    return u


def ensure_categories(session, user: User):
    # Fetch existing categories
    cats = session.execute(
        select(Category).where(Category.user_id == user.id)
    ).scalars().all()

    expense = [c for c in cats if getattr(c, "type") == 0 and not getattr(c, "is_archived", False)]
    income = [c for c in cats if getattr(c, "type") == 1 and not getattr(c, "is_archived", False)]

    now = datetime.utcnow()

    def create_cat(type_int: int, name: str, icon: str, position: int):
        c = Category(
            id=uuid4(),
            user_id=user.id,
            type=type_int,               # 0 expense, 1 income
            name=name,
            icon=icon,
            color=None,
            is_default=False,
            is_archived=False,
            position=position,
            created_at=now,
            updated_at=now,
        )
        session.add(c)
        return c

    if len(expense) < 6:
        to_add = [
            ("Food", "🍔"),
            ("Transport", "🚌"),
            ("Coffee", "☕"),
            ("Groceries", "🛒"),
            ("Home", "🏠"),
            ("Fun", "🎮"),
            ("Health", "💊"),
            ("Subscriptions", "📺"),
        ]
        pos = 10
        for name, icon in to_add:
            if any(c.name == name and getattr(c, "type") == 0 for c in cats):
                continue
            create_cat(0, name, icon, pos)
            pos += 10

    if len(income) < 3:
        to_add = [
            ("Salary", "💼"),
            ("Freelance", "🧑‍💻"),
            ("Gift", "🎁"),
        ]
        pos = 10
        for name, icon in to_add:
            if any(c.name == name and getattr(c, "type") == 1 for c in cats):
                continue
            create_cat(1, name, icon, pos)
            pos += 10

    session.commit()

    cats = session.execute(select(Category).where(Category.user_id == user.id)).scalars().all()
    expense = [c for c in cats if getattr(c, "type") == 0 and not getattr(c, "is_archived", False)]
    income = [c for c in cats if getattr(c, "type") == 1 and not getattr(c, "is_archived", False)]
    return expense, income


def main():
    args = parse_args()
    random.seed(args.seed)

    if not args.db_url:
        raise RuntimeError(
            "DB URL not provided. Set env DATABASE_URL or pass --db-url.\n"
            "Example: postgresql+psycopg://user:pass@localhost:5432/expenses"
        )

    engine = create_engine(args.db_url, future=True)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

    with Session() as session:
        user = pick_user(session, args.user_email, args.user_id)
        print(f"Using user: id={user.id} email={getattr(user, 'email', '')}")

        expense_cats, income_cats = ensure_categories(session, user)
        print(f"Categories: expense={len(expense_cats)} income={len(income_cats)}")

        start_day = date.today() - timedelta(days=max(args.days - 1, 0))
        end_day = date.today()

        notes = [
            "Latte", "Taxi", "Lunch", "Grocery run", "Subscription", "Medicine",
            "Cinema", "Snacks", "Fuel", "Gym", "Delivery", "Coffee beans"
        ]
        pay_methods = list(PM_MAP.values())

        inserted = 0
        now = datetime.utcnow()

        for i in range(1, args.count + 1):
            is_income = random.random() < args.income_ratio
            type_int = 1 if is_income else 0

            day_offset = random.randint(0, max(args.days - 1, 0))
            tx_date = start_day + timedelta(days=day_offset)
            occurred_at = noon_local(tx_date)

            # amount distribution: more small expenses, occasional large
            amt = random.uniform(args.min_amount, args.max_amount)
            if not is_income and random.random() < 0.12:
                amt *= random.uniform(1.8, 3.2)  # occasional bigger expense
            if is_income:
                amt *= random.uniform(1.5, 6.0)  # income generally bigger
            amt = max(args.min_amount, min(amt, args.max_amount * 10))
            amount_cents = money_to_cents(amt)

            cat = random.choice(income_cats if is_income else expense_cats)
            pm = random.choice(pay_methods)
            note = random.choice(notes) if random.random() < 0.65 else None

            tx = Transaction(
                id=uuid4(),
                user_id=user.id,
                type=type_int,
                amount_cents=amount_cents,
                currency=args.currency,
                occurred_at=occurred_at,
                category_id=cat.id,
                payment_method=pm,
                note=note,
                source=0,              # seed/manual
                client_ref=uuid4().hex, # unique
                created_at=now,
                updated_at=now,
            )
            session.add(tx)
            inserted += 1

            if inserted % args.commit_every == 0:
                session.commit()
                print(f"Inserted {inserted}/{args.count}...")

        session.commit()
        print(f"Done. Inserted {inserted} transactions across ~{args.days} days.")


if __name__ == "__main__":
    main()
