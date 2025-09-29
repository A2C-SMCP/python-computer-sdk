"""
* 文件名: test_smcp_namespace
* 作者: JQQ
* 创建日期: 2025/9/29
* 最后修改日期: 2025/9/29
* 版权: 2023 JQQ. All rights reserved.
* 依赖: pytest, socketio
* 描述: SMCP Namespace测试用例 / SMCP Namespace test cases
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from a2c_smcp.server import (
    AuthenticationProvider,
    DefaultAuthenticationProvider,
    SMCPNamespace,
)
from a2c_smcp.smcp import SMCP_NAMESPACE, EnterOfficeReq, LeaveOfficeReq


class MockAuthProvider(AuthenticationProvider):
    """Mock认证提供者用于测试 / Mock authentication provider for testing"""

    async def get_agent_id(self, sio: AsyncMock, environ: dict) -> str:
        """Mock获取agent_id逻辑 / Mock agent_id retrieval logic"""
        return "test_agent"

    async def authenticate(self, sio: AsyncMock, agent_id: str, auth: dict | None, headers: list) -> bool:
        """简单的Mock认证逻辑 / Simple mock authentication logic"""
        # 从headers中提取API密钥进行认证
        # Extract API key from headers for authentication
        for header in headers:
            if isinstance(header, (list, tuple)) and len(header) >= 2:
                header_name = header[0].decode("utf-8").lower() if isinstance(header[0], bytes) else str(header[0]).lower()
                header_value = header[1].decode("utf-8") if isinstance(header[1], bytes) else str(header[1])

                if header_name == "x-api-key" and header_value == "valid_key":
                    return True
        return False

    async def has_admin_permission(self, sio: AsyncMock, agent_id: str, secret: str) -> bool:
        """Mock管理员权限检查 / Mock admin permission check"""
        return secret == "admin_secret"


@pytest.fixture
def mock_auth_provider():
    """创建Mock认证提供者 / Create mock authentication provider"""
    return MockAuthProvider()


@pytest.fixture
def smcp_namespace(mock_auth_provider):
    """创建SMCP命名空间实例 / Create SMCP namespace instance"""
    return SMCPNamespace(mock_auth_provider)


@pytest.fixture
def mock_server():
    """创建Mock服务器 / Create mock server"""
    server = AsyncMock()
    server.app = MagicMock()
    server.app.state = MagicMock()
    server.app.state.agent_id = "test_agent"
    server.manager = AsyncMock()
    return server


class TestSMCPNamespace:
    """SMCP命名空间测试类 / SMCP namespace test class"""

    @pytest.mark.asyncio
    async def test_namespace_initialization(self, smcp_namespace):
        """测试命名空间初始化 / Test namespace initialization"""
        assert smcp_namespace.namespace == SMCP_NAMESPACE
        assert isinstance(smcp_namespace.auth_provider, MockAuthProvider)

    @pytest.mark.asyncio
    async def test_successful_connection(self, smcp_namespace, mock_server):
        """测试成功连接 / Test successful connection"""
        smcp_namespace.server = mock_server

        # Mock环境变量和认证数据
        # Mock environment variables and auth data
        environ = {
            "asgi": {
                "scope": {
                    "headers": [
                        (b"x-api-key", b"valid_key"),
                    ],
                },
            },
        }

        # 测试连接
        # Test connection
        result = await smcp_namespace.on_connect("test_sid", environ, None)
        assert result is True

    @pytest.mark.asyncio
    async def test_failed_authentication(self, smcp_namespace, mock_server):
        """测试认证失败 / Test authentication failure"""
        smcp_namespace.server = mock_server

        # Mock环境变量和无效认证数据
        # Mock environment variables and invalid auth data
        environ = {
            "asgi": {
                "scope": {
                    "headers": [
                        (b"x-api-key", b"invalid_key"),
                    ],
                },
            },
        }

        # 测试连接应该失败
        # Test connection should fail
        with pytest.raises(ConnectionRefusedError):
            await smcp_namespace.on_connect("test_sid", environ, None)

    @pytest.mark.asyncio
    async def test_join_office_success(self, smcp_namespace):
        """测试成功加入房间 / Test successful office join"""
        # Mock会话数据
        # Mock session data
        session = {}
        smcp_namespace.get_session = AsyncMock(return_value=session)
        smcp_namespace.save_session = AsyncMock()
        smcp_namespace.enter_room = AsyncMock()

        # 测试数据
        # Test data
        data = EnterOfficeReq(**{
            "role": "computer",
            "name": "test_computer",
            "office_id": "office_123",
        })

        # 执行测试
        # Execute test
        success, error = await smcp_namespace.on_server_join_office("test_sid", data)

        assert success is True
        assert error is None
        assert session["role"] == "computer"
        assert session["name"] == "test_computer"

    @pytest.mark.asyncio
    async def test_join_office_role_mismatch(self, smcp_namespace):
        """测试角色不匹配的情况 / Test role mismatch scenario"""
        # Mock会话数据，已有不同角色
        # Mock session data with different existing role
        session = {"role": "agent"}
        smcp_namespace.get_session = AsyncMock(return_value=session)
        smcp_namespace.save_session = AsyncMock()

        # 测试数据
        # Test data
        data = EnterOfficeReq(**{
            "role": "computer",
            "name": "test_computer",
            "office_id": "office_123",
        })

        # 执行测试
        # Execute test
        success, error = await smcp_namespace.on_server_join_office("test_sid", data)

        assert success is False
        assert "Role mismatch" in error

    @pytest.mark.asyncio
    async def test_leave_office(self, smcp_namespace):
        """测试离开房间 / Test leaving office"""
        smcp_namespace.leave_room = AsyncMock()

        # 测试数据
        # Test data
        data = LeaveOfficeReq(**{"office_id": "office_123"})

        # 执行测试
        # Execute test
        success, error = await smcp_namespace.on_server_leave_office("test_sid", data)

        assert success is True
        assert error is None
        smcp_namespace.leave_room.assert_called_once_with("test_sid", "office_123")


class TestDefaultAuthenticationProvider:
    """默认认证提供者测试类 / Default authentication provider test class"""

    def test_initialization(self):
        """测试初始化 / Test initialization"""
        provider = DefaultAuthenticationProvider("admin_secret", "custom-api-key")
        assert provider.admin_secret == "admin_secret"
        assert provider.api_key_name == "custom-api-key"

    @pytest.mark.asyncio
    async def test_admin_authentication(self):
        """测试管理员认证 / Test admin authentication"""
        provider = DefaultAuthenticationProvider("admin_secret")
        mock_sio = AsyncMock()

        headers = [(b"x-api-key", b"admin_secret")]
        result = await provider.authenticate(mock_sio, "agent_123", None, headers)
        assert result is True

    @pytest.mark.asyncio
    async def test_failed_authentication(self):
        """测试认证失败 / Test authentication failure"""
        provider = DefaultAuthenticationProvider("admin_secret")
        mock_sio = AsyncMock()

        headers = [(b"x-api-key", b"wrong_secret")]
        result = await provider.authenticate(mock_sio, "agent_123", None, headers)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_api_key(self):
        """测试无API密钥的情况 / Test no API key scenario"""
        provider = DefaultAuthenticationProvider("admin_secret")
        mock_sio = AsyncMock()

        headers = []  # 空的headers列表
        result = await provider.authenticate(mock_sio, "agent_123", None, headers)
        assert result is False
