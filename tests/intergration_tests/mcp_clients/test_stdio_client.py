# -*- coding: utf-8 -*-
# filename: test_stdio_client.py
# @Time    : 2025/8/19 17:00
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
# filename: test_std_mcp_client.py
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from mcp import StdioServerParameters
from mcp.types import CallToolResult
from transitions import MachineError

from a2c_smcp_cc.mcp_clients.stdio_client import StdioMCPClient

# 获取当前脚本目录作为工作目录
TEST_DIR: Path = Path(__file__).parent.parent

# 定义示例 MCP Server 的路径
MCP_SERVER_SCRIPT: Path = TEST_DIR / "mcp_servers" / "direct_execution.py"


@pytest.fixture
def stdio_params() -> StdioServerParameters:
    """提供 StdioServerParameters 配置 Provide StdioServerParameters config"""
    return StdioServerParameters(command=sys.executable, args=[str(MCP_SERVER_SCRIPT)])


@pytest.fixture
def track_state() -> tuple[Callable[[str, str], None], list[tuple[str, str]]]:
    """跟踪状态变化的辅助函数 Helper function to track state changes"""
    state_history: list[tuple[str, str]] = []

    def callback(from_state: str, to_state: str) -> None:
        state_history.append((from_state, to_state))

    return callback, state_history


@pytest.mark.asyncio
async def test_state_transitions(
    stdio_params: StdioServerParameters, track_state: tuple[Callable[[str, str], None], list[tuple[str, str]]]
) -> None:
    """测试客户端状态转换 Test client state transitions"""
    callback, history = track_state

    client: StdioMCPClient = StdioMCPClient(stdio_params, state_change_callback=callback)

    # 初始状态检查 Initial state check
    assert client.state == "initialized"

    # 连接服务器 Connect to server
    await client.aconnect()
    assert client.state == "connected"
    assert ("initialized", "connected") in history

    # 断开连接 Disconnect
    await client.adisconnect()
    assert client.state == "disconnected"
    assert ("connected", "disconnected") in history

    # 重新初始化 Re-initialize
    await client.ainitialize()
    assert client.state == "initialized"
    assert ("disconnected", "initialized") in history


@pytest.mark.asyncio
async def test_list_tools(stdio_params: StdioServerParameters) -> None:
    """测试获取工具列表功能 Test getting tool list"""
    client: StdioMCPClient = StdioMCPClient(stdio_params)
    await client.aconnect()

    tools = await client.list_tools()

    # 验证工具列表 Validate tool list
    assert len(tools) == 1
    assert tools[0].name == "hello"
    assert tools[0].description == "Say hello to someone."

    # 清理客户端 Cleanup client
    await client.adisconnect()


@pytest.mark.asyncio
async def test_call_tool_success(stdio_params: StdioServerParameters) -> None:
    """测试成功调用工具 Test successful tool call"""
    client: StdioMCPClient = StdioMCPClient(stdio_params)
    await client.aconnect()

    # 使用默认参数调用 Call with default params
    result_default: CallToolResult = await client.call_tool("hello", {})
    assert isinstance(result_default, CallToolResult)
    assert not result_default.isError
    assert result_default.content[0].text == "Hello, World!"

    # 使用自定义参数调用 Call with custom params
    result_custom: CallToolResult = await client.call_tool("hello", {"name": "Alice"})
    assert not result_custom.isError
    assert result_custom.content[0].text == "Hello, Alice!"

    # 清理客户端 Cleanup client
    await client.adisconnect()


@pytest.mark.asyncio
async def test_call_tool_failure(stdio_params: StdioServerParameters) -> None:
    """测试工具调用失败场景 Test tool call failure"""
    client: StdioMCPClient = StdioMCPClient(stdio_params)
    await client.aconnect()

    # 调用不存在的工具 Call non-existent tool
    result: CallToolResult = await client.call_tool("nonexistent_tool", {})
    assert result.isError, "调用不存在的工具应该失败 Calling non-existent tool should fail"

    # 调用工具但参数错误 Call tool with wrong params
    result = await client.call_tool("hello", {"invalid_param": "value"})
    assert isinstance(result, CallToolResult)
    # 虽然参数错误，但由于mcp server有一定的容错能力，可以返回成功 Even with wrong params, mcp server may return success
    assert not result.isError
    assert result.content[0].text == "Hello, World!"

    # 清理客户端 Cleanup client
    await client.adisconnect()


@pytest.mark.asyncio
async def test_async_session_property(stdio_params: StdioServerParameters) -> None:
    """测试 async_session 属性 Test async_session property"""
    client: StdioMCPClient = StdioMCPClient(stdio_params)

    # 未连接状态下会话为空 Session is None when not connected
    assert client._async_session is None

    # 在未连接状态下访问 @async_property async_session 会触发自动连接，因此会话不为空 Accessing async_session triggers auto-connect
    assert (await client.async_session) is not None

    with pytest.raises(MachineError) as e:
        # 在连接状态下访问 Access when connected
        await client.aconnect()

    assert "Can't trigger event aconnect from state connected!" in str(e.value)
    session = await client.async_session
    assert session is not None

    # 清理客户端 Cleanup client
    await client.adisconnect()


@pytest.mark.asyncio
async def test_invalid_state_operations(stdio_params: StdioServerParameters) -> None:
    """测试在无效状态下执行操作 Test operations in invalid state"""
    client: StdioMCPClient = StdioMCPClient(stdio_params)

    # 在未连接状态下调用工具 Call tool when not connected
    with pytest.raises(ConnectionError):
        await client.call_tool("hello", {})

    # 在未连接状态下获取工具列表 Get tool list when not connected
    with pytest.raises(ConnectionError):
        await client.list_tools()

    # 尝试在未连接状态下断开 Try disconnect when not connected
    with pytest.raises(MachineError) as e:
        await client.adisconnect()
    assert "Can't trigger event adisconnect from state initialized!" in str(e.value)


@pytest.mark.asyncio
async def test_error_recovery(
    stdio_params: StdioServerParameters, track_state: tuple[Callable[[str, str], None], list[tuple[str, str]]]
) -> None:
    """测试错误状态恢复 Test error recovery"""
    callback, history = track_state

    client: StdioMCPClient = StdioMCPClient(stdio_params, state_change_callback=callback)
    await client.aconnect()

    # 强制进入错误状态 Force error state
    await client.aerror()
    assert client.state == "error"
    assert any(from_state == "connected" and to_state == "error" for from_state, to_state in history)

    # 从错误状态恢复 Recover from error
    await client.ainitialize()
    assert client.state == "initialized"
    assert ("error", "initialized") in history

    # 尝试重新连接 Try reconnect
    await client.aconnect()
    assert client.state == "connected"

    # 清理 Cleanup
    await client.adisconnect()
