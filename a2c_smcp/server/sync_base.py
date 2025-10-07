"""
* 文件名: sync_base
* 作者: JQQ
* 创建日期: 2025/9/29
* 最后修改日期: 2025/9/29
* 版权: 2023 JQQ. All rights reserved.
* 依赖: socketio, loguru
* 描述: 同步版本基础Namespace抽象类 / Synchronous Base Namespace abstract class
"""

from typing import Any

from socketio import Namespace

from a2c_smcp.server.sync_auth import SyncAuthenticationProvider
from a2c_smcp.server.types import SID
from a2c_smcp.utils.logger import logger


class SyncBaseNamespace(Namespace):
    """
    同步基础Namespace抽象类，提供通用的连接管理和认证功能
    Synchronous Base Namespace abstract class, provides common connection management and authentication
    """

    def __init__(self, namespace: str, auth_provider: SyncAuthenticationProvider) -> None:
        """
        初始化基础Namespace
        Initialize base namespace
        """
        super().__init__(namespace=namespace)
        self.auth_provider = auth_provider

    def on_connect(self, sid: SID, environ: dict, auth: dict | None = None) -> bool:
        """
        客户端连接事件处理，包含认证逻辑（同步）
        Client connection event handler with authentication (sync)
        """
        try:
            logger.info(f"SocketIO Client {sid} connecting to {self.namespace}...")

            # 提取原始请求头
            # Extract raw request headers
            headers = self._extract_headers(environ)

            # 认证逻辑，直接传递原始数据给用户
            # Authentication logic, pass raw data directly to user
            is_authenticated = self.auth_provider.authenticate(self.server, environ, auth, headers)  # type: ignore[arg-type]
            if not is_authenticated:
                raise ConnectionRefusedError("Authentication failed")

            logger.info(f"SocketIO Client {sid} connected successfully to {self.namespace}")
            return True
        except Exception as e:
            logger.error(f"Connection error for {sid}: {e}")
            raise ConnectionRefusedError("Invalid connection request") from e

    def on_disconnect(self, sid: SID) -> None:
        """
        客户端断开连接事件处理（同步）
        Client disconnect event handler (sync)
        """
        logger.info(f"SocketIO Client {sid} disconnecting from {self.namespace}...")
        rooms = self.rooms(sid)
        for room in rooms:
            if room == sid:
                continue
            self.leave_room(sid, room)
        logger.info(f"SocketIO Client {sid} disconnected from {self.namespace}")

    def trigger_event(self, event: str, *args: Any) -> Any:  # type: ignore[override]
        """
        触发事件，重写触发逻辑，将冒号转换为下划线（同步）
        Trigger event, override logic to replace ':' with '_' (sync)
        """
        return super().trigger_event(event.replace(":", "_"), *args)

    @staticmethod
    def _extract_headers(environ: dict) -> list:
        """
        从请求环境中提取原始请求头列表
        Extract raw request headers list from request environment
        """
        headers = environ.get("asgi", {}).get("scope", {}).get("headers", [])
        if not headers:
            headers = environ.get("HTTP_HEADERS", [])
        return headers
