# -*- coding: utf-8 -*-
# filename: utils.py
# @Time    : 2025/8/19 10:54
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from a2c_smcp.computer.mcp_clients.base_client import BaseMCPClient
from a2c_smcp.computer.mcp_clients.http_client import HttpMCPClient
from a2c_smcp.computer.mcp_clients.model import MCPServerConfig, SseServerConfig, StdioServerConfig, StreamableHttpServerConfig
from a2c_smcp.computer.mcp_clients.sse_client import SseMCPClient
from a2c_smcp.computer.mcp_clients.stdio_client import StdioMCPClient


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
            raise ValueError(f"Unsupported config type: {type(config)}")  # noqa
    return client
