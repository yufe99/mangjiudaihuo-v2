"""Smoke test: app import + health + auth flow.

Run: pytest tests/test_smoke.py -v
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.fixture
async def client():
    from app.core.db import Base, engine, init_db

    await init_db()

    # Clean slate: drop + recreate all tables (test isolation)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # ASGITransport doesn't run lifespan; register providers explicitly
    from app.providers.registry import register_all_providers

    register_all_providers()

    from app.main import create_app

    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


@pytest.mark.asyncio
async def test_register_login_me(client: AsyncClient):
    email = "smoke@example.com"
    password = "testpass123"

    # Register
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "name": "Smoke"},
    )
    assert r.status_code == 201, r.text
    tokens = r.json()
    assert "access_token" in tokens
    access = tokens["access_token"]

    # Login
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert r.status_code == 200, r.text

    # Me
    r = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert r.status_code == 200
    assert r.json()["email"] == email


@pytest.mark.asyncio
async def test_project_crud_flow(client: AsyncClient):
    # Register + login
    email = "project@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123"},
    )
    access = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {access}"}

    # Create project
    r = await client.post(
        "/api/v1/projects",
        headers=auth,
        json={
            "name": "测试漫剧",
            "type": "manju",
            "style": "穿越",
            "topic": "一个程序员穿越到古代",
            "episode_count": 3,
            "seconds_per_episode": 15,
        },
    )
    assert r.status_code == 201, r.text
    project = r.json()
    pid = project["id"]

    # List
    r = await client.get("/api/v1/projects", headers=auth)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Get
    r = await client.get(f"/api/v1/projects/{pid}", headers=auth)
    assert r.status_code == 200
    assert r.json()["name"] == "测试漫剧"

    # Update
    r = await client.patch(
        f"/api/v1/projects/{pid}",
        headers=auth,
        json={"topic": "改了个主题"},
    )
    assert r.status_code == 200
    assert r.json()["topic"] == "改了个主题"

    # Delete
    r = await client.delete(f"/api/v1/projects/{pid}", headers=auth)
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_script_generate_local_preview(client: AsyncClient):
    """Script generation via local_preview provider (no API key needed)."""
    email = "script@example.com"
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "testpass123"},
    )
    access = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {access}"}

    # Create project
    r = await client.post(
        "/api/v1/projects",
        headers=auth,
        json={
            "name": "带货测试",
            "type": "daihuo",
            "style": "短剧带货",
            "topic": "智能手表",
            "product_detail": "这款智能手表支持心率监测、血氧检测、50米防水,续航14天",
            "episode_count": 3,
        },
    )
    pid = r.json()["id"]

    # Generate script — provider defaults to toapis which may not have key.
    # For smoke test, we patch the provider to local_preview first.
    # Since registry is global, simplest: directly test ScriptService with local preview LLM.
    from app.providers.base import ProviderRegistry
    from app.providers.local_preview import LocalPreviewLLMProvider
    from app.modules.script.service import ScriptService

    llm = LocalPreviewLLMProvider()
    system, user_prompt = ScriptService.build_prompt(
        topic="智能手表",
        style="短剧带货",
        project_type="daihuo",
        episode_count=3,
        seconds_per_episode=15,
        product_info="心率监测",
    )
    result = await llm.generate_text(prompt=user_prompt, system=system)
    assert result.success
    assert result.text
    parsed = ScriptService.parse_response(result.text)
    assert "characters" in parsed
    assert "episodes" in parsed
    assert len(parsed["episodes"]) >= 1