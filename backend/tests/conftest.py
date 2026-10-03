"""Shared PostgreSQL-backed API test fixtures."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import URL
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import get_db
from app.main import app
from app.models import Base, User, UserRole
from app.security import hash_password

os.environ.setdefault("APP_ENV", "test")

TEST_DATABASE_URL = os.environ.get("DATABASE_URL")
if TEST_DATABASE_URL is None and os.environ.get("DATABASE_HOST"):
    TEST_DATABASE_URL = URL.create(
        "postgresql+psycopg",
        username=os.environ.get("DATABASE_USER", "biblio"),
        password=os.environ.get("DATABASE_PASSWORD", ""),
        host=os.environ["DATABASE_HOST"],
        port=int(os.environ.get("DATABASE_PORT", "5432")),
        database=os.environ.get("DATABASE_NAME", "biblio_tpv_test"),
    ).render_as_string(hide_password=False)
TEST_DATABASE_URL = TEST_DATABASE_URL or "sqlite+pysqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False} if TEST_DATABASE_URL.startswith("sqlite") else {},
    poolclass=StaticPool if TEST_DATABASE_URL.endswith(":memory:") else None,
)
TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def reset_schema() -> None:
    """Recreate the isolated test schema so failed runs cannot leak DDL state."""
    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.exec_driver_sql("DROP SCHEMA IF EXISTS public CASCADE")
            connection.exec_driver_sql("CREATE SCHEMA public")
    else:
        Base.metadata.drop_all(engine)


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    """Provide an isolated schema and a seeded administrator per test."""
    reset_schema()
    Base.metadata.create_all(engine)

    def override_get_db() -> Generator[Session, None, None]:
        with TestingSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestingSession() as session:
        session.add_all([
            User(username="admin", password_hash=hash_password("test-admin-password"), role=UserRole.ADMIN),
            User(username="cashier", password_hash=hash_password("test-cashier-password"), role=UserRole.CASHIER),
            User(username="supervisor", password_hash=hash_password("test-supervisor-password"), role=UserRole.SUPERVISOR),
        ])
        session.commit()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    reset_schema()


@pytest.fixture()
def admin(client: TestClient) -> TestClient:
    """Return a client authenticated as administrator."""
    client.post("/api/v1/auth/login", json={"username": "admin", "password": "test-admin-password"})
    return client