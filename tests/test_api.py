from fastapi.testclient import TestClient
from thechangelogbot.api.main import app

client = TestClient(app)


class TestAPI:
    def test_read_root(self):
        response = client.get("/")
        assert response.status_code == 200
