# filename: client.py
# @Time    : 2025/8/17 16:55
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import Any

from mcp.types import CallToolResult
from socketio import AsyncClient

from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.socketio.smcp import (
    GET_MCP_CONFIG_EVENT,
    GET_TOOLS_EVENT,
    JOIN_OFFICE_EVENT,
    LEAVE_OFFICE_EVENT,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_MCP_CONFIG_EVENT,
    EnterOfficeReq,
    GetMCPConfigReq,
    GetMCPConfigRet,
    GetToolsReq,
    GetToolsRet,
    LeaveOfficeReq,
    ToolCallReq,
    UpdateMCPConfigReq,
)


class SMCPComputerClient(AsyncClient):
    """
    SMCP协议Computer侧的Socket.IO客户端，在创建的时候需要指定 MCPServerManager
    如果在使用Socket.IO过程中，需要实现SMCP协议，则需要使用此客户端，不能仅仅使用原生AsyncClient
    """

    def __init__(self, *args: Any, mcp_manager: MCPServerManager, **kwargs: Any) -> None:  # noqa: E112
        super().__init__(*args, **kwargs)
        self.mcp_manager = mcp_manager
        self.on(TOOL_CALL_EVENT, self.on_tool_call, namespace=SMCP_NAMESPACE)
        self.on(GET_MCP_CONFIG_EVENT, self.on_get_mcp_config, namespace=SMCP_NAMESPACE)
        self.on(GET_TOOLS_EVENT, self.on_get_tools, namespace=SMCP_NAMESPACE)
        self.office_id: str | None = None

    async def emit(self, event: str, data: Any = None, namespace: str | None = None, callback: Any = None) -> None:
        """
        相较于父类方法，提供一个event校验能力，在A2C-smcp协议内，Computer客户端不允许发起 notify:* 事件与 client:* 事件

        A2C-smcp协议内：
            notify:* 事件由信令服务器发起，用于通知客户端
            client:* 事件由ComputerClient执行，一般会给出执行结果
            agent:* 事件由AgentClient执行，一般会给出执行结果
            server:* 事件由服务管理器执行，但一般不需要给出执行结果

        Args:
            event (str): 发送的事件名称
            data (Any): 发送的数据
            namespace (str | None): 命名空间
            callback (Any): 回调
        """
        if event.startswith("notify:"):
            raise ValueError("ComputerClient不允许使用notify:*事件")
        if event.startswith("client:"):
            raise ValueError("ComputerClient不允许发起client:*事件")
        await super().emit(event, data, namespace, callback)

    async def join_office(self, office_id: str, computer_name: str) -> None:
        """
        加入一个Office（Socket.IO中的Room）

        Args:
            office_id (str): 房间ID，在A2C-smcp协议中，OfficeID即为Socket.IO RoomID，并且与 AgentID保持一致
            computer_name (str): 计算机名称，需要注意在整体通信中，Computer的标识一般使用sid。computer_name是提供给前端展示用，
                因此不般不作为唯一标识使用
        """
        await self.emit(JOIN_OFFICE_EVENT, EnterOfficeReq(office_id=office_id, role="computer", name=computer_name))
        self.office_id = office_id

    async def leave_office(self, office_id: str) -> None:
        """
        离开一个Office（Socket.IO中的Room）

        Args:
            office_id (str): 房间ID
        """
        await self.emit(LEAVE_OFFICE_EVENT, LeaveOfficeReq(office_id=office_id))
        self.office_id = None

    async def update_mcp_config(self) -> None:
        """
        当前MCP配置更新时需要触发此事件向信令服务器推送，进而触发Agent端的配置更新

        不需要传递当前的配置参数，因为Agnet会通过其它接口进行刷新
        """
        await self.emit(UPDATE_MCP_CONFIG_EVENT, UpdateMCPConfigReq(computer=self.sid))

    async def on_tool_call(self, data: ToolCallReq) -> CallToolResult:
        """
        信令服务器通知计算机端，有工具调用请求

        Args:
            data (ToolCallReq): 请求数据
        """
        assert self.office_id == data["robot_id"], "房间名称与Agent信息名称不匹配"
        assert self.sid == data["computer"], "计算机标识不匹配"
        try:
            return await self.mcp_manager.aexecute_tool(tool_name=data["tool_name"], parameters=data["params"], timeout=data["timeout"])
        except Exception as e:
            return CallToolResult(isError=True, structuredContent={"error": str(e), "error_type": type(e).__name__}, content=[])

    async def on_get_mcp_config(self, data: GetMCPConfigReq) -> GetMCPConfigRet:
        """
        信令服务器通知计算机端，有工具调用请求

        Args:
            data (GetMCPConfigReq): 请求数据
        """
        ...

    async def on_get_tools(self, data: GetToolsReq) -> GetToolsRet:
        """
        信令服务器通知计算机端，有工具调用请求

        Args:
            data (GetToolsReq): 请求数据
        """
        ...
