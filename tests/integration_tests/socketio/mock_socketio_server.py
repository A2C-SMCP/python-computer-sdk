# -*- coding: utf-8 -*-
# filename: mock_socketio_server.py
# @Time    : 2025/8/21 14:02
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
import copy
from typing import Any

from mcp.types import CallToolResult
from pydantic import TypeAdapter
from socketio import AsyncNamespace, AsyncServer

from a2c_smcp_cc.socketio.smcp import (
    ENTER_OFFICE_NOTIFICATION,
    GET_TOOLS_EVENT,
    LEAVE_OFFICE_NOTIFICATION,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_CONFIG_NOTIFICATION,
    EnterOfficeNotification,
    EnterOfficeReq,
    GetToolsReq,
    GetToolsRet,
    LeaveOfficeNotification,
    LeaveOfficeReq,
    ToolCallReq,
    UpdateMCPConfigNotification,
    UpdateMCPConfigReq,
)
from a2c_smcp_cc.utils.logger import logger


class MockComputerServerNamespace(AsyncNamespace):
    """模拟信令服务器处理Computer Client请求"""

    def __init__(self, *args, **kwargs):
        super().__init__(namespace=SMCP_NAMESPACE)
        # key为客户端sid，tuple为(操作名称，操作返回数据)
        self.client_operations_record: dict[str, tuple[str, Any]] = {}

    async def trigger_event(self, event: str, *args: Any) -> Any:
        """触发事件 重写触发逻辑，处理冒号事件"""
        return await super().trigger_event(event.replace(":", "_"), *args)

    async def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> bool:
        self.client_operations_record[sid] = ("connect", None)
        logger.info(f"Computer Client {sid} 连接成功")
        return True

    async def on_disconnect(self, sid: str) -> None:
        self.client_operations_record[sid] = ("disconnect", None)
        logger.info(f"Computer Client {sid} 断开连接")
        rooms = self.rooms(sid)
        for room in rooms:
            if room == sid:
                # Socket.IO有自己的机制，每个客户端会进入一个同名房间。这是Socket.IO的机制，不需要客户端自己管理
                continue
            logger.info(f"Computer Client {sid} leave room {room}")
            await self.leave_room(sid, room)
        logger.info(f"SocketIO Client {sid} disconnected")

    async def enter_room(self, sid: str, room: str, namespace: str | None = None) -> None:
        """
        客户端加入房间，相较于父方法，添加了对sid的合规校验。维护session中的sid和name字段。

        Compared to the parent method, it adds checks for sid compliance and maintains the 'sid' and 'name' fields in
            the session.
        """
        logger.info(f"Computer Client {sid} enter room {room}")
        self.client_operations_record[sid] = ("enter_room", room)
        session = await self.get_session(sid)
        # 确保session中有sid字段
        # Ensure 'sid' field exists in session
        if session.get("sid") != sid:
            session["sid"] = sid
        # 确保session中有name字段（如无可用默认值）
        # Ensure 'name' field exists in session (use default if missing)
        if not session.get("name"):
            session["name"] = f"{session.get('role', 'unknown')}_{sid[:6]}"
        if session["role"] == "agent":
            # 如果sid已经存在于某个房间中，并且房间号不是当前房间号
            if session.get("office_id") and session.get("office_id") != room:
                logger.error(f"Agent sid: {sid} already in room: {session.get('office_id')}, can't join room: {room}")
                raise ValueError("Agent sid already in room")
            # 如果sid不存在于任何房间中
            elif not session.get("office_id"):
                # 获取房间内所有参与者
                participants = await self.server.manager.get_participants(SMCP_NAMESPACE, room)
                logger.debug(f"Room {room} participants: {participants}")
                agent_check_results = [(await self.get_session(s)).get("role") == "agent" async for s in participants]
                # 确保房间内没有Agent
                assert not any(agent_check_results), "Agent already in room"
            else:
                logger.warning(f"Agent sid: {sid} already in room: {session.get('office_id')}. 正在重复加入房间")
                return
        else:
            # Computer可以切换房间，但需要注意向即将离开的房间广播离开消息
            if session.get("office_id") and (past_room := session.get("office_id")) != room:
                await self.leave_room(sid, past_room)
            elif session.get("office_id") == room:
                logger.warning(f"Computer sid: {sid} already in room: {session.get('office_id')}. 正在重复加入房间")
                return
        # 加入新房间
        await super().enter_room(sid, room)
        # 保存sid与房间号的映射关系
        session["office_id"] = room
        await self.save_session(sid, session)
        # 广播加入新房间的消息至房间内其它人
        await self.emit(
            ENTER_OFFICE_NOTIFICATION,
            EnterOfficeNotification(office_id=room, computer=sid),
            skip_sid=sid,
            room=room,
        )

    async def leave_room(self, sid: str, room: str, namespace: str | None = None) -> None:
        """在离开房间之前发布离开消息"""
        self.client_operations_record[sid] = ("leave_room", room)
        session = await self.get_session(sid)
        notification = (
            LeaveOfficeNotification(office_id=room, computer=sid)
            if session.get("role") == "computer"
            else LeaveOfficeNotification(office_id=room, agent=sid)
        )
        await self.emit(LEAVE_OFFICE_NOTIFICATION, notification, skip_sid=sid, room=room)
        # 维护session中的office_id字段
        del session["office_id"]
        await self.save_session(sid, session)
        await super().leave_room(sid, room)

    async def on_server_join_office(self, sid: str, data: EnterOfficeReq) -> tuple[bool, str | None]:
        """Computer加入Office"""
        self.client_operations_record[sid] = ("server_join_office", data)
        role_info = TypeAdapter(EnterOfficeReq).validate_python(data)
        expected_role = role_info["role"]

        session = await self.get_session(sid)
        backup_session = copy.deepcopy(session)
        try:
            if session.get("role") and session["role"] != expected_role:
                return False, f"Role mismatch, expected {expected_role}, but {session['role']} use this sid exists"

            session["role"] = expected_role
            session["name"] = role_info["name"]
            await self.save_session(sid, session)
            await self.enter_room(sid, role_info["office_id"])
            return True, None
        except Exception as e:
            await self.save_session(sid, backup_session)
            return False, f"Internal server error: {str(e)}"

    async def on_server_leave_office(self, sid: str, data: LeaveOfficeReq) -> tuple[bool, str | None]:
        """
        事件名：server:leave_office 由全局变量 LEAVE_OFFICE_EVENT 定义
        Computer或者Agent离开房间，为了突显smcp的办公特性，因此离开房间的动作命名为leave_office

        Args:
            sid (str): 客户端ID 可能是 Computer或者Agent
            data (dict): 离开房间的数据

        Returns:
            tuple[bool, Optional[str]]: 返回是否允许离开房间，以及可能的错误信息
        """
        self.client_operations_record[sid] = ("server_leave_office", data)
        try:
            await self.leave_room(sid, data["office_id"])
        except Exception as e:
            return False, f"Internal server error: {str(e)}"
        return True, None

    async def on_server_update_config(self, sid: str, data: UpdateMCPConfigReq) -> None:
        """处理Computer更新MCP配置事件"""
        self.client_operations_record[sid] = ("server_update_config", data)
        logger.info(f"Computer {sid} 更新了MCP配置")
        session = await self.get_session(sid)
        assert session["role"] == "computer", "目前仅支持Computer调用更新MCP配置的操作"
        update_config = TypeAdapter(UpdateMCPConfigReq).validate_python(data)
        await self.emit(
            UPDATE_CONFIG_NOTIFICATION,
            UpdateMCPConfigNotification(computer=update_config["computer"]),
            room=session["office_id"],
            skip_sid=sid,
        )

    async def on_client_tool_call(self, sid: str, data: ToolCallReq) -> CallToolResult:
        """处理来自Agent的工具调用请求"""
        logger.debug(f"收到来自Agent的工具调用请求: {data['tool_name']}")
        session = await self.get_session(sid)
        assert session["role"] == "agent", "目前仅支持Agent调用工具"
        tool_call = TypeAdapter(ToolCallReq).validate_python(data)
        return await self.call(TOOL_CALL_EVENT, tool_call, to=tool_call["computer"], timeout=tool_call["timeout"])

    async def on_client_get_tools(self, sid: str, data: GetToolsReq) -> GetToolsRet:
        """处理获取工具请求"""
        logger.debug(f"收到来自Computer的获取工具请求: {data}")
        computer_sid = data["computer"]
        session = await self.get_session(computer_sid)
        assert session["role"] == "computer", "目前仅支持Computer获取工具列表"
        assert session["agent_id"] == sid, "目前仅支持Agent获取自己房间内Computer的工具列表"
        client_response = await self.call(GET_TOOLS_EVENT, data, to=data["computer"], namespace=SMCP_NAMESPACE)
        return TypeAdapter(GetToolsRet).validate_python(client_response)


def create_computer_test_socketio() -> AsyncServer:
    """创建用于测试Computer Client的Socket.IO服务器"""

    sio = AsyncServer(
        async_mode="asgi",
        logger=True,
        engineio_logger=True,
        cors_allowed_origins="*",
        ping_timeout=10,
        ping_interval=10,
        async_handlers=True,
    )

    namespace = MockComputerServerNamespace()
    sio.register_namespace(namespace)

    return sio
