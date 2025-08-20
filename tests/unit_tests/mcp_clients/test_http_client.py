# -*- coding: utf-8 -*-
# filename: test_http_client.py
# @Time    : 2025/8/20
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp.client.session_group import StreamableHttpParameters
from polyfactory.factories.pydantic_factory import ModelFactory

from a2c_smcp_cc.mcp_clients.http_client import HttpMCPClient


@pytest.mark.asyncio
async def test_abefore_connect_and_on_enter_connected():
    """
    测试 abefore_connect 与 on_enter_connected 的协作，确保 EventData.kwargs 能正确传递 client_session。
    Test abefore_connect and on_enter_connected, ensuring EventData.kwargs passes client_session correctly.
    """
    # 构造 mock 对象 Construct mock objects
    mock_aread_stream = MagicMock(name="aread_stream")
    mock_awrite_stream = MagicMock(name="awrite_stream")
    mock_session = AsyncMock(name="ClientSession")
    mock_initialize = AsyncMock()
    mock_session.initialize = mock_initialize

    mock_params = ModelFactory.create_factory(model=StreamableHttpParameters).build()

    # Patch streamablehttp_client 和 ClientSession
    with (
        patch(
            "a2c_smcp_cc.mcp_clients.http_client.streamablehttp_client",
            new=AsyncMock(return_value=(mock_aread_stream, mock_awrite_stream, None)),
        ),
        patch("a2c_smcp_cc.mcp_clients.http_client.ClientSession", new=AsyncMock(return_value=mock_session)) as mock_cs,
    ):
        # 构造 client 和 event
        client = HttpMCPClient(params=mock_params)
        assert client._async_session is None
        client._aexit_stack = AsyncMock()  # 避免真实上下文
        client._aexit_stack.enter_async_context = AsyncMock(side_effect=[(mock_aread_stream, mock_awrite_stream, None), mock_session])
        # 调用 abefore_connect
        await client.aconnect()
        # 断言 ClientSession 被正确初始化
        mock_cs.assert_called_once_with(mock_aread_stream, mock_awrite_stream)
        # 断言 initialize 被调用
        mock_initialize.assert_awaited()
        # 断言 client._async_session 设置正确
        assert client._async_session is mock_session
        assert client._async_session is not None
