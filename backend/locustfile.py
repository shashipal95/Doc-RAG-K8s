import random
from locust import HttpUser, task, between

# --- Test Prompts ---
TEST_PROMPTS = [
    "Hello! What is Kubernetes?",
    "Explain vertical pod autoscaling vs horizontal pod autoscaling.",
    "Tell me a short story about an AI agent that loves monitoring databases.",
    "What is Prometheus and how does it collect metrics?",
    "Can you give me a quick Python snippet to calculate Fibonacci numbers?"
]

class DocChatUser(HttpUser):
    # Simulated think time between tasks (1 to 3 seconds)
    wait_time = between(1, 3)

    def on_start(self):
        """ Runs once when a virtual user is spawned """
        self.email = f"locust_{random.randint(100000, 999999)}@example.com"
        self.password = "locustpassword123"
        self.token = None
        self.session_id = None

        # 1. Sign up the user
        signup_payload = {
            "email": self.email,
            "password": self.password,
            "full_name": "Locust Load Tester"
        }
        with self.client.post("/api/v1/auth/signup", json=signup_payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Signup failed: {response.status_code} - {response.text}")

        # 2. Login to get JWT Token
        login_data = {
            "username": self.email,
            "password": self.password
        }
        with self.client.post("/api/v1/auth/login", data=login_data, catch_response=True) as response:
            if response.status_code == 200:
                token_data = response.json()
                self.token = token_data.get("access_token")
                self.client.headers.update({"Authorization": f"Bearer {self.token}"})
                response.success()
            else:
                response.failure(f"Login failed: {response.status_code} - {response.text}")
                return

        # 3. Create a chat session
        session_payload = {
            "title": "Locust Load Testing Session"
        }
        with self.client.post("/api/v1/sessions", json=session_payload, catch_response=True) as response:
            if response.status_code == 200:
                session_data = response.json()
                self.session_id = session_data.get("id")
                response.success()
            else:
                response.failure(f"Session creation failed: {response.status_code} - {response.text}")

    @task(3)
    def ask_llm_query(self):
        """ Task that sends query prompts to the backend """
        if not self.session_id:
            return

        prompt = random.choice(TEST_PROMPTS)
        payload = {
            "question": prompt,
            "provider": "groq",
            "session_id": self.session_id,
            "query_mode": "followup"
        }

        with self.client.post("/api/v1/documents/query", json=payload, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"LLM Query failed: {response.status_code} - {response.text}")

    @task(1)
    def get_chat_sessions(self):
        """ Task that lists the user's active sessions """
        with self.client.get("/api/v1/sessions", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Get sessions failed: {response.status_code} - {response.text}")
