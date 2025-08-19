# filename: model.py
# @Time    : 2025/8/17 16:53
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import ClassVar, Protocol, TypeAlias

from mcp import StdioServerParameters, Tool
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, Field

TOOL_NAME: TypeAlias = str
SERVER_NAME: TypeAlias = str
A2C_TOOL_META: str = "a2c_tool_meta"


class ToolMeta(BaseModel):
    auto_apply: bool | None = Field(default=None, title="是否自动使用", description="如果设置为False，则调用工具前会触发回调，请求用例批准")
    alias: str | None = Field(
        default=None, title="工具别名", description="如果不同MCP Server中存在同名工具，允许通过此别名修改，从而解决名称冲突"
    )
    # 不同MCP工具返回值并不统一，虽然其满足MCP标准的返回格式，但具体的原始内容命名仍然无法避免出现不一致的情况。通过object_mapper可以方便
    # 前端对其进行转换，以使用标准组件渲染解析。
    ret_object_mapper: dict | None = Field(
        default=None, title="字段转换映射", description="允许定义一个映射表完成MCPTool工具返回结构映射到自定义结构"
    )

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


class MCPClientProtocol(Protocol):
    state: str

    async def connect(self) -> None:
        """连接MCP Server"""
        ...

    async def disconnect(self) -> None:
        """断开连接"""
        ...

    async def list_tools(self) -> list[Tool]:
        """获取可用工具列表"""
        return []

    async def call_tool(self, tool_name: str, params: dict) -> CallToolResult:
        """运行指定工具"""
        pass
