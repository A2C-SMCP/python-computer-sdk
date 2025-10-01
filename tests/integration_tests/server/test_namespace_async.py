# -*- coding: utf-8 -*-
# filename: test_namespace_async.py
# @Time    : 2025/09/30 23:20
# @Author  : A2C-SMCP
# @Software: PyCharm
"""
中文：针对 `a2c_smcp/server/namespace.py` 的异步命名空间集成测试。
English: Integration tests for async SMCPNamespace in `a2c_smcp/server/namespace.py`.

说明：
- 复用全局 fixtures：`socketio_server`, `basic_server_port`。
- 服务器端命名空间来自 `tests/integration_tests/mock_socketio_server.py` 的 `MockComputerServerNamespace`，不做修改。
- 客户端使用 socketio.AsyncClient 直接与服务端交互，验证服务端行为。
"""

import asyncio
from typing import Literal

import pytest
from mcp.types import CallToolResult, TextContent
from socketio import AsyncClient

from a2c_smcp.smcp import (
    ENTER_OFFICE_NOTIFICATION,
    GET_TOOLS_EVENT,
    JOIN_OFFICE_EVENT,
    LEAVE_OFFICE_EVENT,
    LEAVE_OFFICE_NOTIFICATION,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_CONFIG_EVENT,
    EnterOfficeReq,
    GetToolsReq,
    UpdateMCPConfigNotification,
)


async def _join_office(client: AsyncClient, role: Literal["computer", "agent"], office_id: str, name: str) -> None:
    payload: EnterOfficeReq = {"role": role, "office_id": office_id, "name": name}
    ok, err = await client.call(JOIN_OFFICE_EVENT, payload, namespace=SMCP_NAMESPACE)
    assert ok and err is None


