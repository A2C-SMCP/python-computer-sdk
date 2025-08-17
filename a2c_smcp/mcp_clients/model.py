# filename: model.py
# @Time    : 2025/8/17 16:53
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import TypeAlias

from mcp import StdioServerParameters
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from pydantic import BaseModel, Field

TOOL_NAME: TypeAlias = str


class ToolMeta(BaseModel):
    auto_apply: bool | None
    # 不同MCP工具返回值并不统一，虽然其满足MCP标准的返回格式，但具体的原始内容命名仍然无法避免出现不一致的情况。通过object_mapper可以方便前端对其进行转换，以使用标准组件渲染解析。
    ret_object_mapper: dict | None


class BaseMCPServerConfig(BaseModel):
    """MCP服务器配置基类"""

    name: str  # MCP Server的名称
    disabled: bool
    forbidden_tools: list[str]  # 禁用的工具列表，因为一个mcp可能有非常多工具，有些工具用户需要禁用。
    tool_meta: dict[TOOL_NAME, ToolMeta]


class StdioClientConfig(BaseMCPServerConfig):
    server_parameters: StdioServerParameters = Field(title="MCP Server启动参数", description="引用自MCP Python SDK官方配置")


class SseClientConfig(BaseMCPServerConfig):
    server_parameters: SseServerParameters = Field(title="MCP SSE Server连接参数", description="引用自MCP Python SDK 官方配置")


class StreamableHttpConfig(BaseMCPServerConfig):
    server_parameters: StreamableHttpParameters = Field(title="MCP HTTP Server连接参数", description="引用自MCP Python SDK 官方配置")


ServerParameters: TypeAlias = StdioServerParameters | SseServerParameters | StreamableHttpParameters
