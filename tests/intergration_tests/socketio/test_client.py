# -*- coding: utf-8 -*-
# filename: test_client.py
# @Time    : 2025/8/21 13:56
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm

import asyncio
import socket
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.types import CallToolResult, TextContent
from socketio import ASGIApp

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.socketio.client import SMCPComputerClient
from a2c_smcp_cc.socketio.smcp import GET_TOOLS_EVENT, SMCP_NAMESPACE, TOOL_CALL_EVENT, UPDATE_MCP_CONFIG_EVENT
from a2c_smcp_cc.utils.logger import logger
from tests.intergration_tests.socketio.mock_socketio_server import MockComputerServerNamespace, create_computer_test_socketio
from tests.intergration_tests.socketio.mock_uv_server import UvicornTestServer


@pytest.fixture
def basic_server_port() -> int:
    """Find an available port for the basic server."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def computer() -> Computer:
    """创建一个模拟的Computer对象"""
    mock_computer = MagicMock(spec=Computer)
    mock_computer.mcp_manager = MagicMock(spec=MCPServerManager)
    mock_computer.mcp_manager.aexecute_tool = AsyncMock(
        return_value=CallToolResult(isError=False, content=[TextContent(text="成功执行", type="text")])
    )
    mock_computer.aget_available_tools = AsyncMock(return_value=[])
    return mock_computer


@pytest.mark.asyncio
@pytest.fixture
async def computer_server(basic_server_port: int) -> AsyncGenerator[MockComputerServerNamespace, Any]:
    """启动测试服务器"""
    sio = create_computer_test_socketio()
    sio.eio.start_service_task = False
    asgi_app = ASGIApp(sio, socketio_path="/socket.io")
    server = UvicornTestServer(asgi_app, port=basic_server_port)
    await server.up()
    yield sio.namespace_handlers[SMCP_NAMESPACE]  # 返回命名空间处理器以便测试中访问
    await server.down()


@pytest.mark.asyncio
async def test_computer_join_and_leave_office(computer, computer_server: MockComputerServerNamespace, basic_server_port: int):
    """测试加入和离开办公室"""
    client = SMCPComputerClient(computer=computer)
    logger.info(f"client sid: {client.sid}")

    # 连接服务器
    await client.connect(
        f"http://localhost:{basic_server_port}",
        headers={"mock_header": "mock_value"},
        auth={"mock_header": "mock_value"},
        socketio_path="/socket.io",
        namespaces=[SMCP_NAMESPACE],
    )

    # 验证动作状态
    await asyncio.sleep(0.1)  # 等待事件处理，交出一下控制权
    logger.info(f"client sid: {client.namespaces[SMCP_NAMESPACE]}")
    assert computer_server.client_operations_record[client.namespaces[SMCP_NAMESPACE]] == ("connect", None)

    # 加入办公室
    office_id = "test_office"
    computer_name = "test_computer"
    await client.join_office(office_id, computer_name)
    await asyncio.sleep(0.1)  # 等待事件处理，交出一下控制权
    assert computer_server.client_operations_record[client.namespaces[SMCP_NAMESPACE]] == ("enter_room", office_id)

    # 验证状态
    assert client.office_id == office_id

    # 离开办公室
    await client.leave_office(office_id)
    await asyncio.sleep(0.1)  # 等待事件处理，交出一下控制权
    assert computer_server.client_operations_record[client.namespaces[SMCP_NAMESPACE]] == ("leave_room", office_id)

    # 验证状态
    assert client.office_id is None

    # 断开连接
    await client.disconnect()


@pytest.mark.asyncio
async def test_computer_receives_tool_call(computer, computer_server, basic_server_port: int):
    """测试收到工具调用请求"""
    client = SMCPComputerClient(computer=computer)
    client_connected_event = asyncio.Event()

    async def run_client():
        logger.debug("run_client")
        await client.connect(
            f"http://localhost:{basic_server_port}",
            socketio_path="/socket.io",
            headers={"mock_header": "mock_value"},
            auth={"mock_header": "mock_value"},
            namespaces=[SMCP_NAMESPACE],
        )
        await client.join_office("test_office", "test_computer")
        logger.debug("client connected and joined office")
        client_connected_event.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            ...
        finally:
            await client.disconnect()

    run_client_task = asyncio.create_task(run_client())

    # 等待客户端连接
    await client_connected_event.wait()

    # 模拟工具调用请求
    tool_call_req = {
        "computer": client.namespaces[SMCP_NAMESPACE],
        "tool_name": "test_tool",
        "params": {"param1": "value1"},
        "robot_id": "test_office",
        "req_id": "test_req_id",
        "timeout": 10,
    }

    await computer_server.emit(TOOL_CALL_EVENT, tool_call_req, to=client.namespaces[SMCP_NAMESPACE], namespace=SMCP_NAMESPACE)
    await asyncio.sleep(0.1)

    # 验证工具调用被正确处理
    assert computer.mcp_manager.aexecute_tool.called
    computer.mcp_manager.aexecute_tool.assert_called_with(tool_name="test_tool", parameters={"param1": "value1"}, timeout=10)

    # 取消客户端任务
    run_client_task.cancel()


@pytest.mark.asyncio
async def test_computer_sends_update_mcp_config(computer, computer_server, basic_server_port: int):
    """测试发送更新MCP配置事件"""
    client = SMCPComputerClient(computer=computer)

    await client.connect(
        f"http://localhost:{basic_server_port}",
        socketio_path="/socket.io",
        headers={"mock_header": "mock_value"},
        auth={"mock_header": "mock_value"},
        namespaces=[SMCP_NAMESPACE],
    )
    await client.join_office("test_office", "test_computer")

    # 发送更新MCP配置事件
    await client.update_mcp_config()

    # 等待事件处理
    await asyncio.sleep(0.1)

    assert computer_server.client_operations_record[client.namespaces[SMCP_NAMESPACE]] == (
        "server_update_mcp_config",
        {"computer": client.namespaces[SMCP_NAMESPACE]},
    )

    await client.disconnect()


@pytest.mark.asyncio
async def test_computer_handles_get_tools_request(computer, computer_server, basic_server_port: int):
    """测试处理获取工具请求"""
    client = SMCPComputerClient(computer=computer)

    await client.connect(
        f"http://localhost:{basic_server_port}",
        socketio_path="/socket.io",
        headers={"mock_header": "mock_value"},
        auth={"mock_header": "mock_value"},
        namespaces=[SMCP_NAMESPACE],
    )
    await client.join_office("test_office", "test_computer")

    # 模拟获取工具请求
    get_tools_req = {"computer": client.namespaces[SMCP_NAMESPACE], "robot_id": "test_office", "req_id": "test_req_id"}

    # 发送获取工具请求（模拟Agent的行为）
    await computer_server.emit(GET_TOOLS_EVENT, get_tools_req, namespace=SMCP_NAMESPACE, to=client.namespaces[SMCP_NAMESPACE])
    await asyncio.sleep(0.1)

    # 验证Computer的方法是否被调用
    assert computer.aget_available_tools.called

    await client.disconnect()


@pytest.mark.asyncio
async def test_computer_handles_tool_call_timeout(computer, computer_server, basic_server_port: int):
    """测试工具调用超时处理"""
    # 配置模拟工具调用超时
    computer.mcp_manager.aexecute_tool = AsyncMock(side_effect=asyncio.TimeoutError)

    client = SMCPComputerClient(computer=computer)

    await client.connect(
        f"http://localhost:{basic_server_port}",
        socketio_path="/socket.io",
        headers={"mock_header": "mock_value"},
        auth={"mock_header": "mock_value"},
        namespaces=[SMCP_NAMESPACE],
    )
    await client.join_office("test_office", "test_computer")

    # 模拟工具调用请求（标记为应该超时）
    tool_call_req = {
        "computer": client.namespaces[SMCP_NAMESPACE],
        "tool_name": "test_tool",
        "params": {"param1": "value1"},
        "robot_id": "test_office",
        "req_id": "test_req_id",
        "timeout": 10,
    }

    # 发送工具调用请求
    try:
        await computer_server.emit(TOOL_CALL_EVENT, tool_call_req, namespace=SMCP_NAMESPACE, to=client.namespaces[SMCP_NAMESPACE])
    except Exception as e:
        logger.error(f"工具调用出错: {e}")

    # 等待处理
    await asyncio.sleep(0.1)

    # 验证返回了超时结果
    computer.mcp_manager.aexecute_tool.assert_called()

    await client.disconnect()