@pytest.mark.asyncio
async def test_enter_and_broadcast(socketio_server, basic_server_port: int):
    """
    中文：Agent 先入场，Computer 后入场，服务端应广播 ENTER_OFFICE_NOTIFICATION 给同房间的 Agent。
    English: Agent first, Computer then; server should broadcast ENTER_OFFICE_NOTIFICATION to Agent in same room.
    """
    agent = AsyncClient()
    computer = AsyncClient()

    enter_events: list[dict] = []

    @agent.on(ENTER_OFFICE_NOTIFICATION, namespace=SMCP_NAMESPACE)
    async def _on_enter(data: dict):
        enter_events.append(data)

    # 连接并让 Agent 入场
    await agent.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    office_id = "office-async-1"
    await _join_office(agent, role="agent", office_id=office_id, name="robot-A")

    # 连接并让 Computer 入场
    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-A")

    # 等待广播
    await asyncio.sleep(0.2)

    assert enter_events, "Agent 应收到 ENTER_OFFICE_NOTIFICATION"

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_leave_and_broadcast(socketio_server, basic_server_port: int):
    """
    中文：Computer 离开办公室，服务端应广播 LEAVE_OFFICE_NOTIFICATION 给房间内其他客户端。
    English: When Computer leaves, server should broadcast LEAVE_OFFICE_NOTIFICATION to others in the room.
    """
    agent = AsyncClient()
    computer = AsyncClient()

    leave_events: list[dict] = []

    @agent.on(LEAVE_OFFICE_NOTIFICATION, namespace=SMCP_NAMESPACE)
    async def _on_leave(data: dict):
        leave_events.append(data)

    await agent.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    office_id = "office-async-2"
    await _join_office(agent, role="agent", office_id=office_id, name="robot-B")

    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-B")

    # 通过 server:leave_office 离开
    ok, err = await computer.call(
        LEAVE_OFFICE_EVENT,
        {"office_id": office_id},
        namespace=SMCP_NAMESPACE,
    )
    assert ok and err is None

    await asyncio.sleep(0.2)
    assert leave_events, "Agent 应收到 LEAVE_OFFICE_NOTIFICATION"

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_tool_call_roundtrip(socketio_server, basic_server_port: int):
    """
    中文：Agent 发起 client:tool_call，服务端转发至目标 Computer，并将其 ACK 作为结果返回。
    English: Agent calls client:tool_call; server forwards to Computer and returns ACK result.
    """
    agent = AsyncClient()
    computer = AsyncClient()

    await agent.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    office_id = "office-async-3"
    await _join_office(agent, role="agent", office_id=office_id, name="robot-C")

    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-C")

    @computer.on(TOOL_CALL_EVENT, namespace=SMCP_NAMESPACE)
    async def _on_tool_call(data: dict):
        return CallToolResult(
            isError=False,
            content=[TextContent(type="text", text="ok from computer")],
        ).model_dump(mode="json")

    # 使用 agent 直接调用服务端事件（测试服务端转发与聚合）
    res = await agent.call(
        TOOL_CALL_EVENT,
        {
            "robot_id": agent.get_sid(SMCP_NAMESPACE),
            "computer": computer.get_sid(SMCP_NAMESPACE),
            "tool_name": "echo",
            "params": {"text": "hi"},
            "req_id": "req-001",
            "timeout": 5,
        },
        namespace=SMCP_NAMESPACE,
    )

    assert isinstance(res, dict)
    assert res.get("isError") is False
    assert any(c.get("text") == "ok from computer" for c in res.get("content", []))

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_get_tools_success_same_office(socketio_server, basic_server_port: int):
    """
    中文：Agent 与 Computer 同房间，调用 client:get_tools，服务端通过 call 获取并返回工具列表。
    English: Agent and Computer in same room; client:get_tools returns tools list via server call.
    """
    agent = AsyncClient()
    computer = AsyncClient()

    await agent.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    office_id = "office-async-4"
    await _join_office(agent, role="agent", office_id=office_id, name="robot-D")

    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-D")

    tools_ready = asyncio.Event()

    @computer.on(GET_TOOLS_EVENT, namespace=SMCP_NAMESPACE)
    async def _on_get_tools(data: GetToolsReq):
        tools_ready.set()
        return {
            "tools": [
                {
                    "name": "echo",
                    "description": "echo text",
                    "params_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
                    "return_schema": None,
                },
            ],
            "req_id": data["req_id"],
        }

    res = await agent.call(
        GET_TOOLS_EVENT,
        {
            "computer": computer.get_sid(SMCP_NAMESPACE),
            "robot_id": agent.get_sid(SMCP_NAMESPACE),
            "req_id": "req-002",
        },
        namespace=SMCP_NAMESPACE,
    )

    await asyncio.wait_for(tools_ready.wait(), timeout=3)

    assert isinstance(res, dict)
    assert res.get("tools") and res["tools"][0]["name"] == "echo"

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_update_config_broadcast(socketio_server, basic_server_port: int):
    """
    中文：Computer 触发 server:update_config，服务端向同房间广播 UPDATE_CONFIG_NOTIFICATION。
    English: Computer emits server:update_config; server broadcasts UPDATE_CONFIG_NOTIFICATION.
    """
    agent = AsyncClient()
    computer = AsyncClient()

    update_events: list[UpdateMCPConfigNotification] = []

    @agent.on("notify:update_config", namespace=SMCP_NAMESPACE)
    async def _on_update(data: UpdateMCPConfigNotification) -> None:
        update_events.append(data)

    await agent.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    office_id = "office-async-5"
    await _join_office(agent, role="agent", office_id=office_id, name="robot-E")

    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-E")

    # 由 Computer 触发 server:update_config
    await computer.emit(
        UPDATE_CONFIG_EVENT,
        {"computer": computer.get_sid(SMCP_NAMESPACE)},
        namespace=SMCP_NAMESPACE,
    )

    await asyncio.sleep(0.2)
    assert update_events and update_events[0]["computer"] == computer.get_sid(SMCP_NAMESPACE)

    await agent.disconnect()
    await computer.disconnect()
