"""
* 文件名: auth
* 作者: JQQ
* 创建日期: 2025/9/29
* 最后修改日期: 2025/9/29
* 版权: 2023 JQQ. All rights reserved.
* 依赖: None
* 描述: 认证接口抽象定义 / Authentication interface abstract definition
"""

from abc import ABC, abstractmethod

from socketio import AsyncServer


class AuthenticationProvider(ABC):
    """
    认证提供者抽象基类，用于处理Socket.IO连接的认证逻辑
    Abstract base class for authentication providers, handles Socket.IO connection authentication logic
    """

    @abstractmethod
    async def get_agent_id(self, sio: AsyncServer, environ: dict) -> str:
        """
        获取agent_id，由用户实现具体逻辑
        Get agent_id, implemented by user with specific logic

        Args:
            sio (AsyncServer): Socket.IO服务器实例 / Socket.IO server instance
            environ (dict): 请求环境变量 / Request environment variables

        Returns:
            str: agent_id
        """
        pass

    @abstractmethod
    async def authenticate(self, sio: AsyncServer, agent_id: str, auth: dict | None, headers: list) -> bool:
        """
        认证连接请求
        Authenticate connection request

        Args:
            sio (AsyncServer): Socket.IO服务器实例 / Socket.IO server instance
            agent_id (str): 代理ID / Agent ID
            auth (dict | None): 原始认证数据 / Raw authentication data
            headers (list): 原始请求头列表 / Raw request headers list

        Returns:
            bool: 认证是否成功 / Whether authentication succeeded
        """
        pass

    @abstractmethod
    async def has_admin_permission(self, sio: AsyncServer, agent_id: str, secret: str) -> bool:
        """
        检查是否具有管理员权限
        Check if has admin permission

        Args:
            sio (AsyncServer): Socket.IO服务器实例 / Socket.IO server instance
            agent_id (str): 代理ID / Agent ID
            secret (str): 密钥 / Secret

        Returns:
            bool: 是否具有管理员权限 / Whether has admin permission
        """
        pass


class DefaultAuthenticationProvider(AuthenticationProvider):
    """
    默认认证提供者，提供基础的认证逻辑实现
    Default authentication provider, provides basic authentication logic implementation
    """

    def __init__(self, admin_secret: str | None = None, api_key_name: str = "x-api-key") -> None:
        """
        初始化默认认证提供者
        Initialize default authentication provider

        Args:
            admin_secret (str | None): 管理员密钥 / Admin secret
            api_key_name (str): API密钥字段名 / API key field name
        """
        self.admin_secret = admin_secret
        self.api_key_name = api_key_name

    async def get_agent_id(self, sio: AsyncServer, environ: dict) -> str:
        """
        默认获取agent_id逻辑：从FastAPI应用状态中获取
        Default agent_id retrieval logic: get from FastAPI application state
        """
        if hasattr(sio, 'app') and hasattr(sio.app, 'state') and hasattr(sio.app.state, 'agent_id'):
            return sio.app.state.agent_id
        # 如果无法从应用状态获取，返回默认值
        # If cannot get from app state, return default value
        return "default_agent"

    async def authenticate(self, sio: AsyncServer, agent_id: str, auth: dict | None, headers: list) -> bool:
        """
        默认认证逻辑：从headers中提取API密钥进行认证
        Default authentication logic: extract API key from headers for authentication
        """
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

        # 检查管理员权限
        # Check admin permission
        if await self.has_admin_permission(sio, agent_id, api_key):
            return True

        # 这里可以添加其他认证逻辑，如数据库验证等
        # Additional authentication logic can be added here, such as database validation
        return False

    async def has_admin_permission(self, sio: AsyncServer, agent_id: str, secret: str) -> bool:
        """
        默认管理员权限检查：与配置的管理员密钥比较
        Default admin permission check: compare with configured admin secret
        """
        return self.admin_secret is not None and secret == self.admin_secret
