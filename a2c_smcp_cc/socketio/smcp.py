# -*- coding: utf-8 -*-
# filename: smcp.py
# @Time    : 2025/8/8 12:35
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from typing import Any, Literal, NotRequired, TypeAlias

from typing_extensions import TypedDict

from a2c_smcp_cc.socketio import types

SMCP_NAMESPACE = "/smcp"
# 除了notify:外的所有事件 服务端必须实现，因为由服务端转换或者执行完毕。而notify:*事件均由Server发出，因此Server不需要实现
# 客户端事件 由client:开头的事件ComputerClient必须全部实现，一般由AgentClient触发，由Server转发。client: 开头的事件，会由特定的某一个
# ComputerClient执行
# 一般data中会明确指定computer的sid用于执行此事件，如果需要多个client执行，一般是通过server:事件触发，广播至房间内的所有Computer
TOOL_CALL_EVENT = "client:tool_call"
GET_MCP_CONFIG_EVENT = "client:get_mcp_config"
GET_TOOLS_EVENT = "client:get_tools"
# 服务端事件 由server:开头的事件服务端执行
JOIN_OFFICE_EVENT = "server:join_office"
LEAVE_OFFICE_EVENT = "server:leave_office"
UPDATE_MCP_CONFIG_EVENT = "server:update_mcp_config"
CANCEL_TOOL_CALL_EVENT = "server:tool_call_cancel"
# NOTIFY 通知事件  通知事件全部由Server发出（一般由Client触发其它事件，在响应这些事件时，Server发出通知）
#   1. 比如 AgentClient 发出 server:tool_call_cancel 事件，服务端接收后，发起 notify:tool_call_cancel 通知
#   2. 比如 ComputerClient 发出 server:join_office 事件，服务端接收后，发起 notify:enter_office 通知
# AgentClient与ComputerClient选择性接收。因为Notify均由Server发出，因此Server中不需要实现对应接收方法
CANCEL_TOOL_CALL_NOTIFICATION = "notify:tool_call_cancel"
ENTER_OFFICE_NOTIFICATION = "notify:enter_office"  # AgentClient必须实现 以此，配合 client:get_mcp_config 与 client:get_tools 更新工具配置
LEAVE_OFFICE_NOTIFICATION = "notify:leave_office"  # AgentClient必须实现 以此，配合 client:get_mcp_config 与 client:get_tools 更新工具配置
UPDATE_MCP_CONFIG_NOTIFICATION = (
    "notify:update_mcp_config"  # AgentClient必须实现 以此，配合 client:get_mcp_config 与 client:get_tools 更新工具配置
)


class AgentCallData(TypedDict):
    robot_id: str
    req_id: str


class ToolCallReq(AgentCallData):
    computer: str
    tool_name: str
    params: dict
    timeout: int


class GetToolsReq(AgentCallData):
    computer: str


class SMCPTool(TypedDict):
    """在Computer端侧管理多个MCP时，无法保证ToolName不重复。因此alias字段被添加以帮助用户进行区分不同工具。如果alias被设置，创建工具时将会使用alias。"""

    name: str
    description: str
    params_schema: dict
    return_schema: dict | None
    meta: NotRequired[types.Attributes]


class GetToolsRet(TypedDict):
    tools: list[SMCPTool]
    req_id: str


class EnterOfficeReq(TypedDict):
    role: Literal["computer", "agent"]
    name: str
    office_id: str


class LeaveOfficeReq(TypedDict):
    office_id: str


class UpdateMCPConfigReq(TypedDict):
    computer: str  # 机器人计算机sid


# --- MCPServer 配置，参考借鉴： ---
# VSCode: https://code.visualstudio.com/docs/copilot/chat/mcp-servers#_configuration-format
# AWS Q Developer: https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/mcp-ide.html


class MCPServerInputBase(TypedDict):
    """MCP服务器输入配置基类"""

    id: str
    description: str


class MCPServerPromptStringInput(MCPServerInputBase):
    """字符串输入类型"""

    type: Literal["promptString"]
    default: NotRequired[str]
    password: NotRequired[bool]


