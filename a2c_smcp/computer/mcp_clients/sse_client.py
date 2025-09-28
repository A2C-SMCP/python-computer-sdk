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

from a2c_smcp.computer.mcp_clients.base_client import BaseMCPClient


class SseMCPClient(BaseMCPClient):
    def __init__(self, params: SseServerParameters, state_change_callback: Callable[[str, str], None] = None) -> None:
        assert isinstance(params, SseServerParameters), "params must be an instance of SseServerParameters"
        super().__init__(params, state_change_callback)

    async def _create_async_session(self) -> ClientSession:
        """
        创建异步会话

        Returns:
            ClientSession: 异步会话
        """
        aread_stream, awrite_stream = await self._aexit_stack.enter_async_context(sse_client(**self.params.model_dump(mode="python")))
        client_session = await self._aexit_stack.enter_async_context(ClientSession(aread_stream, awrite_stream))
        return client_session
