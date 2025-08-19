# -*- coding: utf-8 -*-
# filename: test_sse_client.py
# @Time    : 2025/8/19 19:28
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
import multiprocessing
import socket
import time
from collections.abc import Callable, Generator

import anyio
import pytest
import uvicorn
from mcp.client.session_group import SseServerParameters
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ErrorData, TextContent, Tool
from pydantic import AnyUrl
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Mount, Route
from transitions import MachineError

from a2c_smcp_cc.mcp_clients.sse_client import SseMCPClient

SERVER_NAME = "test_server_for_SSE"


@pytest.fixture
def server_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server_url(server_port: int) -> str:
    return f"http://127.0.0.1:{server_port}"


# Test server implementation
class ServerTest(Server):
    def __init__(self) -> None:
        super().__init__(SERVER_NAME)

        @self.read_resource()
        async def handle_read_resource(uri: AnyUrl) -> str | bytes:
            if uri.scheme == "foobar":
                return f"Read {uri.host}"
            elif uri.scheme == "slow":
                # Simulate a slow resource
                await anyio.sleep(2.0)
                return f"Slow response from {uri.host}"

            raise McpError(error=ErrorData(code=404, message="OOPS! no resource with that URI was found"))

        @self.list_tools()
        async def handle_list_tools() -> list[Tool]:
            return [
                Tool(
                    name="test_tool",
                    description="A test tool",
                    inputSchema={"type": "object", "properties": {}},
                )
            ]

        @self.call_tool()
        async def handle_call_tool(name: str, args: dict) -> list[TextContent]:
            if name != "test_tool":
                raise McpError(error=ErrorData(code=404, message="OOPS! no tool with that name was found"))
            return [TextContent(type="text", text=f"Called {name}")]


# Test fixtures


def make_server_app() -> Starlette:
    """创建测试 Starlette app，带有 SSE 传输\nCreate test Starlette app with SSE transport"""
    # 配置测试安全设置 Configure security for testing
    security_settings: TransportSecuritySettings = TransportSecuritySettings(
        allowed_hosts=["127.0.0.1:*", "localhost:*"], allowed_origins=["http://127.0.0.1:*", "http://localhost:*"]
    )
    sse: SseServerTransport = SseServerTransport("/messages/", security_settings=security_settings)
    server: ServerTest = ServerTest()

    async def handle_sse(request: Request) -> Response:
        async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
            await server.run(streams[0], streams[1], server.create_initialization_options())
        return Response()

    app: Starlette = Starlette(
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ]
    )

    return app


def run_server(server_port: int) -> None:
    app: Starlette = make_server_app()
    server = uvicorn.Server(config=uvicorn.Config(app=app, host="127.0.0.1", port=server_port, log_level="error"))
    print(f"starting server on {server_port}")
    server.run()

    # Give server time to start
    while not server.started:
        print("waiting for server to start")
        time.sleep(0.5)


@pytest.fixture()
def server(server_port: int) -> Generator[None, None, None]:
    proc: multiprocessing.Process = multiprocessing.Process(target=run_server, kwargs={"server_port": server_port}, daemon=True)
    print("starting process")
    proc.start()

    # Wait for server to be running
    max_attempts: int = 20
    attempt: int = 0
    print("waiting for server to start")
    while attempt < max_attempts:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(("127.0.0.1", server_port))
                break
        except ConnectionRefusedError:
            time.sleep(0.1)
            attempt += 1
    else:
        raise RuntimeError(f"Server failed to start after {max_attempts} attempts")

    yield

    print("killing server")
    # Signal the server to stop
    proc.kill()
    proc.join(timeout=2)
    if proc.is_alive():
        print("server process failed to terminate")


@pytest.fixture
def sse_params(server_url: str) -> SseServerParameters:
    """
    根据fixture动态生成SseServerParameters，指向运行时服务
    Dynamically generate SseServerParameters based on fixture, pointing to runtime server
    """
    return SseServerParameters(url=f"{server_url}/sse")


