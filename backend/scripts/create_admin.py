"""Create or promote a SOPIA user.

Examples:
    python scripts/create_admin.py --email admin@example.com --password 'Str0ngPass!'
    python scripts/create_admin.py --email user@example.com --password 'Str0ngPass!' --role USER
"""

import argparse
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.security import get_password_hash  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.user import Organization, RoleEnum, User  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or promote a SOPIA user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default=None)
    parser.add_argument(
        "--role",
        default=RoleEnum.SUPER_ADMIN.value,
        choices=[r.value for r in RoleEnum],
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    db = SessionLocal()
    try:
        org = db.query(Organization).order_by(Organization.id).first()
        if org is None:
            org = Organization(name="Default Organization")
            db.add(org)
            db.commit()
            db.refresh(org)

        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(
                email=email,
                hashed_password=get_password_hash(args.password),
                full_name=args.full_name,
                role=args.role,
                organization_id=org.id,
                is_active=True,
            )
            db.add(user)
            db.commit()
            print(f"Created user {email} with role {args.role}")
        else:
            user.role = args.role
            user.hashed_password = get_password_hash(args.password)
            user.is_active = True
            if args.full_name:
                user.full_name = args.full_name
            if user.organization_id is None:
                user.organization_id = org.id
            db.commit()
            print(f"Updated user {email} to role {args.role}")
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
