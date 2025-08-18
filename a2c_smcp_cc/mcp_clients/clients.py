# -*- coding: utf-8 -*-
# filename: clients.py
# @Time    : 2025/8/18 10:57
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm

from mcp.types import CallToolResult, Tool

from a2c_smcp_cc.mcp_clients.model import MCPServerConfig, SseServerConfig, StdioServerConfig, StreamableHttpServerConfig


class BaseMCPClient:
    async def connect(self):
        """连接到MCP服务器"""
        pass

    async def disconnect(self):
        """断开连接"""
        pass

    async def list_tools(self) -> list[Tool]:
        """获取可用工具列表"""
        return []

    async def call_tool(self, tool_name: str, params: dict) -> CallToolResult:
        """运行指定工具"""
        pass


class StdioMCPClient(BaseMCPClient):
    def __init__(self, params):
        self.params = params


class SseMCPClient(BaseMCPClient):
    def __init__(self, params):
        self.params = params


class HttpMCPClient(BaseMCPClient):
    def __init__(self, params):
        self.params = params


def client_factory(config: MCPServerConfig) -> BaseMCPClient:
    """根据配置创建客户端（伪代码实现）/Create client based on config (pseudo code implementation)"""
    # 根据实际配置创建不同类型的客户端/Create different types of clients based on the actual configuration
    match config:
        case StdioServerConfig():
            client = StdioMCPClient(config.server_parameters)
        case SseServerConfig():
            client = SseMCPClient(config.server_parameters)
        case StreamableHttpServerConfig():
            client = HttpMCPClient(config.server_parameters)
        case _:
            raise ValueError(f"Unsupported config type: {type(config)}")
    return client
