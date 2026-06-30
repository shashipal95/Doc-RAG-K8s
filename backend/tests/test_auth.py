import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_signup_and_login_flow():
    # 1. Signup a new user
    signup_data = {
        "email": "test_auth_flow@example.com",
        "password": "testpassword123",
        "full_name": "Test Flow User"
    }
    # Form data request (application/x-www-form-urlencoded)
    response = client.post("/api/v1/auth/signup", data=signup_data)
    print("Signup response:", response.status_code, response.text)
    
    # If the user is already registered (from a previous test run), status could be 400
    if response.status_code == 400 and "Email already registered" in response.text:
        print("User already registered, proceeding to login test.")
    else:
        assert response.status_code == 200
        json_data = response.json()
        assert json_data["email"] == signup_data["email"]
        assert "access_token" in json_data

    # 2. Try to login
    login_data = {
        "email": signup_data["email"],
        "password": signup_data["password"]
    }
    response = client.post("/api/v1/auth/login", data=login_data)
    print("Login response:", response.status_code, response.text)
    assert response.status_code == 200
    json_data = response.json()
    assert "access_token" in json_data
    assert "user" in json_data
    assert json_data["user"]["email"] == signup_data["email"]
