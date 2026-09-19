"""CLI utility to reset user passwords or list accounts in the database.

Usage:
    python -m scripts.reset_password --list
    python -m scripts.reset_password user@example.com NewPassword123!
"""

from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from src.auth import hash_password
from src.database import SessionLocal, init_db
from src.models import User


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reset user passwords or list accounts in the SQLite database."
    )
    parser.add_argument("email", nargs="?", help="User email address")
    parser.add_argument("password", nargs="?", help="New password (min 12 characters)")
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all registered user emails in the database",
    )

    args = parser.parse_args()
    init_db()

    if args.list:
        with SessionLocal() as db:
            users = db.scalars(select(User).order_by(User.id)).all()
            if not users:
                print("No users found in database.")
                return
            print(f"Registered Users ({len(users)} total):")
            for u in users:
                role = getattr(u, "role", "agent")
                print(f"  [ID {u.id}] {u.email} (role: {role}, created: {str(u.created_at)[:19]})")
        return

    if not args.email or not args.password:
        parser.print_help()
        sys.exit(1)

    email = args.email.strip().lower()
    password = args.password

    if len(password) < 12:
        print("Error: Password must be at least 12 characters long.", file=sys.stderr)
        sys.exit(1)

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"Error: No user found with email '{email}'.", file=sys.stderr)
            sys.exit(1)

        user.password_hash = hash_password(password)
        db.commit()
        print(f"Successfully updated password for {user.email}.")


if __name__ == "__main__":
    main()