@pytest.fixture
def track_state() -> tuple[Callable[[str, str], None], list[tuple[str, str]]]:
    """
    跟踪状态变化的辅助函数
    Helper for tracking state changes
    """
    state_history: list[tuple[str, str]] = []

    def callback(from_state: str, to_state: str) -> None:
        state_history.append((from_state, to_state))

    return callback, state_history


@pytest.mark.asyncio
async def test_state_transitions(
    server: Generator[None, None, None],
    sse_params: SseServerParameters,
    track_state: tuple[Callable[[str, str], None], list[tuple[str, str]]],
) -> None:
    """
    测试客户端状态转换
    Test client state transitions
    """
    callback, history = track_state
    client: SseMCPClient = SseMCPClient(sse_params, state_change_callback=callback)
    assert client.state == "initialized"
    await client.aconnect()
    assert client.state == "connected"
    assert ("initialized", "connected") in history
    await client.adisconnect()
    assert client.state == "disconnected"
    assert ("connected", "disconnected") in history
    await client.ainitialize()
    assert client.state == "initialized"
    assert ("disconnected", "initialized") in history


@pytest.mark.asyncio
async def test_list_tools(server: Generator[None, None, None], sse_params: SseServerParameters) -> None:
    """
    测试获取工具列表功能
    Test list_tools functionality
    """
    client: SseMCPClient = SseMCPClient(sse_params)
    await client.aconnect()
    tools: list[Tool] = await client.list_tools()
    assert len(tools) == 1
    assert tools[0].name == "test_tool"
    assert tools[0].description == "A test tool"
    await client.adisconnect()


@pytest.mark.asyncio
async def test_call_tool_success(server: Generator[None, None, None], sse_params: SseServerParameters) -> None:
    """
    测试成功调用工具
    Test successful tool call
    """
    client: SseMCPClient = SseMCPClient(sse_params)
    await client.aconnect()
    result: CallToolResult = await client.call_tool("test_tool", {})
    assert isinstance(result, CallToolResult)
    assert not result.isError
    assert result.content[0].text == "Called test_tool"
    await client.adisconnect()


@pytest.mark.asyncio
async def test_call_tool_failure(server: Generator[None, None, None], sse_params: SseServerParameters) -> None:
    """
    测试工具调用失败场景
    Test tool call failure
    """
    client = SseMCPClient(sse_params)
    await client.aconnect()

    # 调用不存在的工具
    result = await client.call_tool("nonexistent_tool", {})
    assert result.isError, "调用不存在的工具应该失败"

    await client.adisconnect()


@pytest.mark.asyncio
async def test_async_session_property(server: Generator[None, None, None], sse_params: SseServerParameters) -> None:
    """
    测试 async_session 属性
    Test async_session property
    """
    client = SseMCPClient(sse_params)
    # 未连接状态下会话为 None
    assert client._async_session is None

    # 访问 async_session 会自动连接
    session = await client.async_session
    assert session is not None

    await client.adisconnect()


@pytest.mark.asyncio
async def test_error_recovery(
    server: Generator[None, None, None],
    sse_params: SseServerParameters,
    track_state: tuple[Callable[[str, str], None], list[tuple[str, str]]],
) -> None:
    """
    测试错误状态恢复
    Test error recovery
    """
    callback, history = track_state
    client = SseMCPClient(sse_params, state_change_callback=callback)
    await client.aconnect()

    # 强制进入错误状态
    await client.aerror()
    assert client.state == "error"
    assert any(from_state == "connected" and to_state == "error" for from_state, to_state in history)

    # 从错误状态恢复
    await client.ainitialize()
    assert client.state == "initialized"
    assert ("error", "initialized") in history

    # 尝试重新连接
    await client.aconnect()
    assert client.state == "connected"

    await client.adisconnect()


@pytest.mark.asyncio
async def test_invalid_state_operations(server: Generator[None, None, None], sse_params: SseServerParameters) -> None:
    """
    测试在无效状态下执行操作
    Test invalid state operations
    """
    client: SseMCPClient = SseMCPClient(sse_params)
    with pytest.raises(ConnectionError):
        await client.call_tool("test_tool", {})
    with pytest.raises(ConnectionError):
        await client.list_tools()
    with pytest.raises(MachineError):
        await client.adisconnect()
