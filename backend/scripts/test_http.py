import httpx

def test_real_http():
    url = "http://127.0.0.1:8000"
    email = "test_real_http@example.com"
    password = "MySecurePassword123"
    
    print("--- STEP 1: SIGNUP ---")
    signup_data = {
        "email": email,
        "password": password,
        "full_name": "Test Real HTTP User"
    }
    # x-www-form-urlencoded
    res = httpx.post(f"{url}/api/v1/auth/signup", data=signup_data)
    print("Signup Status:", res.status_code)
    print("Signup Body:", res.text)
    
    print("\n--- STEP 2: LOGIN ---")
    login_data = {
        "email": email,
        "password": password
    }
    res2 = httpx.post(f"{url}/api/v1/auth/login", data=login_data)
    print("Login Status:", res2.status_code)
    print("Login Body:", res2.text)

if __name__ == "__main__":
    test_real_http()
