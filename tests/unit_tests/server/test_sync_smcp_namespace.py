# -*- coding: utf-8 -*-
"""
测试 a2c_smcp/server/sync_namespace.py
覆盖 enter_room/leave_room 及所有 on_* 分支
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from a2c_smcp.server.sync_namespace import SyncSMCPNamespace
from a2c_smcp.smcp import (
    CANCEL_TOOL_CALL_NOTIFICATION,
    ENTER_OFFICE_NOTIFICATION,
    LEAVE_OFFICE_NOTIFICATION,
)


class _DummyAuthProv:
    def get_agent_id(self, sio, environ):  # pragma: no cover - not used here
        return "aid"

    def authenticate(self, sio, agent_id, auth, headers):  # pragma: no cover - not used here
        return True


@pytest.fixture()
def ns():
    n = SyncSMCPNamespace(_DummyAuthProv())
    # 伪造 server 结构
    server = MagicMock()
    server.manager = MagicMock()
    server.manager.get_participants = MagicMock(return_value=[])
    n.server = server
    # 常用桩
    n.get_session = MagicMock(return_value={})
    n.save_session = MagicMock()
    n.emit = MagicMock()
    return n


def test_enter_room_agent_rules(ns):
    # agent 在其他房间 -> 抛错
    ns.get_session.return_value = {"role": "agent", "office_id": "A"}
    with pytest.raises(ValueError):
        ns.enter_room("sidA", "B")

    # agent 不在任何房间，房间已有 agent -> 抛错
    ns.get_session.return_value = {"role": "agent"}
    ns.server.manager.get_participants.return_value = ["sidX"]
    # 该参与者为 agent

    def _get_sess_for_participant(sid):
        if sid == "sidX":
            return {"role": "agent"}
        return {}

    ns.get_session.side_effect = [
        {"role": "agent"},  # self session
        {"role": "agent"},  # participant session
    ]
    with pytest.raises(ValueError):
        ns.enter_room("sidB", "room1")

    # agent 已在同一房间 -> 返回且不重复 emit
    ns.get_session.side_effect = None
    ns.get_session.return_value = {"role": "agent", "office_id": "room1"}
    ns.emit.reset_mock()
    ns.enter_room("sidC", "room1")
    ns.emit.assert_not_called()


def test_enter_room_computer_switch_and_duplicate(ns):
    # computer 从 roomA 切到 roomB
    ns.get_session.return_value = {"role": "computer", "office_id": "roomA"}
    ns.leave_room = MagicMock()
    ns.enter_room("csid", "roomB")
    ns.leave_room.assert_called_once_with("csid", "roomA")

    # 重复加入
    ns.get_session.return_value = {"role": "computer", "office_id": "roomB"}
    ns.emit.reset_mock()
    ns.enter_room("csid", "roomB")
    ns.emit.assert_not_called()


def test_enter_room_updates_session_and_broadcast(ns):
    # 新加入应设置 office_id 并广播 ENTER_OFFICE_NOTIFICATION
    ns = SyncSMCPNamespace(_DummyAuthProv())
    server = MagicMock()
    server.manager = MagicMock()
    server.manager.get_participants = MagicMock(return_value=[])
    ns.server = server

    sess = {"role": "computer"}
    ns.get_session = MagicMock(return_value=sess)
    ns.save_session = MagicMock()
    ns.emit = MagicMock()

    ns.enter_room("sid1", "roomZ")

    assert sess["office_id"] == "roomZ"
    ns.emit.assert_called_once()
    args, kwargs = ns.emit.call_args
    assert args[0] == ENTER_OFFICE_NOTIFICATION
    assert kwargs.get("room") == "roomZ"
    assert kwargs.get("skip_sid") == "sid1"


def test_leave_room_broadcast_and_clear_session(monkeypatch):
    ns = SyncSMCPNamespace(_DummyAuthProv())
    ns.emit = MagicMock()
    sess = {"role": "computer", "office_id": "roomX"}
    ns.get_session = MagicMock(return_value=sess)
    ns.save_session = MagicMock()

    # 避免真正调用父类 leave_room
    from a2c_smcp.server.sync_base import SyncBaseNamespace

    monkeypatch.setattr(SyncBaseNamespace, "leave_room", MagicMock())
    ns.leave_room("sidX", "roomX")

    ns.emit.assert_called_once()
    args, kwargs = ns.emit.call_args
    assert args[0] == LEAVE_OFFICE_NOTIFICATION
    assert "office_id" not in sess  # 已清理


def test_on_server_join_office_ok_and_rollback_on_error():
    ns = SyncSMCPNamespace(_DummyAuthProv())
    ns.get_session = MagicMock(return_value={})
    ns.save_session = MagicMock()
    # ensure server exists for enter_room path
    server = MagicMock()
    server.manager = MagicMock()
    server.manager.get_participants = MagicMock(return_value=[])
    ns.server = server

    # 正常路径
    ok, err = ns.on_server_join_office("sid", {"role": "computer", "name": "n", "office_id": "o"})
    assert ok is True and err is None

    # enter_room 抛错 -> 回滚
    ns.enter_room = MagicMock(side_effect=RuntimeError("boom"))
    ok2, err2 = ns.on_server_join_office("sid", {"role": "computer", "name": "n", "office_id": "o"})
    assert ok2 is False and "Internal server error" in err2


def test_on_server_leave_office_ok_and_error():
    ns = SyncSMCPNamespace(_DummyAuthProv())
    ns.leave_room = MagicMock()
    ok, err = ns.on_server_leave_office("sid", {"office_id": "o"})
    assert ok is True and err is None

    ns.leave_room = MagicMock(side_effect=RuntimeError("x"))
    ok2, err2 = ns.on_server_leave_office("sid", {"office_id": "o"})
    assert ok2 is False and "Internal server error" in err2


def test_on_server_tool_call_cancel_and_update_config_and_client_paths():
    ns = SyncSMCPNamespace(_DummyAuthProv())

    # cancel 仅允许 agent
    ns.get_session = MagicMock(return_value={"role": "agent"})
    ns.emit = MagicMock()
    ns.on_server_tool_call_cancel("a1", {"robot_id": "a1", "req_id": "r1"})
    ns.emit.assert_called_once()
    args1, kwargs1 = ns.emit.call_args
    assert args1[0] == CANCEL_TOOL_CALL_NOTIFICATION
    assert kwargs1.get("skip_sid") == "a1"

    # update_config 仅允许 computer
    ns.get_session = MagicMock(return_value={"role": "computer", "office_id": "roomR"})
    ns.emit = MagicMock()
    ns.on_server_update_config("c1", {"computer": "c1"})
    ns.emit.assert_called_once()
    _args2, kwargs2 = ns.emit.call_args
    assert kwargs2.get("room") == "roomR"

    # client tool_call：仅允许 agent，直接 emit
    ns.get_session = MagicMock(return_value={"role": "agent"})
    ns.emit = MagicMock()
    ret = ns.on_client_tool_call("a1", {"robot_id": "a1", "computer": "c1", "tool_name": "t", "params": {}})
    assert ret == {"status": "sent"}
    ns.emit.assert_called_once()
    args, kwargs = ns.emit.call_args
    assert kwargs.get("room") == "c1"

    # client get_tools：校验在同一房间并转发
    ns.get_session = MagicMock(side_effect=[
        {"role": "computer", "office_id": "room1"},  # computer sess
        {"role": "agent", "office_id": "room1"},     # agent sess
    ])
    ns.call = MagicMock(return_value={
        "req_id": "r3",
        "tools": [
            {
                "name": "t1",
                "description": "d",
                "params_schema": {"type": "object", "properties": {}, "required": []},
                "return_schema": None,
            },
        ],
    })
    ret2 = ns.on_client_get_tools("a1", {"computer": "c1", "req_id": "r3", "robot_id": "a1"})
    assert isinstance(ret2, dict) and ret2["req_id"] == "r3" and isinstance(ret2.get("tools"), list)
    ns.call.assert_called_once()
