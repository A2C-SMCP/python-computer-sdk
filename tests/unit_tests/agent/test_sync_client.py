"""
* 文件名: test_sync_client
* 作者: JQQ
* 创建日期: 2025/9/30
* 最后修改日期: 2025/9/30
* 版权: 2023 JQQ. All rights reserved.
* 依赖: pytest, unittest.mock
* 描述: 同步Agent客户端测试用例 / Synchronous Agent client test cases
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from mcp.types import CallToolResult

from a2c_smcp.agent.auth import DefaultAgentAuthProvider
from a2c_smcp.agent.sync_client import SMCPAgentClient
from a2c_smcp.smcp import (
    CANCEL_TOOL_CALL_EVENT,
    SMCP_NAMESPACE,
    EnterOfficeNotification,
    LeaveOfficeNotification,
    SMCPTool,
    UpdateMCPConfigNotification,
)


class MockEventHandler:
    """模拟事件处理器 / Mock event handler"""

    def __init__(self) -> None:
        self.enter_office_calls: list[EnterOfficeNotification] = []
        self.leave_office_calls: list[LeaveOfficeNotification] = []
        self.update_config_calls: list[UpdateMCPConfigNotification] = []
        self.tools_received_calls: list[tuple[str, list[SMCPTool]]] = []

    def on_computer_enter_office(self, data: EnterOfficeNotification) -> None:
        self.enter_office_calls.append(data)

    def on_computer_leave_office(self, data: LeaveOfficeNotification) -> None:
        self.leave_office_calls.append(data)

    def on_computer_update_config(self, data: UpdateMCPConfigNotification) -> None:
        self.update_config_calls.append(data)

    def on_tools_received(self, computer: str, tools: list[SMCPTool]) -> None:
        self.tools_received_calls.append((computer, tools))


class TestSMCPAgentClient:
    """测试同步SMCP Agent客户端 / Test synchronous SMCP Agent client"""

    @pytest.fixture
    def auth_provider(self) -> DefaultAgentAuthProvider:
        """创建认证提供者 / Create authentication provider"""
        return DefaultAgentAuthProvider(
            agent_id="test_agent",
            office_id="test_office",
            api_key="test_key",
        )

    @pytest.fixture
    def event_handler(self) -> MockEventHandler:
        """创建事件处理器 / Create event handler"""
        return MockEventHandler()

    @pytest.fixture
    def client(self, auth_provider: DefaultAgentAuthProvider, event_handler: MockEventHandler) -> SMCPAgentClient:
        """创建客户端实例 / Create client instance"""
        return SMCPAgentClient(auth_provider=auth_provider, event_handler=event_handler)

    def test_init(self, client: SMCPAgentClient) -> None:
        """测试客户端初始化 / Test client initialization"""
        assert client.auth_provider is not None
        assert client.event_handler is not None

    def test_validate_emit_event_notify(self, client: SMCPAgentClient) -> None:
        """测试验证notify事件被拒绝 / Test validate notify events are rejected"""
        with pytest.raises(ValueError, match="AgentClient不允许使用notify"):
            client.emit("notify:test_event")

    def test_validate_emit_event_agent(self, client: SMCPAgentClient) -> None:
        """测试验证agent事件被拒绝 / Test validate agent events are rejected"""
        with pytest.raises(ValueError, match="AgentClient不允许发起agent"):
            client.emit("agent:test_event")

    def test_validate_emit_event_valid(self, client: SMCPAgentClient) -> None:
        """测试验证有效事件通过 / Test validate valid events pass"""
        with patch.object(client, 'emit', wraps=client.emit) as mock_emit:
            # 模拟父类emit方法
            # Mock parent class emit method
            with patch('socketio.Client.emit'):
                client.emit("client:test_event")
                mock_emit.assert_called_once()

    @patch('socketio.Client.call')
    def test_emit_tool_call_success(self, mock_call: MagicMock, client: SMCPAgentClient) -> None:
        """测试成功的工具调用 / Test successful tool call"""
        # 模拟成功响应
        # Mock successful response
        mock_response = {
            "content": [{"text": "Success", "type": "text"}],
            "isError": False,
        }
        mock_call.return_value = mock_response

        result = client.emit_tool_call(
            computer="test_computer",
            tool_name="test_tool",
            params={"param1": "value1"},
            timeout=30,
        )

        assert isinstance(result, CallToolResult)
        assert not result.isError
        mock_call.assert_called_once()

    @patch('socketio.Client.call')
    @patch('socketio.Client.emit')
    def test_emit_tool_call_timeout(self, mock_emit: MagicMock, mock_call: MagicMock, client: SMCPAgentClient) -> None:
        """测试工具调用超时 / Test tool call timeout"""
        # 模拟超时异常
        # Mock timeout exception
        mock_call.side_effect = TimeoutError("Timeout")

        result = client.emit_tool_call(
            computer="test_computer",
            tool_name="test_tool",
            params={"param1": "value1"},
            timeout=30,
        )

        assert isinstance(result, CallToolResult)
        assert result.isError
        assert "超时" in result.content[0].text  # type: ignore

        # 验证发送了取消请求
        # Verify cancel request was sent
        mock_emit.assert_called_once()
        args, kwargs = mock_emit.call_args
        assert args[0] == CANCEL_TOOL_CALL_EVENT
        assert args[2] == SMCP_NAMESPACE  # namespace 是第三个位置参数

    @patch('socketio.Client.call')
    def test_get_tools_from_computer_success(self, mock_call: MagicMock, client: SMCPAgentClient) -> None:
        """测试成功获取工具列表 / Test successful get tools list"""
        # 模拟工具响应
        # Mock tools response
        req_id = uuid.uuid4().hex
        mock_response = {
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    "params_schema": {},
                    "return_schema": None,
                },
            ],
            "req_id": req_id,
        }

        with patch('uuid.uuid4') as mock_uuid:
            mock_uuid.return_value.hex = req_id
            mock_call.return_value = mock_response

            result = client.get_tools_from_computer("test_computer")

            assert isinstance(result, dict)
            assert "tools" in result
            assert len(result["tools"]) == 1
            assert result["req_id"] == req_id

    @patch('socketio.Client.call')
    def test_get_tools_from_computer_invalid_response(self, mock_call: MagicMock, client: SMCPAgentClient) -> None:
        """测试获取工具列表响应无效 / Test get tools list invalid response"""
        # 模拟无效响应
        # Mock invalid response
        mock_response = {
            "tools": [],
            "req_id": "wrong_id",
        }
        mock_call.return_value = mock_response

        with pytest.raises(ValueError, match="Invalid response"):
            client.get_tools_from_computer("test_computer")

    def test_handle_computer_enter_office(self, client: SMCPAgentClient, event_handler: MockEventHandler) -> None:
        """测试处理Computer加入办公室事件 / Test handle Computer enter office event"""
        data: EnterOfficeNotification = {
            "office_id": "test_office",
            "computer": "test_computer",
        }

        with patch.object(client, 'get_tools_from_computer') as mock_get_tools:
            mock_get_tools.return_value = {"tools": [], "req_id": "test_req"}

            client._on_computer_enter_office(data)

            # 验证事件处理器被调用
            # Verify event handler was called
            assert len(event_handler.enter_office_calls) == 1
            assert event_handler.enter_office_calls[0] == data

            # 验证获取工具被调用
            # Verify get tools was called
            mock_get_tools.assert_called_once_with("test_computer")

    def test_handle_computer_leave_office(self, client: SMCPAgentClient, event_handler: MockEventHandler) -> None:
        """测试处理Computer离开办公室事件 / Test handle Computer leave office event"""
        data: LeaveOfficeNotification = {
            "office_id": "test_office",
            "computer": "test_computer",
        }

        client._on_computer_leave_office(data)

        # 验证事件处理器被调用
        # Verify event handler was called
        assert len(event_handler.leave_office_calls) == 1
        assert event_handler.leave_office_calls[0] == data

    def test_handle_computer_update_config(self, client: SMCPAgentClient, event_handler: MockEventHandler) -> None:
        """测试处理Computer更新配置事件 / Test handle Computer update config event"""
        data: UpdateMCPConfigNotification = {
            "computer": "test_computer",
        }

        with patch.object(client, 'get_tools_from_computer') as mock_get_tools:
            mock_get_tools.return_value = {"tools": [], "req_id": "test_req"}

            client._on_computer_update_config(data)

            # 验证事件处理器被调用
            # Verify event handler was called
            assert len(event_handler.update_config_calls) == 1
            assert event_handler.update_config_calls[0] == data

            # 验证获取工具被调用
            # Verify get tools was called
            mock_get_tools.assert_called_once_with("test_computer")

    def test_validate_office_data_valid(self, client: SMCPAgentClient) -> None:
        """测试验证有效的办公室数据 / Test validate valid office data"""
        data: EnterOfficeNotification = {
            "office_id": "test_office",
            "computer": "test_computer",
        }

        computer = client.validate_office_data(data)
        assert computer == "test_computer"

    def test_validate_office_data_invalid_office(self, client: SMCPAgentClient) -> None:
        """测试验证无效的办公室ID / Test validate invalid office ID"""
        data: EnterOfficeNotification = {
            "office_id": "wrong_office",
            "computer": "test_computer",
        }

        with pytest.raises(AssertionError, match="无效的办公室ID"):
            client.validate_office_data(data)

    def test_validate_office_data_invalid_computer(self, client: SMCPAgentClient) -> None:
        """测试验证无效的计算机ID / Test validate invalid computer ID"""
        data: EnterOfficeNotification = {
            "office_id": "test_office",
            "computer": "",
        }

        with pytest.raises(AssertionError, match="无效的计算机ID"):
            client.validate_office_data(data)
