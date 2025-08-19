# -*- coding: utf-8 -*-
# filename: sse_client.py
# @Time    : 2025/8/19 10:55
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
from collections.abc import Callable

from mcp.client.session_group import SseServerParameters

from a2c_smcp_cc.mcp_clients.base_client import BaseMCPClient


class SseMCPClient(BaseMCPClient):
    def __init__(self, params: SseServerParameters, state_change_callback: Callable[[str, str], None] = None) -> None:
        super().__init__(params, state_change_callback)
