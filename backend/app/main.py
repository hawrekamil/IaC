import secrets
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from typing import Literal
from pydantic import BaseModel, ConfigDict
from .core import LabError, LabService, Settings


class OURequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmation: Literal['CREATE_TEST_OU']


def create_app(settings=None, service=None):
    settings = settings or Settings.from_env()
    service = service or LabService(settings)
    app = FastAPI(title='Windows Lab Automation', version='0.1.0')
    key_header = APIKeyHeader(name='X-API-Key', auto_error=False)

    def authorize(key=Depends(key_header)):
        if len(settings.api_key) < 32:
            raise HTTPException(503, 'api_key_not_configured')
        if not key or not secrets.compare_digest(key.encode(), settings.api_key.encode()):
            raise HTTPException(401, 'invalid_api_key')

    def run(operation):
        try:
            return service.execute(operation)
        except LabError as exc:
            raise HTTPException(exc.status, exc.code) from None

    @app.get('/health')
    def health():
        return {'status': 'ok', 'execution_enabled': settings.enabled}

    @app.post('/api/v1/connection-tests', dependencies=[Depends(authorize)])
    def connection_test():
        return run('connection')

    @app.post('/api/v1/test-ou', dependencies=[Depends(authorize)])
    def create_test_ou(request: OURequest):
        return run('test_ou')

    return app


app = create_app()
