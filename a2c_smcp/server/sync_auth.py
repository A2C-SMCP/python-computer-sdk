"""
* 文件名: sync_auth
* 作者: JQQ
* 创建日期: 2025/9/29
* 最后修改日期: 2025/9/29
* 版权: 2023 JQQ. All rights reserved.
* 依赖: None
* 描述: 同步版本的认证接口与默认实现 / Synchronous authentication interfaces and default implementation
"""

from abc import ABC, abstractmethod

from socketio import Server


class SyncAuthenticationProvider(ABC):
    """
    同步认证提供者抽象基类，用于处理Socket.IO连接的认证逻辑
    Synchronous base class for authentication providers for Socket.IO authentication
    """

    @abstractmethod
    def get_agent_id(self, sio: Server, environ: dict) -> str:
        """
        获取agent_id，由用户实现具体逻辑
        Get agent_id, implemented by user with specific logic
        """
        raise NotImplementedError

    @abstractmethod
    def authenticate(self, sio: Server, agent_id: str, auth: dict | None, headers: list) -> bool:
        """
        认证连接请求
        Authenticate connection request
        """
        raise NotImplementedError

    @abstractmethod
    def has_admin_permission(self, sio: Server, agent_id: str, secret: str) -> bool:
        """
        检查是否具有管理员权限
        Check if has admin permission
        """
        raise NotImplementedError


class DefaultSyncAuthenticationProvider(SyncAuthenticationProvider):
    """
    同步版本默认认证提供者
    Default sync authentication provider
    """

    def __init__(self, admin_secret: str | None = None, api_key_name: str = "x-api-key") -> None:
        self.admin_secret = admin_secret
        self.api_key_name = api_key_name

    def get_agent_id(self, sio: Server, environ: dict) -> str:
        # 默认获取agent_id逻辑：从FastAPI应用状态中获取
        # Default agent_id retrieval logic: get from FastAPI application state
        if hasattr(sio, "app") and hasattr(sio.app, "state") and hasattr(sio.app.state, "agent_id"):
            return sio.app.state.agent_id
        return "default_agent"

    def authenticate(self, sio: Server, agent_id: str, auth: dict | None, headers: list) -> bool:
        # 从headers中提取API密钥
        # Extract API key from headers
        api_key = None
        for header in headers:
            if isinstance(header, (list, tuple)) and len(header) >= 2:
                header_name = header[0].decode("utf-8").lower() if isinstance(header[0], bytes) else str(header[0]).lower()
                header_value = header[1].decode("utf-8") if isinstance(header[1], bytes) else str(header[1])
                if header_name == self.api_key_name.lower():
                    api_key = header_value
                    break
        if not api_key:
            return False

        # 管理员权限
        # Admin permission
        if self.has_admin_permission(sio, agent_id, api_key):
            return True

        # 可在此扩展其他认证逻辑
        # Extend with other authentication logic here
        return False

    def has_admin_permission(self, sio: Server, agent_id: str, secret: str) -> bool:
        # 默认管理员权限检查：与配置的管理员密钥比较
        # Default admin permission check: compare with configured admin secret
        return self.admin_secret is not None and secret == self.admin_secret
