# -*- coding: utf-8 -*-
# filename: mock_uv_server.py
# @Time    : 2025/8/21 14:29
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm

import asyncio

# 3rd party imports
import uvicorn

# socketio imports
from socketio import ASGIApp

PORT = 8000

# deactivate monitoring task in python-socketio to avoid errores during shutdown
# sio.eio.start_service_task = False

"""
参考：
https://github.com/miguelgrinberg/python-socketio/issues/332?utm_source=chatgpt.com
"""


class UvicornTestServer(uvicorn.Server):
    """Uvicorn test server

    Usage:
        @pytest.fixture
        async def start_stop_server():
            server = UvicornTestServer()
            await server.up()
            yield
            await server.down()
    """

    def __init__(self, app: ASGIApp = None, host: str = "127.0.0.1", port: int = PORT):
        """Create a Uvicorn test server

        Args:
            app (ASGIApp, optional): the ASGIApp app. Defaults to main.asgi_app.
            host (str, optional): the host ip. Defaults to '127.0.0.1'.
            port (int, optional): the port. Defaults to PORT.
        """
        self._startup_done = asyncio.Event()
        super().__init__(config=uvicorn.Config(app, host=host, port=port))

    async def startup(self, sockets: list | None = None) -> None:
        """Override uvicorn startup"""
        await super().startup(sockets=sockets)
        self.config.setup_event_loop()
        self._startup_done.set()

    async def up(self) -> None:
        """Start up server asynchronously"""
        self._serve_task = asyncio.create_task(self.serve())
        await self._startup_done.wait()

    async def down(self) -> None:
        """Shut down server asynchronously"""
        self.should_exit = True
        await self._serve_task
