# -*- coding: utf-8 -*-
# filename: test_manager.py
# @Time    : 2025/8/18 14:59
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp import StdioServerParameters, Tool
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from mcp.types import CallToolResult

from a2c_smcp_cc.mcp_clients.manager import MCPServerManager, ToolNameDuplicatedError
from a2c_smcp_cc.mcp_clients.model import MCPServerConfig, SseServerConfig, StdioServerConfig, StreamableHttpServerConfig, ToolMeta

# 模拟类型定义
TOOL_NAME = str
SERVER_NAME = str


# 模拟BaseMCPClient
class MockMCPClient:
    def __init__(self, tools: list[Tool] = None):
        self.tools = tools or []
        self.connect = AsyncMock()
        self.disconnect = AsyncMock()
        self.list_tools = AsyncMock(return_value=tools)
        call_ret = MagicMock(spec=CallToolResult)
        call_ret.result = None
        call_ret.meta = None
        self.call_tool = AsyncMock(return_value=call_ret)
        self.state = "connected"


def create_mock_tool(name: str, meta: dict | None = None) -> Tool:
    tool = MagicMock(name=name, spec=Tool)
    tool.name = name
    tool.meta = meta
    return tool


# 模拟client_factory函数
def mock_client_factory(config: MCPServerConfig) -> MockMCPClient:
    # 简化处理：根据配置名称返回不同的工具列表
    if "server1" in config.name:
        return MockMCPClient([create_mock_tool("tool1"), create_mock_tool("tool2")])
    elif "server2" in config.name:
        return MockMCPClient([create_mock_tool("tool3"), create_mock_tool("tool4")])
    elif "alias_server" in config.name:
        return MockMCPClient([create_mock_tool("tool5")])
    elif "duplicate_server" in config.name:
        return MockMCPClient([create_mock_tool("duplicate_tool")])
    return MockMCPClient()


# Monkey patch客户端工厂函数
@pytest.fixture(autouse=True)
def patch_client_factory(monkeypatch):
    monkeypatch.setattr("a2c_smcp_cc.mcp_clients.manager.client_factory", mock_client_factory)


# 创建示例服务器配置
def create_server_config(name: str, disabled: bool = False, forbidden_tools: list = None, tool_meta: dict = None) -> MCPServerConfig:
    forbidden_tools = forbidden_tools or []
    tool_meta = tool_meta or {}
    if "sse" in name:
        return SseServerConfig(
            name=name,
            disabled=disabled,
            forbidden_tools=forbidden_tools,
            tool_meta=tool_meta,
            server_parameters=MagicMock(spec=SseServerParameters),
        )
    elif "http" in name:
        return StreamableHttpServerConfig(
            name=name,
            disabled=disabled,
            forbidden_tools=forbidden_tools,
            tool_meta=tool_meta,
            server_parameters=MagicMock(spec=StreamableHttpParameters),
        )
    else:
        return StdioServerConfig(
            name=name,
            disabled=disabled,
            forbidden_tools=forbidden_tools,
            tool_meta=tool_meta,
            server_parameters=MagicMock(spec=StdioServerParameters),
        )


@pytest.fixture
def manager() -> MCPServerManager:
    manager = MCPServerManager()
    manager.auto_reconnect = True  # 启用自动重连便于测试
    return manager


@pytest.mark.asyncio
async def test_initialize_with_servers(manager):
    """测试初始化和服务器启动"""
    servers = [create_server_config("server1"), create_server_config("server2", disabled=True), create_server_config("sse_server")]

    await manager.ainitialize(servers)

    # 初始化后不会自动启动所有服务。验证活动客户端
    assert "server1" not in manager.active_clients
    assert "sse_server" not in manager.active_clients
    assert "server2" not in manager.active_clients

    # 调用start_all
    await manager.astart_all()

    # 验证启动
    assert "server1" in manager.active_clients
    assert "sse_server" in manager.active_clients
    assert "server2" not in manager.active_clients

    # 验证工具映射
    assert manager.tool_mapping["tool1"] == "server1"
    assert manager.tool_mapping["tool2"] == "server1"
    assert "tool3" not in manager.tool_mapping  # 禁用的服务器

    # 验证状态检查
    statuses = manager.get_server_status()
    assert ("server1", True, "connected") in statuses
    assert ("server2", False, "pending") in statuses
    assert ("sse_server", True, "connected") in statuses


@pytest.mark.asyncio
async def test_tool_execution(manager):
    """测试工具执行流程"""
    servers = [create_server_config("server1")]
    await manager.ainitialize(servers)

    await manager.astart_all()

    # 执行工具
    params = {"key": "value"}
    await manager.aexecute_tool("tool1", params)

    # 验证调用
    client = manager.active_clients["server1"]
    client.call_tool.assert_awaited_once_with("tool1", params)


@pytest.mark.asyncio
async def test_tool_with_alias(manager):
    """测试别名映射功能"""
    tool_meta = {"tool5": ToolMeta(alias="aliased_tool")}
    servers = [create_server_config("alias_server", tool_meta=tool_meta)]
    await manager.ainitialize(servers)
    await manager.astart_all()

    # 验证别名映射
    assert manager.alias_mapping["aliased_tool"] == ("alias_server", "tool5")
    assert "tool5" not in manager.tool_mapping
    assert manager.tool_mapping["aliased_tool"] == "alias_server"

    # 执行别名工具
    await manager.aexecute_tool("aliased_tool", {})
    client = manager.active_clients["alias_server"]
    print("Call args list:", client.call_tool.call_args_list)
    client.call_tool.assert_awaited_once_with("tool5", {})


