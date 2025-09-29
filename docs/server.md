# A2C-SMCP Server 模块文档

## 概述 / Overview

A2C-SMCP Server模块提供了SMCP协议的服务端实现，主要负责中央信令服务器功能，包括：

- 维护Computer/Agent元数据信息
- 信号传输转发消息  
- 将收到的消息转换为Notification广播

The A2C-SMCP Server module provides server-side implementation of the SMCP protocol, mainly responsible for central signaling server functions, including:

- Maintaining Computer/Agent metadata information
- Signal transmission and message forwarding
- Converting received messages into Notification broadcasts

## 核心组件 / Core Components

### 1. 认证系统 / Authentication System

#### AuthenticationProvider (抽象基类)

认证提供者抽象基类，定义了认证接口：

```python
from a2c_smcp.server import AuthenticationProvider
from socketio import AsyncServer

class CustomAuthProvider(AuthenticationProvider):
    async def get_agent_id(self, sio: AsyncServer, environ: dict) -> str:
        # 实现获取agent_id的逻辑
        # Implement agent_id retrieval logic
        pass
    
    async def authenticate(self, sio: AsyncServer, agent_id: str, auth: dict | None, headers: list) -> bool:
        # 实现自定义认证逻辑
        # Implement custom authentication logic
        pass
    
    async def has_admin_permission(self, sio: AsyncServer, agent_id: str, secret: str) -> bool:
        # 实现管理员权限检查
        # Implement admin permission check
        pass
```

#### DefaultAuthenticationProvider (默认实现)

提供基础的认证逻辑实现：

```python
from a2c_smcp.server import DefaultAuthenticationProvider

# 创建默认认证提供者
# Create default authentication provider
auth_provider = DefaultAuthenticationProvider(
    admin_secret="your_admin_secret",
    api_key_name="x-api-key"  # 可自定义API密钥字段名
)
```

**新的接口特性 / New Interface Features:**
- `get_agent_id()`: 由用户实现agent_id获取逻辑，可从FastAPI应用状态或其他源获取
- `authenticate()`: 接收Socket.IO实例、agent_id、原始auth数据和原始headers列表
- `has_admin_permission()`: 接收Socket.IO实例和agent_id参数

### 2. 命名空间系统 / Namespace System

#### BaseNamespace (基础抽象类)

提供通用的连接管理和认证功能的基础类。

#### SMCPNamespace (SMCP协议实现)

处理SMCP相关事件的Socket.IO命名空间：

```python
from a2c_smcp.server import SMCPNamespace, DefaultAuthenticationProvider

# 创建认证提供者
auth_provider = DefaultAuthenticationProvider("admin_secret")

# 创建SMCP命名空间
smcp_namespace = SMCPNamespace(auth_provider)
```

### 3. 类型定义 / Type Definitions

```python
from a2c_smcp.server import (
    OFFICE_ID,      # 房间ID类型别名
    SID,            # 会话ID类型别名
    BaseSession,    # 基础会话类型
    ComputerSession,# Computer会话类型
    AgentSession,   # Agent会话类型
    Session         # 联合会话类型
)
```

### 4. 工具函数 / Utility Functions

```python
from a2c_smcp.server import (
    aget_computers_in_office,      # 异步获取房间内Computer列表
    get_computers_in_office,       # 同步获取房间内Computer列表
    aget_all_sessions_in_office,   # 异步获取房间内所有会话
    get_all_sessions_in_office,    # 同步获取房间内所有会话
)
```

## 使用示例 / Usage Examples

### 基础使用 / Basic Usage

```python
import asyncio
from socketio import AsyncServer
from a2c_smcp.server import SMCPNamespace, DefaultAuthenticationProvider

async def setup_server():
    # 1. 创建认证提供者
    # Create authentication provider
    auth_provider = DefaultAuthenticationProvider(
        admin_secret="your_admin_secret",
        api_key_name="x-api-key"
    )
    
    # 2. 创建SMCP命名空间
    # Create SMCP namespace
    smcp_namespace = SMCPNamespace(auth_provider)
    
    # 3. 创建Socket.IO服务器并注册命名空间
    # Create Socket.IO server and register namespace
    sio = AsyncServer(cors_allowed_origins="*")
    sio.register_namespace(smcp_namespace)
    
    return sio

# 在FastAPI中使用 / Usage with FastAPI
from fastapi import FastAPI
import socketio

app = FastAPI()
sio = asyncio.run(setup_server())

# 挂载Socket.IO到FastAPI
# Mount Socket.IO to FastAPI
socket_app = socketio.ASGIApp(sio, app)
```

### 自定义认证 / Custom Authentication

