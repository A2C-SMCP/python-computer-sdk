"""
* 文件名: base
* 作者: JQQ
* 创建日期: 2025/9/29
* 最后修改日期: 2025/9/29
* 版权: 2023 JQQ. All rights reserved.
* 依赖: socketio, loguru
* 描述: 基础Namespace抽象类 / Base Namespace abstract class
"""

from typing import Any

from socketio import AsyncNamespace

from a2c_smcp.server.auth import AuthenticationProvider
from a2c_smcp.server.types import SID
from a2c_smcp.utils.logger import logger


class BaseNamespace(AsyncNamespace):
    """
    基础Namespace抽象类，提供通用的连接管理和认证功能
    Base Namespace abstract class, provides common connection management and authentication features
    """

    def __init__(self, namespace: str, auth_provider: AuthenticationProvider) -> None:
        """
        初始化基础Namespace
        Initialize base namespace

        Args:
            namespace (str): 命名空间路径 / Namespace path
            auth_provider (AuthenticationProvider): 认证提供者 / Authentication provider
        """
        super().__init__(namespace=namespace)
        self.auth_provider = auth_provider

    async def on_connect(self, sid: SID, environ: dict, auth: dict | None = None) -> bool:
        """
        客户端连接事件处理，包含认证逻辑
        Client connection event handler, includes authentication logic

        Args:
            sid (SID): 客户端连接的ID / Client connection ID
            environ (dict): 请求的环境变量 / Request environment variables
            auth (dict | None): 认证信息 / Authentication information

        Returns:
            bool: 是否允许连接 / Whether to allow connection
        """
        try:
            logger.info(f"SocketIO Client {sid} connecting to {self.namespace}...")

            # 提取原始请求头
            # Extract raw request headers
            headers = self._extract_headers(environ)

            # 认证逻辑，直接传递原始数据给用户
            # Authentication logic, pass raw data directly to user
            is_authenticated = await self.auth_provider.authenticate(self.server, environ, auth, headers)
            if not is_authenticated:
                raise ConnectionRefusedError("Authentication failed")

            logger.info(f"SocketIO Client {sid} connected successfully to {self.namespace}")
            return True

        except Exception as e:
            logger.error(f"Connection error for {sid}: {e}")
            raise ConnectionRefusedError("Invalid connection request") from e

    async def on_disconnect(self, sid: SID) -> None:
        """
        客户端断开连接事件处理
        Client disconnect event handler

        Args:
            sid (SID): 客户端连接的ID / Client connection ID
        """
        logger.info(f"SocketIO Client {sid} disconnecting from {self.namespace}...")

        # 清理房间连接
        # Clean up room connections
        rooms = self.rooms(sid)
        for room in rooms:
            if room == sid:
                # Socket.IO有自己的机制，每个客户端会进入一个同名房间
                # Socket.IO has its own mechanism, each client enters a room with the same name
                continue
            await self.leave_room(sid, room)

        logger.info(f"SocketIO Client {sid} disconnected from {self.namespace}")

    async def trigger_event(self, event: str, *args: Any) -> Any:
        """
        触发事件，重写触发逻辑，将冒号转换为下划线
        Trigger event, override trigger logic, convert colons to underscores

        Args:
            event (str): 事件名称 / Event name
            *args: 事件参数 / Event arguments

        Returns:
            Any: 事件处理结果 / Event handling result
        """
        return await super().trigger_event(event.replace(":", "_"), *args)

    @staticmethod
    def _extract_headers(environ: dict) -> list:
        """
        从请求环境中提取原始请求头列表
        Extract raw request headers list from request environment

        Args:
            environ (dict): 请求环境变量 / Request environment variables

        Returns:
            list: 原始请求头列表 / Raw request headers list
        """
        # 尝试从不同的环境变量结构中获取headers
        # Try to get headers from different environment variable structures
        headers = environ.get("asgi", {}).get("scope", {}).get("headers", [])
        if not headers:
            headers = environ.get("HTTP_HEADERS", [])

        return headers
