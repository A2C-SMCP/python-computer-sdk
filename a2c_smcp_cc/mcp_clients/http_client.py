# -*- coding: utf-8 -*-
# filename: http_client.py
# @Time    : 2025/8/19 10:55
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from collections.abc import Callable

from mcp import ClientSession
from mcp.client.session_group import StreamableHttpParameters
from mcp.client.streamable_http import streamablehttp_client
from transitions.core import EventData

from a2c_smcp_cc.mcp_clients.base_client import BaseMCPClient
from a2c_smcp_cc.utils.logger import logger


class HttpMCPClient(BaseMCPClient):
    def __init__(self, params: StreamableHttpParameters, state_change_callback: Callable[[str, str], None] = None) -> None:
        assert isinstance(params, StreamableHttpParameters), "params must be an instance of StreamableHttpParameters"
        super().__init__(params, state_change_callback)

    async def abefore_connect(self, event: EventData) -> None:
        """
        尝试以 self.params 为参数启动 MCP Server

        Args:
            event (EventData): Transitions事件
        """
        logger.debug(f"Before connection actions with event: {event}\n\nserver params: {self.params}")
        # 目前忽略了 GetSessionIdCallback。只有在手动管理Session才有必要，在封装内全部使用自动管理。
        # 需要注意 self.params.model_dump() 的 mode 参数使用默认python，不可以使用json，因为当前Params中有 timedelta，如果使用json会序列化
        # 为str，导致连接报错。
        aread_stream, awrite_stream, _ = await self.aexit_stack.enter_async_context(
            streamablehttp_client(**self.params.model_dump(mode="python"))
        )
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
