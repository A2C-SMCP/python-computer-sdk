# -*- coding: utf-8 -*-
# filename: test_sync_agent_e2e.py
# @Time    : 2025/10/05 15:47
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
中文: 同步 Agent 模块的端到端测试：基于真实 HTTP 服务与真实 SMCPAgentClient，验证核心功能流。
English: End-to-end tests for the Sync Agent module: real HTTP service and real SMCPAgentClient validating core functionality flows.
"""

from __future__ import annotations

import time

import pytest

from a2c_smcp.agent import DefaultAgentAuthProvider, SMCPAgentClient
from a2c_smcp.smcp import (
    JOIN_OFFICE_EVENT,
    LEAVE_OFFICE_EVENT,
    SMCP_NAMESPACE,
    EnterOfficeNotification,
    LeaveOfficeNotification,
    SMCPTool,
    UpdateMCPConfigNotification,
)

pytestmark = pytest.mark.e2e


def _wait_until(cond, timeout: float = 2.0, step: float = 0.01) -> bool:
    """
    中文: 简易等待辅助函数，直到条件满足或超时。
    English: Simple wait helper until condition met or timeout.
    """
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        time.sleep(step)
    return cond()


class MockEventHandler:
    """
    中文: 测试用的事件处理器，记录所有事件
    English: Test event handler that records all events
    """

    def __init__(self):
        self.enter_office_events: list[EnterOfficeNotification] = []
        self.leave_office_events: list[LeaveOfficeNotification] = []
        self.update_config_events: list[UpdateMCPConfigNotification] = []
        self.tools_received_events: list[tuple[str, list[SMCPTool]]] = []

    def on_computer_enter_office(self, data: EnterOfficeNotification) -> None:
        self.enter_office_events.append(data)

    def on_computer_leave_office(self, data: LeaveOfficeNotification) -> None:
        self.leave_office_events.append(data)

    def on_computer_update_config(self, data: UpdateMCPConfigNotification) -> None:
        self.update_config_events.append(data)

    def on_tools_received(self, computer: str, tools: list[SMCPTool]) -> None:
        self.tools_received_events.append((computer, tools))


def test_sync_agent_connect_and_join_office(server_endpoint: str, mock_computer_client):
    """
    中文:
      - 验证 Agent 客户端连接到服务器
      - 验证 Agent 加入办公室
      - 验证 Computer 先加入后 Agent 能收到通知
    English:
      - Verify Agent client connects to server
      - Verify Agent joins office
      - Verify Agent receives notification when Computer joins first
    """
    # 创建认证提供者 / Create auth provider
    auth_provider = DefaultAgentAuthProvider(
        agent_id="test-agent-1",
        office_id="office-sync-1",
    )

    # 创建事件处理器 / Create event handler
    event_handler = MockEventHandler()

    # 创建 Agent 客户端 / Create Agent client
    agent_client = SMCPAgentClient(
        auth_provider=auth_provider,
        event_handler=event_handler,
    )

    try:
        # 连接到服务器 / Connect to server
        agent_client.connect_to_server(server_endpoint)

        # 等待连接稳定 / Wait for connection to stabilize
        time.sleep(0.1)

        # Agent 加入办公室 / Agent joins office
        ok, err = agent_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "agent", "name": "test-agent-1", "office_id": "office-sync-1"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )
        assert ok is True
        assert err is None

        # Computer 加入办公室 / Computer joins office
        ok, err = mock_computer_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "computer", "name": "test-computer-1", "office_id": "office-sync-1"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )
        assert ok is True
        assert err is None

        # 等待事件处理 / Wait for event processing
        assert _wait_until(lambda: len(event_handler.enter_office_events) >= 1, timeout=3)

        # 验证收到的事件 / Verify received events
        assert len(event_handler.enter_office_events) >= 1
        enter_event = event_handler.enter_office_events[0]
        assert enter_event["office_id"] == "office-sync-1"
        assert "computer" in enter_event

        # 验证自动获取工具列表 / Verify automatic tools fetching
        assert _wait_until(lambda: len(event_handler.tools_received_events) >= 1, timeout=3)
        computer_id, tools = event_handler.tools_received_events[0]
        assert len(tools) == 2  # echo and add
        assert tools[0]["name"] == "echo"
        assert tools[1]["name"] == "add"

    finally:
        # 清理连接 / Cleanup connection
        agent_client.disconnect()


def test_sync_agent_tool_call(server_endpoint: str, mock_computer_client):
    """
    中文:
      - 验证 Agent 调用 Computer 工具
      - 验证工具调用返回正确结果
    English:
      - Verify Agent calls Computer tools
      - Verify tool call returns correct results
    """
    auth_provider = DefaultAgentAuthProvider(
        agent_id="test-agent-2",
        office_id="office-sync-2",
    )

    agent_client = SMCPAgentClient(
        auth_provider=auth_provider,
        event_handler=None,
    )

    try:
        # 连接并加入办公室 / Connect and join office
        agent_client.connect_to_server(server_endpoint)
        time.sleep(0.1)

        agent_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "agent", "name": "test-agent-2", "office_id": "office-sync-2"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # Computer 加入办公室 / Computer joins office
        mock_computer_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "computer", "name": "test-computer-2", "office_id": "office-sync-2"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # 等待连接稳定 / Wait for connection to stabilize
        time.sleep(0.2)

        # 获取 Computer SID / Get Computer SID
        computer_sid = mock_computer_client.get_sid(namespace=SMCP_NAMESPACE)

        # 调用 echo 工具 / Call echo tool
        result = agent_client.emit_tool_call(
            computer=computer_sid,
            tool_name="echo",
            params={"message": "Hello, World!"},
            timeout=5,
        )

        # 验证结果 / Verify result
        assert result.isError is False
        assert len(result.content) == 1
        assert "Echo: Hello, World!" in result.content[0].text

        # 调用 add 工具 / Call add tool
        result = agent_client.emit_tool_call(
            computer=computer_sid,
            tool_name="add",
            params={"a": 10, "b": 20},
            timeout=5,
        )

        # 验证结果 / Verify result
        assert result.isError is False
        assert len(result.content) == 1
        assert "Result: 30" in result.content[0].text

    finally:
        agent_client.disconnect()


def test_sync_agent_get_tools_and_desktop(server_endpoint: str, mock_computer_client):
    """
    中文:
      - 验证 Agent 获取 Computer 工具列表
      - 验证 Agent 获取 Computer 桌面信息
    English:
      - Verify Agent gets Computer tools list
      - Verify Agent gets Computer desktop info
    """
    auth_provider = DefaultAgentAuthProvider(
        agent_id="test-agent-3",
        office_id="office-sync-3",
    )

    agent_client = SMCPAgentClient(
        auth_provider=auth_provider,
        event_handler=None,
    )

    try:
        # 连接并加入办公室 / Connect and join office
        agent_client.connect_to_server(server_endpoint)
        time.sleep(0.1)

        agent_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "agent", "name": "test-agent-3", "office_id": "office-sync-3"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # Computer 加入办公室 / Computer joins office
        mock_computer_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "computer", "name": "test-computer-3", "office_id": "office-sync-3"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        time.sleep(0.2)

        # 获取 Computer SID / Get Computer SID
        computer_sid = mock_computer_client.get_sid(namespace=SMCP_NAMESPACE)

        # 获取工具列表 / Get tools list
        tools_response = agent_client.get_tools_from_computer(computer_sid, timeout=5)

        # 验证工具列表 / Verify tools list
        assert tools_response["req_id"] is not None
        assert len(tools_response["tools"]) == 2
        assert tools_response["tools"][0]["name"] == "echo"
        assert tools_response["tools"][1]["name"] == "add"

        # 获取桌面信息 / Get desktop info
        desktop_response = agent_client.get_desktop_from_computer(computer_sid, timeout=5)

        # 验证桌面信息 / Verify desktop info
        assert desktop_response["req_id"] is not None
        assert len(desktop_response["desktops"]) == 2
        assert "window://1" in desktop_response["desktops"]
        assert "window://2" in desktop_response["desktops"]

    finally:
        agent_client.disconnect()


def test_sync_agent_computer_leave_notification(server_endpoint: str, mock_computer_client):
    """
    中文:
      - 验证 Computer 离开办公室时 Agent 收到通知
    English:
      - Verify Agent receives notification when Computer leaves office
    """
    auth_provider = DefaultAgentAuthProvider(
        agent_id="test-agent-4",
        office_id="office-sync-4",
    )

    event_handler = MockEventHandler()

    agent_client = SMCPAgentClient(
        auth_provider=auth_provider,
        event_handler=event_handler,
    )

    try:
        # 连接并加入办公室 / Connect and join office
        agent_client.connect_to_server(server_endpoint)
        time.sleep(0.1)

        agent_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "agent", "name": "test-agent-4", "office_id": "office-sync-4"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # Computer 加入办公室 / Computer joins office
        mock_computer_client.call(
            JOIN_OFFICE_EVENT,
            {"role": "computer", "name": "test-computer-4", "office_id": "office-sync-4"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # 等待加入事件和工具获取完成 / Wait for join event and tools fetching
        assert _wait_until(lambda: len(event_handler.enter_office_events) >= 1, timeout=3)
        # 等待工具列表自动获取完成 / Wait for automatic tools fetching to complete
        assert _wait_until(lambda: len(event_handler.tools_received_events) >= 1, timeout=3)

        # Computer 离开办公室 / Computer leaves office
        mock_computer_client.call(
            LEAVE_OFFICE_EVENT,
            {"office_id": "office-sync-4"},
            namespace=SMCP_NAMESPACE,
            timeout=5,
        )

        # 等待离开事件 / Wait for leave event
        assert _wait_until(lambda: len(event_handler.leave_office_events) >= 1, timeout=3)

        # 验证离开事件 / Verify leave event
        leave_event = event_handler.leave_office_events[0]
        assert leave_event["office_id"] == "office-sync-4"
        assert "computer" in leave_event

    finally:
        agent_client.disconnect()