```python
from a2c_smcp.server import AuthenticationProvider, SMCPNamespace
from socketio import AsyncServer

class DatabaseAuthProvider(AuthenticationProvider):
    def __init__(self, db_connection):
        self.db = db_connection
    
    async def get_agent_id(self, sio: AsyncServer, environ: dict) -> str:
        # 从请求中提取agent_id，例如从路径或查询参数
        # Extract agent_id from request, e.g., from path or query parameters
        if hasattr(sio, 'app') and hasattr(sio.app, 'state'):
            return getattr(sio.app.state, 'agent_id', 'default_agent')
        return 'default_agent'
    
    async def authenticate(self, sio: AsyncServer, agent_id: str, auth: dict | None, headers: list) -> bool:
        # 从headers中提取API密钥
        # Extract API key from headers
        api_key = None
        for header in headers:
            if isinstance(header, (list, tuple)) and len(header) >= 2:
                header_name = header[0].decode("utf-8").lower() if isinstance(header[0], bytes) else str(header[0]).lower()
                header_value = header[1].decode("utf-8") if isinstance(header[1], bytes) else str(header[1])
                
                if header_name == "x-api-key":
                    api_key = header_value
                    break
        
        if not api_key:
            return False
        
        # 从数据库验证API密钥
        # Validate API key from database
        user = await self.db.get_user_by_api_key(api_key)
        return user is not None and user.agent_id == agent_id
    
    async def has_admin_permission(self, sio: AsyncServer, agent_id: str, secret: str) -> bool:
        # 检查数据库中的管理员权限
        # Check admin permission in database
        return await self.db.check_admin_permission(agent_id, secret)

# 使用自定义认证
# Use custom authentication
auth_provider = DatabaseAuthProvider(db_connection)
smcp_namespace = SMCPNamespace(auth_provider)
```

### 获取房间信息 / Getting Room Information

```python
from a2c_smcp.server import aget_computers_in_office

async def get_office_status(office_id: str, sio: AsyncServer):
    # 获取房间内所有Computer
    # Get all Computers in the room
    computers = await aget_computers_in_office(office_id, sio)
    
    print(f"Office {office_id} has {len(computers)} computers:")
    for computer in computers:
        print(f"  - {computer['name']} (sid: {computer['sid']})")
```

## 支持的事件 / Supported Events

### 服务端事件 / Server Events

- `server:join_office` - Computer/Agent加入房间
- `server:leave_office` - Computer/Agent离开房间  
- `server:update_config` - 更新MCP配置
- `server:tool_call_cancel` - 取消工具调用

### 客户端事件 / Client Events

- `client:tool_call` - 工具调用
- `client:get_tools` - 获取工具列表

### 通知事件 / Notification Events

- `notify:enter_office` - 进入房间通知
- `notify:leave_office` - 离开房间通知
- `notify:update_config` - 配置更新通知
- `notify:tool_call_cancel` - 工具调用取消通知

## 会话管理 / Session Management

Server模块自动管理客户端会话，包括：

- 会话状态维护
- 房间成员管理
- 角色验证（Computer/Agent）
- 权限控制

The Server module automatically manages client sessions, including:

- Session state maintenance
- Room member management
- Role validation (Computer/Agent)
- Permission control

## 错误处理 / Error Handling

Server模块提供了完善的错误处理机制：

- 连接认证失败 → `ConnectionRefusedError`
- 角色冲突 → 返回错误信息
- 房间管理错误 → 自动恢复会话状态

The Server module provides comprehensive error handling:

- Connection authentication failure → `ConnectionRefusedError`
- Role conflicts → Return error information
- Room management errors → Automatic session state recovery

## 扩展性 / Extensibility

Server模块设计为高度可扩展：

1. **自定义认证** - 实现`AuthenticationProvider`接口，完全控制认证逻辑
2. **灵活agent_id获取** - 通过`get_agent_id()`方法自定义agent_id获取逻辑
3. **原始数据访问** - 直接访问原始auth数据和headers，无预处理
4. **Socket.IO实例访问** - 在认证过程中可访问Socket.IO服务器实例
5. **事件扩展** - 继承`SMCPNamespace`添加新事件
6. **中间件** - 在基础类中添加中间件逻辑

The Server module is designed to be highly extensible:

1. **Custom Authentication** - Implement `AuthenticationProvider` interface with full control
2. **Flexible agent_id Retrieval** - Customize agent_id retrieval logic via `get_agent_id()` method
3. **Raw Data Access** - Direct access to raw auth data and headers without preprocessing
4. **Socket.IO Instance Access** - Access Socket.IO server instance during authentication
5. **Event Extension** - Inherit `SMCPNamespace` to add new events
6. **Middleware** - Add middleware logic in base classes

## 测试 / Testing

运行Server模块测试：

```bash
# 运行所有Server测试
pytest tests/unit_tests/server/

# 运行特定测试文件
pytest tests/unit_tests/server/test_smcp_namespace.py

# 运行带覆盖率的测试
pytest tests/unit_tests/server/ --cov=a2c_smcp.server
```

## 注意事项 / Notes

1. **线程安全** - 所有方法都是异步的，确保线程安全
2. **内存管理** - 会话数据会自动清理，无需手动管理
3. **性能优化** - 大量连接时建议使用Redis作为会话存储
4. **日志记录** - 使用项目统一的logger进行日志记录
5. **接口变更** - 新版本中`robot_id`已更名为`agent_id`，认证接口已简化
6. **用户控制** - 用户现在对认证过程有更多控制权，包括agent_id获取和原始数据处理

1. **Thread Safety** - All methods are asynchronous, ensuring thread safety
2. **Memory Management** - Session data is automatically cleaned up, no manual management needed
3. **Performance Optimization** - For large numbers of connections, consider using Redis for session storage
4. **Logging** - Uses the project's unified logger for logging
5. **Interface Changes** - In the new version, `robot_id` has been renamed to `agent_id`, and authentication interface has been simplified
6. **User Control** - Users now have more control over the authentication process, including agent_id retrieval and raw data processing
