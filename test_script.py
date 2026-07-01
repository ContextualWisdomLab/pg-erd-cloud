from fastapi.testclient import TestClient
from app import main as main_app
from app.csrf import CSRF_HEADER_NAME, generate_csrf_token
from app.settings import settings

client = TestClient(main_app.app)
headers = {CSRF_HEADER_NAME: generate_csrf_token(settings.app_secret)}
response = client.post("/api/auth/logout", headers=headers)
print(response.status_code)
print(response.json() if response.status_code != 500 else response.text)