@pytest.mark.asyncio
async def test_disabled_tool(manager):
    """测试禁用工具处理"""
    servers = [create_server_config("server1", forbidden_tools=["tool2"])]
    await manager.ainitialize(servers)
    await manager.astart_all()

    # 验证禁用状态
    assert "tool2" in manager.disabled_tools

    # 尝试执行禁用工具
    with pytest.raises(PermissionError):
        await manager.aexecute_tool("tool2", {})


@pytest.mark.asyncio
async def test_tool_name_conflict(manager):
    """测试工具名冲突处理"""
    servers = [
        create_server_config("server1"),
        create_server_config("duplicate_server", tool_meta={"duplicate_tool": ToolMeta(alias="tool1")}),
    ]

    # 验证初始化时检测到冲突
    with pytest.raises(ToolNameDuplicatedError):
        await manager.ainitialize(servers)
        await manager.astart_all()

    # 工具重名导致的异常是在逐个启动Client的时候抛出的，因此只会回滚检测到异常的Client，
    # 而不会回滚所有Client
    assert len(manager.active_clients) == 1


@pytest.mark.asyncio
async def test_dynamic_server_management(manager):
    """测试动态添加/移除服务器"""
    # 初始配置
    servers = [create_server_config("server1")]
    await manager.ainitialize(servers)
    await manager.astart_all()
    assert "server1" in manager.active_clients

    # 添加新服务器
    new_server = create_server_config("http_server")
    await manager.aadd_or_aupdate_server(new_server)

    # 验证新服务器启动
    assert "http_server" not in manager.active_clients
    await manager.astart_client("http_server")
    assert "http_server" in manager.active_clients

    # 更新服务器配置（启用自动重连）
    updated_server = create_server_config("server1", forbidden_tools=["tool1"])
    # 验证服务器重启
    old_client = manager.active_clients["server1"]  # 要提示保存旧客户端的引用，因为add_or_update_server会销毁旧客户端
    await manager.aadd_or_aupdate_server(updated_server)
    await asyncio.sleep(0.1)  # 等待自动重连 需要释放一次协程才能触发协程任务的执行与调用。

    old_client.disconnect.assert_awaited()

    # 验证更新应用
    assert "tool1" in manager.disabled_tools

    # 移除服务器
    await manager.aremove_server("http_server")
    assert "http_server" not in manager.active_clients
    assert "http_server" not in manager.servers_config


@pytest.mark.asyncio
async def test_auto_reconnect_disabled(manager):
    """测试禁用自动重连时更新配置"""
    manager.auto_reconnect = False

    servers = [create_server_config("server1")]
    await manager.ainitialize(servers)
    await manager.astart_all()

    # 尝试更新活动服务器的配置
    updated_config = create_server_config("server1", forbidden_tools=["tool1"])

    with pytest.raises(RuntimeError):
        await manager.aadd_or_aupdate_server(updated_config)


@pytest.mark.asyncio
async def test_get_available_tools(manager):
    """测试获取可用工具"""
    tool_meta = {"tool1": ToolMeta(auto_apply=True)}
    servers = [create_server_config("server1", tool_meta=tool_meta)]
    await manager.ainitialize(servers)
    await manager.astart_all()

    # 获取工具
    tools = []
    async for tool in manager.aget_available_tools():
        tools.append(tool)

    assert len(tools) == 2
    tool1 = next(t for t in tools if t.name == "tool1")
    assert tool1.meta["a2c_tool_meta"].auto_apply


@pytest.mark.asyncio
async def test_error_handling(manager):
    """测试错误处理"""
    # 模拟客户端连接错误
    bad_server = create_server_config("error_server")
    bad_client = MockMCPClient()
    bad_client.list_tools.side_effect = Exception("Connection failed")
    manager.client_factory = lambda _: bad_client

    await manager.aadd_or_aupdate_server(bad_server)

    # 验证状态
    assert "error_server" not in manager.active_clients

    # 工具执行错误处理
    servers = [create_server_config("server1")]
    await manager.ainitialize(servers)
    await manager.astart_all()

    client = manager.active_clients["server1"]
    client.call_tool.side_effect = TimeoutError("Execution timed out")

    with pytest.raises(TimeoutError):
        await manager.aexecute_tool("tool1", {}, timeout=0.1)


@pytest.mark.asyncio
async def test_meta_data_injection(manager):
    """测试工具元数据注入"""
    tool_meta = {"tool1": ToolMeta(ret_object_mapper={"result": "data"})}
    servers = [create_server_config("server1", tool_meta=tool_meta)]
    await manager.ainitialize(servers)
    await manager.astart_all()

    # 执行工具
    result = await manager.aexecute_tool("tool1", {})

    # 验证元数据注入
    assert "a2c_tool_meta" in result.meta
    assert result.meta["a2c_tool_meta"].ret_object_mapper == {"result": "data"}
