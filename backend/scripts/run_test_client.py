import asyncio
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def run_test():
    email = "test_run_client@example.com"
    password = "MySecurePassword123"
    
    print("--- STEP 1: SIGNUP ---")
    signup_data = {
        "email": email,
        "password": password,
        "full_name": "Test Run User"
    }
    res = client.post("/api/v1/auth/signup", data=signup_data)
    print("Signup Status:", res.status_code)
    print("Signup Body:", res.text)
    
    print("\n--- STEP 2: LOGIN ---")
    login_data = {
        "email": email,
        "password": password
    }
    res2 = client.post("/api/v1/auth/login", data=login_data)
    print("Login Status:", res2.status_code)
    print("Login Body:", res2.text)

if __name__ == "__main__":
    run_test()
