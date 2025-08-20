# filename: manager.py
# @Time    : 2025/8/17 16:53
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
import asyncio
import copy
from collections import defaultdict
from collections.abc import AsyncGenerator
from typing import Any

from mcp.types import CallToolResult, Tool

from a2c_smcp_cc.mcp_clients.model import A2C_TOOL_META, SERVER_NAME, TOOL_NAME, MCPClientProtocol, MCPServerConfig
from a2c_smcp_cc.mcp_clients.utils import client_factory
from a2c_smcp_cc.utils.logger import logger


class ToolNameDuplicatedError(Exception):
    def __init__(self, *args: Any) -> None:
        super().__init__(*args)


class MCPServerManager:
    """
    MCP Server管理器

    所有以下划线开头的私有方法是非协程安全的。如果外部调用，需要使用普通方法。
    """

    def __init__(self, auto_connect: bool = False, auto_reconnect: bool = True) -> None:
        # 存储所有服务器配置
        self._servers_config: dict[SERVER_NAME, MCPServerConfig] = {}
        # 存储活动客户端 {server_name: client}
        self._active_clients: dict[SERVER_NAME, MCPClientProtocol] = {}
        # 工具到服务器的映射 {tool_name: server_name}
        self._tool_mapping: dict[TOOL_NAME, SERVER_NAME] = {}
        # 工具的alias到server+original_name的映射 {alias: (server_name, original_name)}
        self._alias_mapping: dict[str, tuple[SERVER_NAME, TOOL_NAME]] = {}
        # 禁用工具集合
        self._disabled_tools: set[TOOL_NAME] = set()
        # 自动重连标志
        self.auto_reconnect: bool = auto_reconnect
        # 自动连接标志
        self.auto_connect: bool = auto_connect
        # 内部锁防止并发修改
        self._lock = asyncio.Lock()

    async def ainitialize(self, servers: list[MCPServerConfig]) -> None:
        """
        初始化管理器并添加服务器配置

        Args:
            servers (list[MCPServerConfig]): MCP服务器配置
        """
        async with self._lock:
            # 清理旧设置与配置
            # 1. 停止所有活动客户端
            await self._astop_all()
            # 2. 清空所有状态存储
            self._clear_all()
            # 3. 添加新配置
            for server in servers:
                await self._add_or_update_server_config(server)
            try:
                await self._arefresh_tool_mapping()
            except ToolNameDuplicatedError as e:  # pragma: no cover
                # 极端分支：仅在外部错误用法下触发，主流程不会走到这里
                # 中文：此处为防御性分支，正常流程不会触发
                # English: Defensive branch, not triggered in normal flow
                await self._astop_all()  # pragma: no cover
                self._clear_all()  # pragma: no cover
                raise e  # pragma: no cover

    async def _add_or_update_server_config(self, config: MCPServerConfig) -> None:
        """
        添加/更新服务器配置（不启动客户端）

        如果已存在，检查是否已经建立客户端连接，如果是，检查是否需要自动重连
        如果不存在，直接添加配置

        Args:
            config (MCPServerConfig): MCP服务器配置
        """
        if config.name in self._servers_config:
            # 配置更新时检查是否激活
            if config.name in self._active_clients:
                if self.auto_reconnect:
                    self._servers_config[config.name] = config
                    await self._arestart_server(config.name)
                else:
                    raise RuntimeError(f"Server {config.name} is active. Stop it before updating config")
        else:
            self._servers_config[config.name] = config
            if self.auto_connect:
                await self._astart_client(config.name)

    async def aadd_or_aupdate_server(self, config: MCPServerConfig) -> None:
        """
        添加或更新服务器配置

        Args:
            config (MCPServerConfig): MCP服务器配置
        """
        async with self._lock:
            backup_config = copy.deepcopy(self._servers_config)
            try:
                await self._add_or_update_server_config(config)
                await self._arefresh_tool_mapping()
            except ToolNameDuplicatedError as e:
                self._servers_config = backup_config
                raise e

    async def aremove_server(self, server_name: str) -> None:
        """移除服务器配置"""
        async with self._lock:
            if server_name in self._active_clients:
                await self._astop_client(server_name)
            del self._servers_config[server_name]
            await self._arefresh_tool_mapping()

    async def _arestart_server(self, server_name: str) -> None:
        """
        重启服务器客户端

        Args:
            server_name (str): 服务器名称
        """
        # 明确使用当前管理器中的最新配置
        config = self._servers_config.get(server_name)
        if not config:
            # 极端分支：仅在外部错误用法下触发，主流程不会走到这里
            # 中文：此处为防御性分支，正常流程不会触发
            # English: Defensive branch, not triggered in normal flow
            raise ValueError(f"Server {server_name} not found in config")  # pragma: no cover

        # 确保使用最新配置重启
        if server_name in self._active_clients:
            await self._astop_client(server_name)

        # 只有启用的配置才能重启
        if not config.disabled:
            await self._astart_client(server_name)

    async def astart_all(self) -> None:
        """启动所有启用的服务器"""
        async with self._lock:
            logger.debug(f"Manager Start all async task: {asyncio.current_task().get_name()}")
            for server_name in self._servers_config:
                if not self._servers_config[server_name].disabled:
                    await self._astart_client(server_name)

    async def astart_client(self, server_name: str) -> None:
        """启动单个服务器客户端"""
        async with self._lock:
            await self._astart_client(server_name)

    async def _astart_client(self, server_name: str) -> None:
        """启动单个服务器客户端"""
        config = self._servers_config.get(server_name)
        if not config:
            # 极端分支：仅在外部错误用法下触发，主流程不会走到这里
            # 中文：此处为防御性分支，正常流程不会触发
            # English: Defensive branch, not triggered in normal flow
            raise ValueError(f"Unknown server: {server_name}")  # pragma: no cover

        if config.disabled:
            raise RuntimeError(f"Cannot start disabled server: {server_name}")

        if server_name in self._active_clients:
            return  # 已经启动

        # 伪代码：根据配置类型创建客户端
        client = client_factory(config)
        await client.aconnect()
        self._active_clients[server_name] = client
        try:
            await self._arefresh_tool_mapping()
        except ToolNameDuplicatedError as e:
            await client.adisconnect()
            del self._active_clients[server_name]
            raise e

    async def astop_client(self, server_name: str) -> None:
        """停止单个服务器客户端"""
        async with self._lock:
            await self._astop_client(server_name)

    async def _astop_client(self, server_name: str) -> None:
        """停止单个服务器客户端"""
        client = self._active_clients.pop(server_name, None)
        if client:
            await client.adisconnect()
            await self._arefresh_tool_mapping()

    async def _astop_all(self) -> None:
        """停止所有客户端"""
        for name in list(self._active_clients.keys()):
            await self._astop_client(name)

    async def astop_all(self) -> None:
        """停止所有客户端"""
        async with self._lock:
            logger.debug(f"Manager Stop all async task: {asyncio.current_task().get_name()}")
            await self._astop_all()

    def _clear_all(self) -> None:
        """清空所有连接（别名）"""
        self._servers_config.clear()
        self._active_clients.clear()
        self._tool_mapping.clear()
        self._alias_mapping.clear()
        self._disabled_tools.clear()

    async def aclose(self) -> None:
        """关闭所有连接（别名）"""
        await self.astop_all()

        # 2. 清空所有状态存储
        self._clear_all()

    async def _arefresh_tool_mapping(self) -> None:
        """刷新工具映射和禁用状态"""
        # 清空现有映射
        self._tool_mapping.clear()
        self._disabled_tools.clear()
        self._alias_mapping.clear()

        # 临时存储工具源服务器
        tool_sources: dict[TOOL_NAME, list[str]] = defaultdict(list)

        # 收集所有活动服务器的工具
        for server_name, client in self._active_clients.items():
            config = self._servers_config[server_name]
            try:
                tools = await client.list_tools()
                for t in tools:
                    original_tool_name = t.name
                    # 获取工具元数据
                    tool_meta = (config.tool_meta or {}).get(original_tool_name)

                    # 确定最终显示的工具名（优先使用别名）
                    display_name: str = tool_meta.alias if tool_meta and tool_meta.alias else original_tool_name
                    # 如果使用提别名，则更新别名映射
                    if display_name != original_tool_name:
                        self._alias_mapping[display_name] = (server_name, original_tool_name)

                    # 将工具添加到映射
                    tool_sources[display_name].append(server_name)

                    # 检查是否为禁用工具 (根据配置，但此时需要注意如果原始名称在禁用列表中，也应该禁用，因为此处的禁用列表是归属于某个
                    # ServerConfig的，不存在重复名称的情况，用户有可能配置了alias，但是使用原始名称禁用。)
                    if display_name in (config.forbidden_tools or []) or original_tool_name in (config.forbidden_tools or []):
                        self._disabled_tools.add(display_name)
            except Exception as e:
                logger.error(f"Error listing tools for {server_name}: {e}")

        # 构建最终映射（处理工具名冲突）
        for tool, sources in tool_sources.items():
            if len(sources) > 1:
                logger.warning(f"Warning: Tool '{tool}' exists in multiple servers: {sources}")
                suggestion = (
                    "Please use the 'alias' feature in ToolMeta to resolve conflicts. "
                    "Each tool should have a unique name or alias across all servers."
                )
                raise ToolNameDuplicatedError(f"Tool '{tool}' exists in multiple servers: {sources}\n{suggestion}")
            self._tool_mapping[tool] = sources[0]

    async def aexecute_tool(self, tool_name: str, parameters: dict, timeout: float | None = None) -> CallToolResult:
        """执行指定工具"""
        # 检查工具是否可用
        if tool_name in self._disabled_tools:
            raise PermissionError(f"Tool '{tool_name}' is disabled by configuration")

        server_name = self._tool_mapping.get(tool_name)
        if not server_name:
            raise ValueError(f"Tool '{tool_name}' not found in any active server")

        client = self._active_clients.get(server_name)
        if not client:
            raise RuntimeError(f"Server '{server_name}' for tool '{tool_name}' is not active")

        # 如果tool_name是一个别名，则使用别名映射到原始名称
        if tool_name in self._alias_mapping:
            original_server_name, tool_name = self._alias_mapping[tool_name]
            assert original_server_name == server_name, "Alias mapping should map to the same server"

        # 获取工具元数据
        config = self._servers_config[server_name]
        tool_meta = (config.tool_meta or {}).get(tool_name)

        # 执行工具调用
        try:
            if timeout:
                result = await asyncio.wait_for(client.call_tool(tool_name, parameters), timeout)
            else:
                result = await client.call_tool(tool_name, parameters)

            # 如果有自定义元数据，则利用MCP协议返回Result中的meta元数据携带能力透传。
            if tool_meta:
                if result.meta:
                    result.meta[A2C_TOOL_META] = result.meta.get(A2C_TOOL_META, {})
                    result.meta[A2C_TOOL_META].update(tool_meta)
                else:
                    result.meta = {A2C_TOOL_META: tool_meta}
            return result
        except TimeoutError:
            raise TimeoutError(f"Tool '{tool_name}' execution timed out") from None
        except Exception as e:
            raise RuntimeError(f"Tool execution failed: {e}") from e

    def get_server_status(self) -> list[tuple[str, bool, str]]:
        """获取服务器状态列表"""
        return [
            (
                server_name,
                server_name in self._active_clients,
                "pending" if server_name not in self._active_clients else self._active_clients[server_name].state,
            )
            for server_name in self._servers_config
        ]

    async def available_tools(self) -> AsyncGenerator[Tool, Any]:
        """获取可用工具及其元数据"""
        async with self._lock:
            servers_cached_tools = defaultdict(list)
            for tool_name, server in self._tool_mapping.items():
                if server not in servers_cached_tools and server in self._active_clients:
                    client = self._active_clients[server]
                    tools = await client.list_tools()
                    servers_cached_tools[server] = tools

                config = self._servers_config[server]
                assert not config.disabled, "Server should not be disabled"

                original_server, original_tool_name = self._alias_mapping.get(tool_name) or (server, tool_name)
                assert original_server == server, "Alias mapping error"

                tool = next((t for t in tools if t.name == original_tool_name), None)
                if tool:
                    a2c_meta = config.tool_meta.get(original_tool_name)
                    if a2c_meta:
                        if tool.meta is None:
                            tool.meta = {A2C_TOOL_META: a2c_meta}
                        else:
                            tool.meta.update({A2C_TOOL_META: a2c_meta})
                    yield tool
