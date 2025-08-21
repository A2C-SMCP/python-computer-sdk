# 文件名: main.py
# @Time    : 2025/8/17 16:52
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm

"""
计算机管理模块 Computer
==============================

该模块定义了 Computer 类，用于管理 MCP 服务器的生命周期、工具获取等功能。

This module defines the Computer class, which manages the lifecycle of MCP servers and provides tool retrieval functions.

类和方法均采用 Google 风格注释（中英文双语）。
All classes and methods use Google style docstrings (bilingual: Chinese and English).

依赖 Dependencies:
    - mcp
    - pydantic
    - a2c_smcp_cc.mcp_clients.manager
    - a2c_smcp_cc.mcp_clients.model
    - a2c_smcp_cc.socketio.smcp
    - a2c_smcp_cc.socketio.types
    - a2c_smcp_cc.utils.logger
"""

import json
from types import MappingProxyType
from typing import Any

from mcp import Tool
from pydantic import TypeAdapter

from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.mcp_clients.model import MCPServerConfig
from a2c_smcp_cc.socketio.smcp import SMCPTool
from a2c_smcp_cc.socketio.types import AttributeValue
from a2c_smcp_cc.utils.logger import logger


class Computer:
    def __init__(
        self, mcp_servers: dict[str, MCPServerConfig] | None = None, auto_connect: bool = True, auto_reconnect: bool = True
    ) -> None:
        """
        初始化 Computer 实例
        Initialize Computer instance

        MCP Server使用宝典的形式进行配置是为了帮助使用者减少重复配置的可能性，建议字典的key使用MCP Server的名称。以此避免重复配置。当然，
            如果有特殊的设计需要保持名称的重复。可以自定义字典值以避开这个限制

        The MCP Server configuration is in the form of a dictionary to help users reduce the possibility of duplicate
        configuration, and it is recommended to use the name of the MCP Server as the key to avoid duplicate
        configuration. Of course, if there is a special design that requires the name to be repeated, you can
        customize the dictionary value to avoid this limitation

        Args:
            mcp_servers (dict[str, MCPServerConfig] | None): MCP服务器配置字典。MCP server config dict.
            auto_connect (bool): 是否自动连接。Whether to auto connect.
            auto_reconnect (bool): 是否自动重连。Whether to auto reconnect.
        """
        self.mcp_manager: MCPServerManager | None = None
        self._mcp_servers = mcp_servers or {}
        self._auto_connect = auto_connect
        self._auto_reconnect = auto_reconnect

    async def boot_up(self) -> None:
        """
        启动计算机，初始化 MCP 服务器管理器。
        Boot up the computer and initialize the MCP server manager.
        """
        self.mcp_manager = MCPServerManager(auto_connect=self._auto_connect, auto_reconnect=self._auto_reconnect)
        await self.mcp_manager.ainitialize(self._mcp_servers.values())

    async def shutdown(self) -> None:
        """
        关闭计算机，关闭 MCP 服务器管理器。
        Shutdown the computer and close the MCP server manager.
        """
        if self.mcp_manager:
            await self.mcp_manager.aclose()
        self.mcp_manager = None

    async def __aenter__(self) -> "Computer":
        """
        异步上下文进入方法。
        Async context enter method.

        Returns:
            Computer: 当前实例。Current instance.
        """
        await self.boot_up()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        """
        异步上下文退出方法。
        Async context exit method.

        Args:
            exc_type (type[BaseException] | None): 异常类型。Exception type.
            exc_val (BaseException | None): 异常值。Exception value.
            exc_tb (object | None): 异常追踪。Exception traceback.
        """
        await self.shutdown()

    @property
    def mcp_servers(self) -> MappingProxyType[MCPServerConfig, ...]:
        """
        获取 MCP 服务器配置（不可变）。
        Get MCP server config (immutable).

        Returns:
            MappingProxyType[MCPServerConfig, ...]: 配置字典。Config dict.
        """
        return MappingProxyType(self._mcp_servers)

    async def aget_available_tools(self) -> list[SMCPTool]:
        """
        获取可用工具列表。
        Get available tools list.

        Returns:
            list[SMCPTool]: 工具列表。Tool list.
        """
        # 从Manager获取全部工具
        tools = [t async for t in self.mcp_manager.available_tools()]

        def is_attr(v: Any) -> bool:
            """
            判断值是否为简单属性。
            Check if value is a simple attribute.

            Args:
                v (Any): 待检测值。Value to check.

            Returns:
                bool: 是否为简单属性。Whether it is simple attribute.
            """
            try:
                TypeAdapter(AttributeValue).validate_python(v)
                return True
            except Exception as e:
                logger.debug(f"非简单属性:{v}", exc_info=e)
                return False

        def convert_tool(t: Tool) -> SMCPTool:
            """
            将 MCP 工具定义转换为 SMCP 工具定义。
            Convert MCP tool definition to SMCP tool definition.

            Args:
                t (Tool): MCP 工具。MCP tool.

            Returns:
                SMCPTool: SMCP 工具。SMCP tool.
            """
            meta = {}
            if t.meta:
                for k, v in t.meta.items():
                    if not is_attr(v):
                        try:
                            meta[k] = json.dumps(v)
                        except Exception as e:
                            logger.error(f"无法序列化工具元数据{k}:{v}", exc_info=e)
                            meta[k] = str(v)
                    else:
                        meta[k] = v
            if t.annotations:
                meta["MCP_TOOL_ANNOTATION"] = t.annotations.model_dump(mode="json")
            return SMCPTool(name=t.name, description=t.description, params_schema=t.inputSchema, return_schema=t.outputSchema, meta=meta)

        mcp_tools = [convert_tool(t) for t in tools]
        return mcp_tools
