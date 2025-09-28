# filename: model.py
# @Time    : 2025/8/17 16:53
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import ClassVar, Literal, Protocol, TypeAlias, runtime_checkable

from mcp import StdioServerParameters, Tool
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from mcp.types import CallToolResult
from pydantic import BaseModel, ConfigDict, Field

from a2c_smcp.computer.types import SERVER_NAME, TOOL_NAME

A2C_TOOL_META: str = "a2c_tool_meta"


class ToolMeta(BaseModel):
    auto_apply: bool | None = Field(default=None, title="是否自动使用", description="如果设置为False，则调用工具前会触发回调，请求用户批准")
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
    disabled: bool = Field(default=False, title="是否禁用", description="是否禁用MCP Server")
    forbidden_tools: list[TOOL_NAME] = Field(
        default_factory=list, title="禁用工具列表", description="禁用的工具列表，因为一个mcp可能有非常多工具，有些工具用户需要禁用。"
    )
    tool_meta: dict[TOOL_NAME, ToolMeta] = Field(default_factory=dict, title="工具元数据", description="工具元数据，用于描述工具的基本信息")
    # 默认工具元数据（可选）。当某个具体工具未在 tool_meta 中提供专门配置时，使用该默认配置。
    # Default tool metadata (optional). Used when a specific tool has no explicit entry in tool_meta.
    default_tool_meta: ToolMeta | None = Field(default=None)

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=False, frozen=True)
    """配置字段在初始化完成后不允许修改"""

    def __hash__(self) -> int:
        """对于MCP Server配置，以name作为唯一标识凭证，如果name相同则表示完全相同"""
        return hash(self.name)


class StdioServerConfig(BaseMCPServerConfig):
    type: Literal["stdio"] = "stdio"
    server_parameters: StdioServerParameters = Field(title="MCP Server启动参数", description="引用自MCP Python SDK官方配置")


class SseServerConfig(BaseMCPServerConfig):
    type: Literal["sse"] = "sse"
    server_parameters: SseServerParameters = Field(title="MCP SSE Server连接参数", description="引用自MCP Python SDK 官方配置")


class StreamableHttpServerConfig(BaseMCPServerConfig):
    type: Literal["streamable"] = "streamable"
    server_parameters: StreamableHttpParameters = Field(title="MCP HTTP Server连接参数", description="引用自MCP Python SDK 官方配置")


MCPServerConfig: TypeAlias = StdioServerConfig | SseServerConfig | StreamableHttpServerConfig


class MCPServerInputBase(BaseModel):
    """MCP服务器输入项配置基类"""

    id: str
    """Input的唯一标准，即使跨类型，也不可重复"""
    description: str

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", arbitrary_types_allowed=False, frozen=True)
    """配置字段在初始化完成后不允许修改"""

    def __hash__(self) -> int:
        """以 id 作为唯一哈希，确保在 set 中按 id 去重"""
        return hash(self.id)

    def __eq__(self, other: object) -> bool:
        """按 id 判断相等性，确保不同内容但相同 id 的输入在集合中视为同一元素"""
        if not isinstance(other, MCPServerInputBase):
            return False
        return self.id == other.id


class MCPServerPromptStringInput(MCPServerInputBase):
    """字符串输入类型，参考：https://code.visualstudio.com/docs/reference/variables-reference#_input-variables"""

    type: Literal["promptString"] = Field(default="promptString")
    default: str | None = Field(default=None)
    password: bool | None = Field(default=None)


class MCPServerPickStringInput(MCPServerInputBase):
    """选择输入类型，参考：https://code.visualstudio.com/docs/reference/variables-reference#_input-variables"""

    type: Literal["pickString"] = Field(default="pickString")
    options: list[str] = Field(default_factory=list)
    default: str | None = Field(default=None)


class MCPServerCommandInput(MCPServerInputBase):
    """命令输入类型，参考：https://code.visualstudio.com/docs/reference/variables-reference#_input-variables"""

    type: Literal["command"] = Field(default="command")
    command: str = Field(title="")
    args: dict[str, str] | None = Field(default=None)


MCPServerInput = MCPServerPromptStringInput | MCPServerPickStringInput | MCPServerCommandInput


@runtime_checkable
class MCPClientProtocol(Protocol):
    state: str

    async def aconnect(self) -> None:
        """连接MCP Server"""
        ...

    async def adisconnect(self) -> None:
        """断开连接"""
        ...

    async def list_tools(self) -> list[Tool]:
        """获取可用工具列表"""
        return []

    async def call_tool(self, tool_name: str, params: dict) -> CallToolResult:
        """运行指定工具"""
        pass
