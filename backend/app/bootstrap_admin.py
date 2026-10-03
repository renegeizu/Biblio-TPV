"""Create the first administrator from explicitly supplied environment secrets."""

from sqlalchemy import func, select

from app.config import get_settings
from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password


def main() -> None:
    """Create the first administrator, or safely skip an initialized database."""
    settings = get_settings()
    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(User)):
            print("Database already has users; administrator bootstrap skipped")
            return
        username = settings.bootstrap_admin_username.strip().lower()
        password = settings.bootstrap_admin_password
        if not username or password is None or len(password.get_secret_value()) < 12:
            raise SystemExit("Set BOOTSTRAP_ADMIN_USERNAME and BOOTSTRAP_ADMIN_PASSWORD (at least 12 characters)")
        db.add(User(username=username, password_hash=hash_password(password.get_secret_value()), role=UserRole.ADMIN))
        db.commit()
    print(f"Initial administrator '{username}' created")


if __name__ == "__main__":
    main()