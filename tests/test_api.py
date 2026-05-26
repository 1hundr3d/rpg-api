import pytest

def test_root(client):
    response = client.get("/docs")
    assert response.status_code == 200

def test_register_success(client):
    response = client.post("/auth/register", json={
        "username": "tester",
        "password": "testpass"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_register_duplicate_username(client):
    client.post("/auth/register", json={
        "username": "duplicate",
        "password": "testpassword"
    })

    response = client.post("/auth/register", json={
        "username": "duplicate",
        "password": "anotherpassword"
    })

    assert response.status_code == 400

def test_login_success(client):
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

def test_wrong_login(client):
    client.post("/auth/register", json = {
        "username": "wronglogin",
        "password": "wrongpassword"
    })

    response = client.post("/auth/login", json = {
        "username": "wronglogin",
        "password": "specialwrong"
    })

    assert response.status_code == 401

def test_create_hero(authorized_client):
    response = authorized_client.post("/hero/create", json = {
        "name": "herotester"
    })

    assert response.status_code == 200
    data = response.json()
    assert data["hero_name"] == "herotester"
    assert data["hero_hp"] == 50
    assert data["hero_max_hp"] == 50

def test_create_hero_without_token(client):
    response = client.post("/hero/create", json = {
        "name": "НеавторизированныйГерой"
    })

    assert response.status_code == 401

