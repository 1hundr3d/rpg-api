import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
import psycopg2

from database import Base, get_db
from rpg_api import app
from fastapi.testclient import TestClient

TEST_DATABASE_URL = os.getenv(
    'TEST_DATABASE_URL',
    f"postgresql://"
    f"{os.getenv('POSTGRES_USER', 'postgres')}:"
    f"{os.getenv('POSTGRES_PASSWORD', '12345')}@"
    f"{os.getenv('DB_HOST', 'localhost')}:"
    f"{os.getenv('DB_PORT', '5432')}/"
    f"testdb"
)

@pytest.fixture(scope='session')
def create_test_db():
    admin_url = TEST_DATABASE_URL.replace('/testdb', '/postgres')
    conn = psycopg2.connect(admin_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'testdb'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE testdb")
    
    cur.close()
    conn.close()

@pytest.fixture(scope='session')
def engine(create_test_db):
    return create_engine(TEST_DATABASE_URL, poolclass = NullPool)

@pytest.fixture(scope='function')
def db_session(engine):
    Base.metadata.create_all(bind=engine)

    connection = engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture(scope='function')
def client(db_session):
    def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

@pytest.fixture(scope='function')
def token(client, db_session):
    register_data = {
        "username": "testuser",
        "password": "testpassword"
    }
    client.post("/auth/register", json=register_data)
    response = client.post("/auth/login", json=register_data)
    return response.json()["access_token"]

@pytest.fixture(scope='function')
def authorized_client(client, token):
    client.headers.update({"Authorization": f"Bearer {token}"})
    return client


