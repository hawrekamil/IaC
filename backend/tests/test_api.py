from fastapi.testclient import TestClient
from app.core import Settings
from app.main import create_app


class StubService:
    def execute(self, operation):
        return {'operation': operation, 'status': 'succeeded'}


def client():
    return TestClient(create_app(Settings(api_key='k' * 32), StubService()))


def test_requires_authentication():
    assert client().post('/api/v1/connection-tests').status_code == 401


def test_connection_contract():
    response = client().post('/api/v1/connection-tests', headers={'X-API-Key': 'k' * 32})
    assert response.json() == {'operation': 'connection', 'status': 'succeeded'}


def test_ou_requires_explicit_confirmation():
    response = client().post('/api/v1/test-ou', json={}, headers={'X-API-Key': 'k' * 32})
    assert response.status_code == 422


def test_ou_rejects_extra_parameters():
    response = client().post('/api/v1/test-ou', json={
        'confirmation': 'CREATE_TEST_OU', 'host': 'other-server'
    }, headers={'X-API-Key': 'k' * 32})
    assert response.status_code == 422


def test_ou_contract():
    response = client().post('/api/v1/test-ou', json={'confirmation': 'CREATE_TEST_OU'},
                             headers={'X-API-Key': 'k' * 32})
    assert response.json() == {'operation': 'test_ou', 'status': 'succeeded'}
