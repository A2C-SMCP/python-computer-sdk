# -*- coding: utf-8 -*-
"""
测试 a2c_smcp/server/auth.py
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from a2c_smcp.server.auth import DefaultAuthenticationProvider


@pytest.mark.asyncio
async def test_get_agent_id_from_app_state_and_default():
    prov = DefaultAuthenticationProvider("admin")

    # 带 app.state.agent_id
    sio = AsyncMock()
    sio.app = MagicMock()
    sio.app.state = MagicMock()
    sio.app.state.agent_id = "agentX"
    assert await prov.get_agent_id(sio, {}) == "agentX"

    # 无 app/state -> default_agent（使用无属性对象避免 Mock 自动创建属性）
    sio2 = object()
    assert await prov.get_agent_id(sio2, {}) == "default_agent"


@pytest.mark.asyncio
async def test_authenticate_admin_ok_and_missing_or_wrong_key():
    prov = DefaultAuthenticationProvider("admin_secret")
    sio = AsyncMock()

    # 正确 key
    headers = [(b"x-api-key", b"admin_secret")]
    ok = await prov.authenticate(sio, "aid", None, headers)
    assert ok is True

    # 缺失 key
    headers = []
    ok2 = await prov.authenticate(sio, "aid", None, headers)
    assert ok2 is False

    # 错误 key
    headers = [(b"x-api-key", b"wrong")]
    ok3 = await prov.authenticate(sio, "aid", None, headers)
    assert ok3 is False


@pytest.mark.asyncio
async def test_has_admin_permission_variants():
    prov1 = DefaultAuthenticationProvider(None)
    sio = AsyncMock()
    assert await prov1.has_admin_permission(sio, "aid", "admin") is False

    prov2 = DefaultAuthenticationProvider("admin")
    assert await prov2.has_admin_permission(sio, "aid", "admin") is True
