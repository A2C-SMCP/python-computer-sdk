# -*- coding: utf-8 -*-
# filename: base_client.py
# @Time    : 2025/8/18 10:57
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
import asyncio
from collections.abc import Awaitable, Callable
from contextlib import AsyncExitStack
from enum import StrEnum
from typing import cast

from mcp import ClientSession, Tool
from mcp.types import CallToolResult
from pydantic import BaseModel
from transitions.core import EventData
from transitions.extensions import AsyncMachine

from a2c_smcp_cc.utils.async_property import async_property
from a2c_smcp_cc.utils.logger import logger


class STATES(StrEnum):
    initialized = "initialized"
    connected = "connected"
    disconnected = "disconnected"
    error = "error"


TRANSITIONS = [
    {
        "trigger": "aconnect",
        "source": STATES.initialized,
        "dest": STATES.connected,
        "prepare": "aprepare_connect",
        "conditions": "acan_connect",
        "before": "abefore_connect",
        "after": "aafter_connect",
    },
    {
        "trigger": "adisconnect",
        "source": STATES.connected,
        "dest": STATES.disconnected,
        "prepare": "aprepare_disconnect",
        "conditions": "acan_disconnect",
        "before": "abefore_disconnect",
        "after": "aafter_disconnect",
    },
    {
        "trigger": "aerror",
        "source": "*",
        "dest": STATES.error,
        "prepare": "aprepare_error",
        "conditions": "acan_error",
        "before": "abefore_error",
        "after": "aafter_error",
    },
    {
        "trigger": "ainitialize",
        "source": "*",
        "dest": STATES.initialized,
        "prepare": "aprepare_initialize",
        "conditions": "acan_initialize",
        "before": "abefore_initialize",
        "after": "aafter_initialize",
    },
]


class A2CAsyncMachine(AsyncMachine):
    @staticmethod
    async def await_all(callables: list[Callable]) -> list:
        """
        Executes callables without parameters in parallel and collects their results.

        A2C协议中，需要在状态机的状态变化函数之间管理异步上下文，但由于原生实现 await_all 方法使用 asyncio.gather会导致上下文打开与关闭处于
            不同的async task中进而导致关闭异常。因此重写此实现，将await_all方法变为同步执行。以此实现上下文打开与关闭处于同一个async task中

        Args:
            callables (list): A list of callable functions

        Returns:
            list: A list of results. Using asyncio the list will be in the same order as the passed callables.
        """
        ret = []
        for c in callables:
            ret.append(await c())
        return ret


