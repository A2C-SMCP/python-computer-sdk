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

from a2c_smcp.computer.mcp_clients.base_client import BaseMCPClient


class HttpMCPClient(BaseMCPClient):
    def __init__(self, params: StreamableHttpParameters, state_change_callback: Callable[[str, str], None] = None) -> None:
        assert isinstance(params, StreamableHttpParameters), "params must be an instance of StreamableHttpParameters"
        super().__init__(params, state_change_callback)

    async def _create_async_session(self) -> ClientSession:
        """
        创建异步会话

        Returns:
            ClientSession: 异步会话
        """
        # 目前忽略了 GetSessionIdCallback。只有在手动管理Session才有必要，在封装内全部使用自动管理。
        # 需要注意 self.params.model_dump() 的 mode 参数使用默认python，不可以使用json，因为当前Params中有 timedelta，如果使用json会序列化
        # 为str，导致连接报错。
        aread_stream, awrite_stream, _ = await self._aexit_stack.enter_async_context(
            streamablehttp_client(**self.params.model_dump(mode="python"))
        )
        client_session = await self._aexit_stack.enter_async_context(ClientSession(aread_stream, awrite_stream))
        return client_session
