# filename: client.py
# @Time    : 2025/8/17 16:55
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
from typing import Any

from mcp.types import CallToolResult
from pydantic import TypeAdapter
from socketio import AsyncClient

from a2c_smcp.computer.computer import Computer
from a2c_smcp.computer.socketio.smcp import (
    GET_CONFIG_EVENT,
    GET_TOOLS_EVENT,
    JOIN_OFFICE_EVENT,
    LEAVE_OFFICE_EVENT,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_CONFIG_EVENT,
    EnterOfficeReq,
    GetMCPConfigReq,
    GetMCPConfigRet,
    GetToolsReq,
    GetToolsRet,
    LeaveOfficeReq,
    MCPServerInput,
    ToolCallReq,
    UpdateMCPConfigReq,
)
from a2c_smcp.computer.socketio.smcp import (
    MCPServerConfig as SMCPServerConfigDict,
)


class SMCPComputerClient(AsyncClient):
    """
    SMCP协议Computer侧的Socket.IO客户端，在创建的时候需要指定 MCPServerManager
    如果在使用Socket.IO过程中，需要实现SMCP协议，则需要使用此客户端，不能仅仅使用原生AsyncClient
    """

    def __init__(self, *args: Any, computer: Computer, **kwargs: Any) -> None:  # noqa: E112
        super().__init__(*args, **kwargs)
        self.computer = computer
        self.on(TOOL_CALL_EVENT, self.on_tool_call, namespace=SMCP_NAMESPACE)
        self.on(GET_TOOLS_EVENT, self.on_get_tools, namespace=SMCP_NAMESPACE)
        self.on(GET_CONFIG_EVENT, self.on_get_config, namespace=SMCP_NAMESPACE)
        self.office_id: str | None = None

    async def emit(self, event: str, data: Any = None, namespace: str | None = SMCP_NAMESPACE, callback: Any = None) -> None:
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
            raise ValueError("ComputerClient不允许使用notify:*事件")  # pragma: no cover
        if event.startswith("client:"):
            raise ValueError("ComputerClient不允许发起client:*事件")  # pragma: no cover
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

    async def emit_update_config(self) -> None:
        """
        当前MCP配置更新时需要触发此事件向信令服务器推送，进而触发Agent端的配置更新

        不需要传递当前的配置参数，因为Agnet会通过其它接口进行刷新
        """
        if self.office_id:
            await self.emit(UPDATE_CONFIG_EVENT, UpdateMCPConfigReq(computer=self.namespaces[SMCP_NAMESPACE]))

    async def update_config(self) -> None:
        """
        当前MCP配置更新时需要触发此事件向信令服务器推送，进而触发Agent端的配置更新

        不需要传递当前的配置参数，因为Agnet会通过其它接口进行刷新
        """
        await self.emit(UPDATE_CONFIG_EVENT, UpdateMCPConfigReq(computer=self.namespaces[SMCP_NAMESPACE]))

    async def on_tool_call(self, data: ToolCallReq) -> CallToolResult:
        """
        信令服务器通知计算机端，有工具调用请求

        Args:
            data (ToolCallReq): 请求数据
        """
        assert self.office_id == data["robot_id"], "房间名称与Agent信息名称不匹配"
        assert self.namespaces[SMCP_NAMESPACE] == data["computer"], "计算机标识不匹配"
        try:
            ret = await self.computer.aexecute_tool(
                req_id=data["req_id"], tool_name=data["tool_name"], parameters=data["params"], timeout=data["timeout"]
            )
            return ret
        except Exception as e:
            return CallToolResult(isError=True, structuredContent={"error": str(e), "error_type": type(e).__name__}, content=[])

    async def on_get_tools(self, data: GetToolsReq) -> GetToolsRet:
        """
        信令服务器通知计算机端，有工具调用请求

        Args:
            data (GetToolsReq): 请求数据
        """
        assert self.office_id == data["robot_id"], "房间名称与Agent信息名称不匹配"
        assert self.namespaces[SMCP_NAMESPACE] == data["computer"], "计算机标识不匹配"

        mcp_tools = await self.computer.aget_available_tools()

        return GetToolsRet(tools=mcp_tools, req_id=data["req_id"])

    async def on_get_config(self, data: GetMCPConfigReq) -> GetMCPConfigRet:
        """
        获取当前计算机的 MCP 配置（供 Agent 端刷新使用）。
        Get current machine MCP configuration for Agent refresh.

        中文：校验房间与计算机标识后，收集并序列化所有 MCP Server 配置，返回 SMCP 协议定义的配置结构。
        English: Validate office and computer identifiers, then collect and serialize all MCP server configs
        into SMCP protocol defined structure.

        Args:
            data (GetMCPConfigReq): 请求数据。Request payload.

        Returns:
            GetMCPConfigRet: SMCP 协议定义的 MCP 配置返回。SMCP formatted MCP configuration.
        """
        # 校验上下文一致性（中英双语）/ Validate context consistency (bilingual)
        assert self.office_id == data["robot_id"], "房间名称与Agent信息名称不匹配"
        assert self.namespaces[SMCP_NAMESPACE] == data["computer"], "计算机标识不匹配"

        servers: dict[str, dict] = {}
        # 从 Computer 中获取初始化时传入的配置集合（不可变元组）
        # From Computer, get the immutable tuple of initial MCP server configs
        for cfg in self.computer.mcp_servers:
            # 使用强校验转换为协议定义（中英文）/ Validate strictly to protocol definition (bilingual)
            # 若类型不匹配，抛出异常，属于硬性 Bug / If mismatched, raise to surface a hard bug.
            validated_server = TypeAdapter(SMCPServerConfigDict).validate_python(cfg.model_dump(mode="json"), from_attributes=True)
            servers[cfg.name] = validated_server

        inputs: list[MCPServerInput] = []
        for i in self.computer.inputs:
            validated_input = TypeAdapter(MCPServerInput).validate_python(i.model_dump(mode="json"), from_attributes=True)
            inputs.append(validated_input)

        # 端到端返回强校验（中英双语）/ End-to-end response strict validation (bilingual)
        ret = TypeAdapter(GetMCPConfigRet).validate_python({"servers": servers, "inputs": inputs})
        return ret