class BaseMCPClient:
    def __init__(self, params: BaseModel, state_change_callback: Callable[[str, str], None | Awaitable[None]] | None = None) -> None:
        """
        基类初始化

        Attributes:
            params (BaseModel): MCP Server启动参数
            state_change_callback (Callable[[str, str], None | Awaitable[None]]): 状态变化回调，兼容同步与异步
        """
        self.params = params
        self._state_change_callback = state_change_callback
        self.aexit_stack = AsyncExitStack()
        self._async_session: ClientSession | None = None

        # 初始化异步状态机
        self.machine = A2CAsyncMachine(
            model=self,
            states=STATES,
            transitions=TRANSITIONS,
            initial=STATES.initialized,
            send_event=True,  # 传递事件对象给回调
            auto_transitions=False,  # 禁用自动生成的状态转移
            ignore_invalid_triggers=False,  # 忽略无效触发器
        )

    async def _trigger_state_change(self, event: EventData) -> None:
        """
        触发状态变化回调，兼容同步与异步

        Args:
            event (EventData): 事件对象
        """
        if not self._state_change_callback:
            return

        callback_result = self._state_change_callback(event.transition.source, event.transition.dest)
        # 处理异步回调
        if isinstance(callback_result, Awaitable):
            await callback_result

    @async_property
    async def async_session(self) -> ClientSession:
        """
        异步会话对象

        Returns:
            ClientSession: MCP 官方异步会话，用于触发 MCP Server 指令
        """
        if self._async_session is None:
            await self.aconnect()
        return cast(ClientSession, self._async_session)

    # region 状态转换回调函数基类实现
    async def aprepare_connect(self, event: EventData) -> None:
        """连接准备操作（可重写）"""
        logger.debug(f"Preparing connection with event: {event}\n\nserver params: {self.params}")

    async def acan_connect(self, event: EventData) -> bool:
        """连接条件检查（可重写）"""
        logger.debug(f"Checking connection conditions with event: {event}\n\nserver params: {self.params}")
        return True

    async def abefore_connect(self, event: EventData) -> None:
        """连接前操作（可重写）"""
        logger.debug(f"Before connection actions with event: {event}\n\nserver params: {self.params}")

    async def on_enter_connected(self, event: EventData) -> None:
        """进入已连接状态（可重写）"""
        logger.debug(f"Entering connected state with event: {event}\n\nserver params: {self.params}")

    async def aafter_connect(self, event: EventData) -> None:
        """连接后操作（可重写）"""
        logger.debug(f"After connection actions with event: {event}\n\nserver params: {self.params}")
        await self._trigger_state_change(event)

    async def aprepare_disconnect(self, event: EventData) -> None:
        """断开准备操作（可重写）"""
        logger.debug(f"Preparing disconnection with event: {event}\n\nserver params: {self.params}")

    async def acan_disconnect(self, event: EventData) -> bool:
        """断开条件检查（可重写）"""
        logger.debug(f"Checking disconnection conditions with event: {event}\n\nserver params: {self.params}")
        return (await self.async_session) is not None

    async def abefore_disconnect(self, event: EventData) -> None:
        """断开前操作（可重写）"""
        logger.debug(f"Before disconnection actions with event: {event}\n\nserver params: {self.params}")

    async def on_enter_disconnected(self, event: EventData) -> None:
        """状态机进入断开状态时的回调（可重写）"""
        logger.debug(f"Entering disconnected state with event: {event}\n\nserver params: {self.params}")
        # 关闭异步会话，保证资源的正常释放
        logger.debug(f"Enter disconnected state async task: {asyncio.current_task().get_name()}")
        await self.aexit_stack.aclose()
        self._async_session = None

    async def aafter_disconnect(self, event: EventData) -> None:
        """断开后操作（可重写）"""
        logger.debug(f"After disconnection actions with event: {event}\n\nserver params: {self.params}")
        await self._trigger_state_change(event)

    async def aprepare_error(self, event: EventData) -> None:
        """错误准备操作（可重写）"""
        logger.debug(f"Preparing error with event: {event}\n\nserver params: {self.params}")

    async def acan_error(self, event: EventData) -> bool:
        """错误条件检查（可重写）"""
        logger.debug(f"Checking error conditions with event: {event}\n\nserver params: {self.params}")
        return True

    async def abefore_error(self, event: EventData) -> None:
        """错误前操作（可重写）"""
        logger.debug(f"Before error actions with event: {event}\n\nserver params: {self.params}")

    async def on_enter_error(self, event: EventData) -> None:
        """状态机进入错误状态时的回调（可重写）"""
        logger.debug(f"Entered error state with event: {event}\n\nserver params: {self.params}")
        # 关闭异步会话，保证资源的正常释放
        await self.aexit_stack.aclose()

    async def aafter_error(self, event: EventData) -> None:
        """错误后操作（可重写）"""
        logger.debug(f"After error actions with event: {event}\n\nserver params: {self.params}")
        await self._trigger_state_change(event)

    async def aprepare_initialize(self, event: EventData) -> None:
        """初始化准备操作（可重写）"""
        logger.debug(f"Preparing initialization with event: {event}\n\nserver params: {self.params}")

    async def acan_initialize(self, event: EventData) -> bool:
        """初始化条件检查（可重写）"""
        logger.debug(f"Checking initialization conditions with event: {event}\n\nserver params: {self.params}")
        return True

    async def abefore_initialize(self, event: EventData) -> None:
        """初始化前操作（可重写）"""
        logger.debug(f"Before initialization actions with event: {event}\n\nserver params: {self.params}")

    async def on_enter_initialized(self, event: EventData) -> None:
        """状态机进入初始化状态时的回调（可重写）"""
        logger.debug(f"Entered initialized state with event: {event}\n\nserver params: {self.params}")
        # 关闭异步会话，保证资源的正常释放
        await self.aexit_stack.aclose()
        self._async_session = None

    async def aafter_initialize(self, event: EventData) -> None:
        """初始化后操作（可重写）"""
        logger.debug(f"After initialization actions with event: {event}\n\nserver params: {self.params}")
        await self._trigger_state_change(event)

    async def list_tools(self) -> list[Tool]:
        """
        获取可用工具列表，MCP协议获取接口可分页，在此会尝试获取所有。对于大模型使用场景而言，需要一次性给出所有可用工具，没有必要分页，如果数据量过大，则属于设计问题。

        Returns:
            list[Tool]: 工具列表
        """
        if self.state != STATES.connected:
            raise ConnectionError("Not connected to server")
        tools: list[Tool] = []
        asession = cast(ClientSession, await self.async_session)
        ret = await asession.list_tools()
        tools.extend(ret.tools)
        while ret.nextCursor:
            ret = await asession.list_tools(cursor=ret.nextCursor)
            tools.extend(ret.tools)
        return tools

    async def call_tool(self, tool_name: str, params: dict) -> CallToolResult:
        """
        运行指定工具（子类必须实现）

        在此不需要再考虑工具Alias的问题，由外层Manager进行处理，因此直接尝试调用触发MCP协议即可

        Args:
            tool_name (str): 被调用的工具名称
            params (dict): 调用参数

        Returns:
            CallToolResult: 调用结果 MCP 协议标准制定
        """
        if self.state != STATES.connected:
            raise ConnectionError("Not connected to server")
        return await (await self.async_session).call_tool(tool_name, params)
