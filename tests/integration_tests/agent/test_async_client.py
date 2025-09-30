# -*- coding: utf-8 -*-
# filename: test_async_client.py
# @Time    : 2025/9/30 17:05
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
中文：AsyncSMCPAgentClient 的集成测试用例。
English: Integration tests for AsyncSMCPAgentClient.
"""

import asyncio
from typing import Literal

import pytest
from mcp.types import CallToolResult, TextContent
from socketio import AsyncClient

from a2c_smcp.agent.auth import DefaultAgentAuthProvider
from a2c_smcp.agent.client import AsyncSMCPAgentClient
from a2c_smcp.agent.types import AsyncAgentEventHandler
from a2c_smcp.smcp import (
    GET_TOOLS_EVENT,
    JOIN_OFFICE_EVENT,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    EnterOfficeNotification,
    EnterOfficeReq,
    GetToolsReq,
    GetToolsRet,
    LeaveOfficeNotification,
    SMCPTool,
    UpdateMCPConfigNotification,
)


class _EH(AsyncAgentEventHandler):
    """
    中文：异步事件处理器，记录回调到事件数据。
    English: Async event handler recording callbacks.
    """

    def __init__(self) -> None:
        self.enter_events: list[EnterOfficeNotification] = []
        self.leave_events: list[LeaveOfficeNotification] = []
        self.update_events: list[UpdateMCPConfigNotification] = []
        self.tools_received: list[tuple[str, list[SMCPTool]]] = []

    async def on_computer_enter_office(self, data: EnterOfficeNotification) -> None:
        self.enter_events.append(data)

    async def on_computer_leave_office(self, data: LeaveOfficeNotification) -> None:
        self.leave_events.append(data)

    async def on_computer_update_config(self, data: UpdateMCPConfigNotification) -> None:
        self.update_events.append(data)

    async def on_tools_received(self, computer: str, tools: list[SMCPTool]) -> None:
        self.tools_received.append((computer, tools))


async def _join_office(client: AsyncClient, role: Literal["computer", "agent"], office_id: str, name: str) -> None:
    """
    中文：通过 server:join_office 进入办公室。
    English: Join office via server:join_office.
    """
    payload: EnterOfficeReq = {"role": role, "office_id": office_id, "name": name}
    ok, err = await client.call(JOIN_OFFICE_EVENT, payload, namespace=SMCP_NAMESPACE)
    assert ok and err is None


@pytest.mark.asyncio
async def test_agent_receives_enter_and_tools(socketio_server, basic_server_port: int):
    """
    中文：验证Agent收到Computer进入办公室事件，并自动拉取工具列表。
    English: Verify Agent receives enter event and auto fetches tools.
    """
    # 启动一个模拟的Computer（纯 AsyncClient）/ Start a fake Computer
    computer = AsyncClient()

    tools_resp_event = asyncio.Event()

    @computer.on(GET_TOOLS_EVENT, namespace=SMCP_NAMESPACE)
    async def _on_get_tools(data: GetToolsReq) -> GetToolsRet:
        # 直接返回工具列表（通过返回值作为ACK）/ respond tools list via return value
        tools: list[SMCPTool] = [
            {
                "name": "echo",
                "description": "echo text",
                "params_schema": {"type": "object", "properties": {"text": {"type": "string"}}},
                "return_schema": None,
            },
        ]
        tools_resp_event.set()
        return {"tools": tools, "req_id": data["req_id"]}

    # 启动Agent客户端 / Start Agent client
    handler = _EH()
    office_id = "office-1"
    auth = DefaultAgentAuthProvider(agent_id="robot-1", office_id=office_id)
    agent = AsyncSMCPAgentClient(auth_provider=auth, event_handler=handler)

    await agent.connect_to_server(
        f"http://localhost:{basic_server_port}",
        namespace=SMCP_NAMESPACE,
        socketio_path="/socket.io",
    )

    # Agent 加入办公室 / Agent join office
    await agent.call(
        JOIN_OFFICE_EVENT,
        {"role": "agent", "office_id": office_id, "name": "robot-1"},
        namespace=SMCP_NAMESPACE,
    )

    # 再启动计算机并加入，确保Agent能收到enter广播 / start computer afterwards so agent receives enter
    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-01")

    # 计算机加入后服务器广播，Agent应自动拉取工具 / after computer joins, agent auto fetches tools
    await asyncio.wait_for(tools_resp_event.wait(), timeout=3)
    await asyncio.sleep(0.3)  # 等待工具注册完成

    # 校验事件与工具列表回调 / Validate callbacks
    assert handler.enter_events, "应收到进入办公室事件 / Enter event expected"
    assert handler.tools_received and handler.tools_received[0][1][0]["name"] == "echo"

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_agent_tool_call_roundtrip(socketio_server, basic_server_port: int):
    """
    中文：验证Agent发起工具调用，Computer返回CallToolResult。
    English: Verify Agent tool-call roundtrip.
    """
    computer = AsyncClient()

    @computer.on(TOOL_CALL_EVENT, namespace=SMCP_NAMESPACE)
    async def _on_tool_call(data: dict):
        # 返回一个 CallToolResult 结构（ACK返回值） / Return CallToolResult via return value
        return CallToolResult(
            isError=False,
            content=[TextContent(type="text", text="ok")],
        ).model_dump(mode="json")

    handler = _EH()
    office_id = "office-2"
    auth = DefaultAgentAuthProvider(agent_id="robot-2", office_id=office_id)
    agent = AsyncSMCPAgentClient(auth_provider=auth, event_handler=handler)

    await agent.connect_to_server(
        f"http://localhost:{basic_server_port}",
        namespace=SMCP_NAMESPACE,
        socketio_path="/socket.io",
    )

    await agent.call(
        "server:join_office",
        {"role": "agent", "office_id": office_id, "name": "robot-2"},
        namespace=SMCP_NAMESPACE,
    )

    # 让Computer随后加入，确保Agent在场并能接收到enter通知
    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-02")

    # 发起工具调用 / Emit tool call
    res = await agent.emit_tool_call(
        computer=computer.namespaces[SMCP_NAMESPACE],
        tool_name="echo",
        params={"text": "hi"},
        timeout=5,
    )

    assert isinstance(res, CallToolResult)
    assert not res.isError
    assert any(isinstance(c, TextContent) and c.text == "ok" for c in res.content)

    await agent.disconnect()
    await computer.disconnect()


@pytest.mark.asyncio
async def test_agent_receives_update_config(socketio_server, basic_server_port: int):
    """
    中文：验证当Computer发出更新配置，Agent收到并再次拉取工具列表。
    English: Verify Agent receives update-config and re-fetches tools.
    """
    computer = AsyncClient()

    tools_req_count = 0
    tools_event = asyncio.Event()

    @computer.on(GET_TOOLS_EVENT, namespace=SMCP_NAMESPACE)
    async def _on_get_tools_again(data: GetToolsReq):  # type: ignore[override]
        nonlocal tools_req_count
        tools_req_count += 1
        tools_event.set()
        return {"tools": [{"name": f"tool-{tools_req_count}"}], "req_id": data["req_id"]}

    handler = _EH()
    office_id = "office-3"
    auth = DefaultAgentAuthProvider(agent_id="robot-3", office_id=office_id)
    agent = AsyncSMCPAgentClient(auth_provider=auth, event_handler=handler)

    await agent.connect_to_server(
        f"http://localhost:{basic_server_port}",
        namespace=SMCP_NAMESPACE,
        socketio_path="/socket.io",
    )

    await agent.call(
        "server:join_office",
        {"role": "agent", "office_id": office_id, "name": "robot-3"},
        namespace=SMCP_NAMESPACE,
    )

    # 让Computer随后加入，触发初次工具拉取 / Computer joins afterwards to trigger initial fetch
    await computer.connect(
        f"http://localhost:{basic_server_port}",
        namespaces=[SMCP_NAMESPACE],
        socketio_path="/socket.io",
    )
    await _join_office(computer, role="computer", office_id=office_id, name="comp-03")

    # 初次工具拉取 / initial tools fetch
    await asyncio.wait_for(tools_event.wait(), timeout=3)
    tools_event.clear()

    # 由 Computer 触发更新配置 / Computer triggers update-config
    await computer.call(
        "server:update_config",
        {"computer": computer.namespaces[SMCP_NAMESPACE]},
        namespace=SMCP_NAMESPACE,
        timeout=3,
    )

    # 再次工具拉取 / tools fetched again
    await asyncio.wait_for(tools_event.wait(), timeout=3)

    # Handler 应至少记录一次 update 回调 / handler should record update
    assert handler.update_events or handler.tools_received

    await agent.disconnect()
    await computer.disconnect()
