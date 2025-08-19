# -*- coding: utf-8 -*-
# filename: stdio_client.py
# @Time    : 2025/8/19 10:55
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from collections.abc import Awaitable, Callable

from mcp import ClientSession, StdioServerParameters, stdio_client
from transitions.core import EventData

from a2c_smcp_cc.mcp_clients.base_client import BaseMCPClient
from a2c_smcp_cc.utils.logger import logger


class StdioMCPClient(BaseMCPClient):
    def __init__(
        self, params: StdioServerParameters, state_change_callback: Callable[[str, str], None | Awaitable[None]] | None = None
    ) -> None:
        assert isinstance(params, StdioServerParameters), "params must be an instance of StdioServerParameters"
        super().__init__(params, state_change_callback)

    async def abefore_connect(self, event: EventData) -> None:
        """
        尝试以self.params为参数启动 MCP Server

        Args:
            event (EventData): Transitions事件
        """
        logger.debug(f"Before connection actions with event: {event}\n\nserver params: {self.params}")
        stdout, stdin = await self.aexit_stack.enter_async_context(stdio_client(self.params))
        client_session = await self.aexit_stack.enter_async_context(ClientSession(stdout, stdin))
        # 将新建的ClientSession寄存在 event.kwargs 中
        event.kwargs["client_session"] = client_session

    async def on_enter_connected(self, event: EventData) -> None:
        """
        状态机进入连接状态时的回调

        Args:
            event (EventData): Transitions事件
        """
        logger.debug(f"Entered connected state with event: {event}\n\nserver params: {self.params}")
        # 使用event.kwargs中的标准输出与标准输入初始化 self._async_session
        self._async_session = event.kwargs["client_session"]
        await (await self.async_session).initialize()
