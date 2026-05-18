from fastapi.testclient import TestClient
from rpg_api import app
import pytest

client = TestClient(app)

@pytest.fixture
def auth_token():
    username = "fixtureuser"
    password = "fixturepassword"

    client.post("/auth/register", json = {
        "username": username,
        "password": password
    })

    response = client.post("/auth/login", json = {
        "username": username,
        "password": password
    })

    return response.json()["access_token"]

def test_root():
    response = client.get("/docs")
    assert response.status_code == 200

def test_register_success():
    response = client.post("/auth/register", json={
        "username": "tester",
        "password": "testpass"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_register_duplicate_username():
    client.post("/auth/register", json={
        "username": "duplicate",
        "password": "testpassword"
    })

    response = client.post("/auth/register", json={
        "username": "duplicate",
        "password": "anotherpassword"
    })

    assert response.status_code == 400

def test_login_success():
    client.post("/auth/register", json = {
        "username": "testlogin",
        "password": "testloginpassword"
    })

    response = client.post("/auth/login", json = {
        "username": "testlogin",
        "password": "testloginpassword"
    })

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_wrong_login():
    client.post("/auth/register", json = {
        "username": "wronglogin",
        "password": "wrongpassword"
    })

    response = client.post("/auth/login", json = {
        "username": "wronglogin",
        "password": "specialwrong"
    })

    assert response.status_code == 401

def test_create_hero():
    register_response = client.post("/auth/register", json = {
        "username": "herotester",
        "password": "hero123"
    })

    token = register_response.json()["access_token"]

    headers = {"Authorization": f"Bearer {token}"}
    response = client.post("/hero/create", json = {
        "name": "ТестовыйГерой"
    }, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["hero_name"] == "ТестовыйГерой"
    assert data["hero_hp"] == 50
    assert data["hero_max_hp"] == 50

def test_create_hero_without_token():
    response = client.post("/hero/create", json = {
        "name": "НеавторизированныйГерой"
    })

    assert response.status_code == 401

def test_create_hero_with_fixture(auth_token):
    headers = {"Authorization": f"Bearer {auth_token}"}
    response = client.post("/hero/create", json = {
        "name": "ГеройОтФикстуры"
    }, headers=headers)

    assert response.status_code == 200
    data = response.json()
    assert data["hero_name"] == "ГеройОтФикстуры"
    assert data["hero_hp"] == 50
    assert data["hero_max_hp"] == 50
