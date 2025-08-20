# -*- coding: utf-8 -*-
# filename: sse_client.py
# @Time    : 2025/8/19 10:55
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from collections.abc import Callable

from mcp import ClientSession
from mcp.client.session_group import SseServerParameters
from mcp.client.sse import sse_client
from transitions import EventData

from a2c_smcp_cc.mcp_clients.base_client import BaseMCPClient
from a2c_smcp_cc.utils.logger import logger


class SseMCPClient(BaseMCPClient):
    def __init__(self, params: SseServerParameters, state_change_callback: Callable[[str, str], None] = None) -> None:
        assert isinstance(params, SseServerParameters), "params must be an instance of SseServerParameters"
        super().__init__(params, state_change_callback)

    async def abefore_connect(self, event: EventData) -> None:
        """
        尝试以 self.params 为参数启动 MCP Server

        Args:
            event (EventData): Transitions事件
        """
        logger.debug(f"Before connection actions with event: {event}\n\nserver params: {self.params}")
        aread_stream, awrite_stream = await self.aexit_stack.enter_async_context(sse_client(**self.params.model_dump(mode="python")))
        client_session = await self.aexit_stack.enter_async_context(ClientSession(aread_stream, awrite_stream))
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
