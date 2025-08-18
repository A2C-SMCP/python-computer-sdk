# filename: model.py
# @Time    : 2025/8/17 16:53
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import ClassVar, TypeAlias

from mcp import StdioServerParameters
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from pydantic import BaseModel, ConfigDict, Field

TOOL_NAME: TypeAlias = str
SERVER_NAME: TypeAlias = str
A2C_TOOL_META: str = "a2c_tool_meta"


class ToolMeta(BaseModel):
    auto_apply: bool | None
    alias: str | None
    # 不同MCP工具返回值并不统一，虽然其满足MCP标准的返回格式，但具体的原始内容命名仍然无法避免出现不一致的情况。通过object_mapper可以方便
    # 前端对其进行转换，以使用标准组件渲染解析。
    ret_object_mapper: dict | None

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow", arbitrary_types_allowed=False)


class BaseMCPServerConfig(BaseModel):
    """MCP服务器配置基类"""

    name: SERVER_NAME  # MCP Server的名称
    disabled: bool
    forbidden_tools: list[TOOL_NAME]  # 禁用的工具列表，因为一个mcp可能有非常多工具，有些工具用户需要禁用。
    tool_meta: dict[TOOL_NAME, ToolMeta]


class StdioServerConfig(BaseMCPServerConfig):
    server_parameters: StdioServerParameters = Field(title="MCP Server启动参数", description="引用自MCP Python SDK官方配置")


class SseServerConfig(BaseMCPServerConfig):
    server_parameters: SseServerParameters = Field(title="MCP SSE Server连接参数", description="引用自MCP Python SDK 官方配置")


class StreamableHttpServerConfig(BaseMCPServerConfig):
    server_parameters: StreamableHttpParameters = Field(title="MCP HTTP Server连接参数", description="引用自MCP Python SDK 官方配置")


MCPServerConfig: TypeAlias = StdioServerConfig | SseServerConfig | StreamableHttpServerConfig
