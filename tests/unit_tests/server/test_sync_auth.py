# -*- coding: utf-8 -*-
"""
测试 a2c_smcp/server/sync_auth.py
"""
from __future__ import annotations

from unittest.mock import MagicMock

from a2c_smcp.server.sync_auth import DefaultSyncAuthenticationProvider


def test_sync_get_agent_id_and_default():
    prov = DefaultSyncAuthenticationProvider("adm")
    sio = MagicMock()
    sio.app = MagicMock()
    sio.app.state = MagicMock()
    sio.app.state.agent_id = "A"
    assert prov.get_agent_id(sio, {}) == "A"

    sio2 = object()
    assert prov.get_agent_id(sio2, {}) == "default_agent"


def test_sync_authenticate_variants():
    prov = DefaultSyncAuthenticationProvider("adm")
    sio = MagicMock()

    ok = prov.authenticate(sio, "aid", None, [(b"x-api-key", b"adm")])
    assert ok is True

    assert prov.authenticate(sio, "aid", None, []) is False
    assert prov.authenticate(sio, "aid", None, [(b"x-api-key", b"wrong")]) is False


def test_sync_has_admin_permission():
    prov1 = DefaultSyncAuthenticationProvider(None)
    assert prov1.has_admin_permission(MagicMock(), "aid", "adm") is False

    prov2 = DefaultSyncAuthenticationProvider("adm")
    assert prov2.has_admin_permission(MagicMock(), "aid", "adm") is True
