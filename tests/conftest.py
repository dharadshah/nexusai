import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers all models with Base.metadata
import app.database as app_database
from app.database import Base, get_db
from app.main import app

TEST_DB_PATH = "./test_nexusai.db"
TEST_DATABASE_URL = f"sqlite:///{TEST_DB_PATH}"


def get_test_engine():
    return create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False}
    )


@pytest.fixture(scope="function")
def db():
    # Create a fresh test engine and session factory
    test_engine = get_test_engine()
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )

    # Patch the app's database module so get_db uses test engine
    app_database.engine = test_engine
    app_database.SessionLocal = TestingSessionLocal

    # Create all tables
    Base.metadata.create_all(bind=test_engine)

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)


@pytest.fixture(scope="function")
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def sample_customer(client):
    response = client.post("/customers/", json={
        "first_name": "Dhara",
        "last_name": "Shah",
        "phone_number": "+919876543210",
        "email": "dhara@example.com",
    })
    assert response.status_code == 201, response.json()
    return response.json()["data"]


@pytest.fixture
def sample_campaign(client):
    response = client.post("/campaigns/", json={
        "name": "Q4 Payment Reminder",
        "campaign_type": "payment_reminder",
        "company_name": "NexusAI",
        "max_retries": 3,
    })
    assert response.status_code == 201, response.json()
    return response.json()["data"]