class MCPServerPickStringInput(MCPServerInputBase):
    """选择输入类型"""

    type: Literal["pickString"]
    options: list[str]
    default: NotRequired[str]


class MCPServerCommandInput(MCPServerInputBase):
    """命令输入类型"""

    type: Literal["command"]
    command: str
    args: NotRequired[dict[str, str]]


MCPServerInput = MCPServerPromptStringInput | MCPServerPickStringInput | MCPServerCommandInput

TOOL_NAME: TypeAlias = str


class ToolMeta(TypedDict, total=False):
    auto_apply: NotRequired[bool]
    # 不同MCP工具返回值并不统一，虽然其满足MCP标准的返回格式，但具体的原始内容命名仍然无法避免出现不一致的情况。通过object_mapper
    # 可以方便前端对其进行转换，以使用标准组件渲染解析。
    ret_object_mapper: NotRequired[dict]


class BaseMCPServerConfig(TypedDict):
    """MCP服务器配置基类"""

    disabled: bool
    forbidden_tools: list[str]  # 禁用的工具列表，因为一个mcp可能有非常多工具，有些工具用户需要禁用。
    tool_meta: dict[TOOL_NAME, ToolMeta]


class MCPServerStdioParameters(TypedDict):
    command: str
    """The executable to run to start the server."""
    args: list[str]
    """Command line arguments to pass to the executable."""
    env: dict[str, str] | None
    """
    The environment to use when spawning the process.

    If not specified, the result of get_default_environment() will be used.
    """
    cwd: str | None
    """The working directory to use when spawning the process."""
    encoding: str
    """
    The text encoding used when sending/receiving messages to the server

    defaults to utf-8
    """
    encoding_error_handler: Literal["strict", "ignore", "replace"]
    """
    The text encoding error handler.

    See https://docs.python.org/3/library/codecs.html#codec-base-classes for
    explanations of possible values
    """


class MCPServerStdioConfig(BaseMCPServerConfig):
    """标准输入输出模式的MCP服务器配置"""

    type: Literal["stdio"]
    server_parameters: MCPServerStdioParameters


class MCPServerStreamableHttpParameters(TypedDict):
    # The endpoint URL.
    url: str
    # Optional headers to include in requests.
    headers: dict[str, Any] | None
    # HTTP timeout for regular operations.
    timeout: float
    # Timeout for SSE read operations.
    sse_read_timeout: float
    # Close the client session when the transport closes.
    terminate_on_close: bool


class MCPServerStreamableHttpConfig(BaseMCPServerConfig):
    """StreamableHttpHTTP模式的MCP服务器配置"""

    type: Literal["streamable_http"]
    server_parameters: MCPServerStreamableHttpParameters


class MCPSSEParameters(TypedDict):
    # The endpoint URL.
    url: str
    # Optional headers to include in requests.
    headers: dict[str, Any] | None
    # HTTP timeout for regular operations.
    timeout: float
    # Timeout for SSE read operations.
    sse_read_timeout: float


class MCPSSEConfig(BaseMCPServerConfig):
    """SSE模式的MCP服务器配置"""

    type: Literal["sse"]
    server_parameters: MCPSSEParameters


MCPServerConfig = MCPServerStdioConfig | MCPServerStreamableHttpConfig | MCPSSEConfig


class GetMCPConfigReq(AgentCallData):
    computer: str


class GetMCPConfigRet(TypedDict):
    """完整的MCP配置文件类型"""

    inputs: NotRequired[list[MCPServerInput]]
    servers: dict[str, MCPServerConfig]


class LeaveOfficeNotification(TypedDict, total=False):
    """Agent或者Computer离开房间的通知，需要向房间内其他人广播。广播时间为真实离开之前，也就是即将离开"""

    office_id: str
    computer: str | None
    agent: str | None


class EnterOfficeNotification(TypedDict, total=False):
    """Agent或者Computer加入房间的通知，需要向房间内其他人广播。广播时间为真实加入之后"""

    office_id: str
    computer: str | None
    agent: str | None


class UpdateMCPConfigNotification(TypedDict, total=False):
    """
    MCP配置更新的通知，需要向房间内其他人广播
    """

    computer: str  # 被更新的Computer sid
