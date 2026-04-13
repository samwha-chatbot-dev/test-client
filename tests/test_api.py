"""API 테스트 코드"""
import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_root_redirect():
    """루트 경로가 로그인 화면으로 리다이렉트되는지 확인"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 307 or response.status_code == 303


@pytest.mark.asyncio
async def test_login_page():
    """로그인 페이지 접근 확인"""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/login")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")









