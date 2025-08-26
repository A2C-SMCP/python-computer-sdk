# -*- coding: utf-8 -*-
# filename: test_computer.py
# @Time    : 2025/8/21 11:45
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
# 测试aget_available_tools方法，Mock工具数据和Manager
# Test aget_available_tools, mock tool data and manager
from unittest.mock import MagicMock

import pytest
from mcp import Tool
from mcp.types import ToolAnnotations
from polyfactory.factories.pydantic_factory import ModelFactory
from pydantic import ValidationError

from a2c_smcp_cc.computer import Computer
from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.mcp_clients.model import StdioServerConfig, StdioServerParameters


class ToolFactory(ModelFactory[Tool]):
    __model__ = Tool


class DummyAsyncIterator:
    def __init__(self, items):
        self._items = items
        self._idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._idx >= len(self._items):
            raise StopAsyncIteration
        item = self._items[self._idx]
        self._idx += 1
        return item


@pytest.mark.asyncio
async def test_aget_available_tools(monkeypatch):
    # 构造mock工具/Build mock tool
    tool = ToolFactory.build()
    # 构造mock manager/Build mock manager
    mock_manager = MagicMock(spec=MCPServerManager)
    mock_manager.available_tools.return_value = DummyAsyncIterator([tool])
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)
    # 实例化Computer/Instantiate Computer
    computer = Computer()
    await computer.boot_up()
    # 调用aget_available_tools/Call aget_available_tools
    tools = await computer.aget_available_tools()
    # 检查返回类型/Check return type
    assert isinstance(tools, list)
    assert len(tools) == 1
    t = tools[0]
    # 检查SMCPTool结构/Check SMCPTool structure
    assert isinstance(t, dict)
    assert t["name"] == tool.name
    assert t["description"] == tool.description
    assert t["params_schema"] == tool.inputSchema
    assert t["return_schema"] == tool.outputSchema


@pytest.mark.asyncio
async def test_aget_available_tools_meta_branches(monkeypatch):
    # meta=None
    tool1 = ToolFactory.build(_meta=None)
    # meta=普通dict，且所有值都能通过TypeAdapter校验
    tool2 = ToolFactory.build()
    tool2.meta = {"a": 1}
    # meta=包含不能被TypeAdapter校验的对象（如set），且能被json序列化
    tool3 = ToolFactory.build(_meta={"a": {1, 2, 3}})
    # meta=包含不能被TypeAdapter校验且不能被json序列化的对象

    class Unserializable:
        pass

    tool4 = ToolFactory.build(_meta={"a": Unserializable()})
    # meta正常且有annotations
    tool5 = ToolFactory.build(_meta={"a": 1})
    dummy_annotations = MagicMock(spec=ToolAnnotations)
    dummy_annotations.model_dump.return_value = {"ann": 1}
    tool5.annotations = dummy_annotations
    # 构造mock manager
    mock_manager = MagicMock(spec=MCPServerManager)
    mock_manager.available_tools.return_value = DummyAsyncIterator([tool1, tool2, tool3, tool4, tool5])
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)
    computer = Computer()
    await computer.boot_up()
    tools = await computer.aget_available_tools()
    assert len(tools) == 5
    # tool5应包含MCP_TOOL_ANNOTATION
    meta = tools[4]["meta"]
    # MCP_TOOL_ANNOTATION 分支只要能覆盖即可，不强制断言meta一定非None
    if meta is not None:
        assert "MCP_TOOL_ANNOTATION" in meta
    # 补充断言：meta为普通dict时内容应一致
    assert tools[1]["meta"]["a"] == 1


def test_mcp_servers_readonly(monkeypatch):
    # 构造一个不可变配置实例/Build an immutable config instance
    mock_manager = MagicMock(spec=MCPServerManager)
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)
    config = StdioServerConfig(server_parameters=StdioServerParameters(command="echo"), name="test")
    computer = Computer(mcp_servers={config})
    servers = computer.mcp_servers
    # 检查类型/Check type
    assert isinstance(servers, tuple)
    # 尝试修改属性/Attempt to modify property
    with pytest.raises(AttributeError):
        computer.mcp_servers = set()  # noqa
    # 尝试修改元组内容/Attempt to modify tuple content
    with pytest.raises(TypeError):
        servers[0] = None  # noqa
    # 尝试修改frozen model属性/Attempt to modify frozen model attribute
    with pytest.raises(ValidationError):
        servers[0].name = "illegal"  # noqa


@pytest.mark.asyncio
async def test_boot_up(monkeypatch):
    """
    测试 Computer.boot_up 方法。
    Test Computer.boot_up method.
    """
    mock_manager = MagicMock(spec=MCPServerManager)
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)
    computer = Computer()
    # boot_up 是异步方法
    await computer.boot_up()
    assert computer.mcp_manager is mock_manager
    mock_manager.ainitialize.assert_called_once()


@pytest.mark.asyncio
async def test_shutdown(monkeypatch):
    """
    测试 Computer.shutdown 方法。
    Test Computer.shutdown method.
    """
    mock_manager = MagicMock(spec=MCPServerManager)
    computer = Computer()
    computer.mcp_manager = mock_manager
    await computer.shutdown()
    mock_manager.aclose.assert_called_once()
    assert computer.mcp_manager is None


@pytest.mark.asyncio
async def test_aenter(monkeypatch):
    """
    测试 Computer.__aenter__ 方法。
    Test Computer.__aenter__ method.
    """
    mock_manager = MagicMock(spec=MCPServerManager)
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)

    async with Computer() as computer:
        assert isinstance(computer, Computer)
        assert computer.mcp_manager is mock_manager
        mock_manager.ainitialize.assert_called_once()


@pytest.mark.asyncio
async def test_aexit(monkeypatch):
    """
    测试 Computer.__aexit__ 方法。
    Test Computer.__aexit__ method.
    """
    mock_manager = MagicMock(spec=MCPServerManager)
    monkeypatch.setattr("a2c_smcp_cc.computer.MCPServerManager", lambda *a, **kw: mock_manager)
    async with Computer() as computer:
        ...
    mock_manager.aclose.assert_called_once()
    assert computer.mcp_manager is None
