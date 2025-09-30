"""
* 文件名: client
* 作者: JQQ
* 创建日期: 2025/9/30
* 最后修改日期: 2025/9/30
* 版权: 2023 JQQ. All rights reserved.
* 依赖: socketio, mcp, asyncio
* 描述: 异步Agent客户端实现 / Asynchronous Agent client implementation
"""

from typing import Any

from mcp.types import CallToolResult, TextContent
from socketio import AsyncClient  # type: ignore[import-untyped]

from a2c_smcp.agent.auth import AgentAuthProvider
from a2c_smcp.agent.base import BaseAgentClient
from a2c_smcp.agent.types import AsyncAgentEventHandler
from a2c_smcp.smcp import (
    CANCEL_TOOL_CALL_EVENT,
    ENTER_OFFICE_NOTIFICATION,
    GET_TOOLS_EVENT,
    LEAVE_OFFICE_NOTIFICATION,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_CONFIG_NOTIFICATION,
    AgentCallData,
    EnterOfficeNotification,
    GetToolsRet,
    LeaveOfficeNotification,
    UpdateMCPConfigNotification,
)
from a2c_smcp.utils.logger import logger


class AsyncSMCPAgentClient(AsyncClient, BaseAgentClient):
    """
    SMCP协议的异步Agent客户端实现
    Asynchronous SMCP protocol Agent client implementation
    """

    def __init__(
        self,
        auth_provider: AgentAuthProvider,
        event_handler: AsyncAgentEventHandler | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """
        初始化异步SMCP Agent客户端
        Initialize asynchronous SMCP Agent client

        Args:
            auth_provider (AgentAuthProvider): 认证提供者 / Authentication provider
            event_handler (AsyncAgentEventHandler | None): 异步事件处理器 / Async event handler
            *args: AsyncClient构造参数 / AsyncClient constructor arguments
            **kwargs: AsyncClient构造参数 / AsyncClient constructor arguments
        """
        # 分别初始化 AsyncClient 与 BaseAgentClient
        # Initialize AsyncClient and BaseAgentClient respectively
        AsyncClient.__init__(self, *args, **kwargs)
        BaseAgentClient.__init__(self, auth_provider=auth_provider, event_handler=None)

        # 使用异步事件处理器（与Base中的同步处理器隔离）
        # Use async event handler (isolated from Base's sync handler)
        self.event_handler = event_handler

        # 注册事件处理器
        # Register event handlers
        self.register_event_handlers()

    async def emit(self, event: str, data: Any = None, namespace: str | None = None, callback: Any = None) -> None:
        """
        异步发送事件，包含事件验证逻辑
        Async send event with event validation logic

        Args:
            event (str): 事件名称 / Event name
            data (Any): 事件数据 / Event data
            namespace (Optional[str]): 命名空间 / Namespace
            callback (Any): 回调函数 / Callback function
        """
        # 验证事件合法性
        # Validate event legality
        self.validate_emit_event(event)

        # 调用父类方法
        # Call parent class method
        await super().emit(event, data, namespace, callback)

    async def call(self, event: str, data: Any = None, namespace: str | None = None, timeout: int = 60) -> Any:
        """
        异步调用事件并等待响应
        Async call event and wait for response

        Args:
            event (str): 事件名称 / Event name
            data (Any): 事件数据 / Event data
            namespace (Optional[str]): 命名空间 / Namespace
            timeout (int): 超时时间 / Timeout duration

        Returns:
            Any: 响应数据 / Response data
        """
        # 验证事件合法性
        # Validate event legality
        self.validate_emit_event(event)

        # 调用父类方法
        # Call parent class method
        return await super().call(event, data, namespace, timeout)

    # 事件合法性校验复用 BaseAgentClient.validate_emit_event
    # Reuse BaseAgentClient.validate_emit_event for event validation

    async def connect_to_server(
        self,
        url: str,
        namespace: str = SMCP_NAMESPACE,
        **kwargs: Any,
    ) -> None:
        """
        异步连接到SMCP服务器
        Async connect to SMCP server

        Args:
            url (str): 服务器URL / Server URL
            namespace (str): 命名空间 / Namespace
            **kwargs: 连接参数 / Connection parameters
        """
        # 获取认证信息
        # Get authentication info
        auth_data = self.auth_provider.get_connection_auth()
        headers = self.auth_provider.get_connection_headers()

        # 合并连接参数
        # Merge connection parameters
        connect_kwargs = {
            "auth": auth_data,
            "headers": headers,
            "namespaces": [namespace],
            **kwargs,
        }

        logger.info(f"Connecting to SMCP server at {url}")
        await self.connect(url, **connect_kwargs)
        logger.info("Connected to SMCP server successfully")

    async def emit_tool_call(self, computer: str, tool_name: str, params: dict, timeout: int) -> CallToolResult:
        """
        异步发起SMCP工具调用
        Async initiate SMCP tool call

        Args:
            computer (str): 远程计算机名称 / Remote computer name
            tool_name (str): 工具名称 / Tool name
            params (dict): 工具调用参数 / Tool call parameters
            timeout (int): 超时时间 / Timeout duration

        Returns:
            CallToolResult: MCP协议工具调用结果 / MCP protocol tool call result
        """
        req = self.create_tool_call_request(computer, tool_name, params, timeout)

        try:
            logger.debug(f"Calling tool {tool_name} on computer {computer}")
            res = await self.call(TOOL_CALL_EVENT, req, timeout=timeout, namespace=SMCP_NAMESPACE)
            return CallToolResult.model_validate(res)

        except TimeoutError:
            # 发送取消请求
            # Send cancel request
            agent_config = self.auth_provider.get_agent_config()
            cancel_data = AgentCallData(robot_id=agent_config["agent_id"], req_id=req["req_id"])
            await self.emit(CANCEL_TOOL_CALL_EVENT, cancel_data, namespace=SMCP_NAMESPACE)
            return self.handle_tool_call_timeout(req["req_id"])

        except Exception as e:
            logger.error(f"Tool call failed: {e}")
            return CallToolResult(
                content=[TextContent(text=f"工具调用失败 / Tool call failed: {str(e)}", type="text")],
                isError=True,
            )

    async def get_tools_from_computer(self, computer: str, timeout: int = 20) -> GetToolsRet:
        """
        异步从指定计算机获取工具列表
        Async get tools list from specified computer

        Args:
            computer (str): 计算机ID / Computer ID
            timeout (int): 超时时间 / Timeout duration

        Returns:
            GetToolsRet: 工具列表响应 / Tools list response
        """
        req = self.create_get_tools_request(computer)

        try:
            logger.debug(f"Getting tools from computer {computer}")
            response = await self.call(GET_TOOLS_EVENT, req, namespace=SMCP_NAMESPACE, timeout=timeout)

            # 验证响应
            # Validate response
            if response.get("req_id") != req["req_id"]:
                raise ValueError("Invalid response with mismatched req_id")

            return GetToolsRet(tools=response.get("tools", []), req_id=response["req_id"])

        except Exception as e:
            logger.error(f"Failed to get tools from computer {computer}: {e}")
            raise

    def register_event_handlers(self) -> None:
        """
        注册SMCP协议事件处理器
        Register SMCP protocol event handlers
        """
        self.on(ENTER_OFFICE_NOTIFICATION, self._on_computer_enter_office, namespace=SMCP_NAMESPACE)
        self.on(LEAVE_OFFICE_NOTIFICATION, self._on_computer_leave_office, namespace=SMCP_NAMESPACE)
        self.on(UPDATE_CONFIG_NOTIFICATION, self._on_computer_update_config, namespace=SMCP_NAMESPACE)

    async def _on_computer_enter_office(self, data: EnterOfficeNotification) -> None:
        """
        处理Computer加入办公室事件的内部方法
        Internal method to handle Computer enter office event
        """
        try:
            computer = self.validate_office_data(data)
            logger.info(f"Computer {computer} entered office {data['office_id']}")

            # 调用事件处理器
            # Call event handler
            if self.event_handler:
                await self.event_handler.on_computer_enter_office(data)

            # 自动获取工具列表
            # Automatically get tools list
            tools_response = await self.get_tools_from_computer(computer)
            await self.process_tools_response(tools_response, computer)

        except Exception as e:
            logger.error(f"Error in _on_computer_enter_office: {e}")

    async def _on_computer_leave_office(self, data: LeaveOfficeNotification) -> None:
        """
        处理Computer离开办公室事件的内部方法
        Internal method to handle Computer leave office event
        """
        try:
            computer = self.validate_office_data(data)
            logger.info(f"Computer {computer} left office {data['office_id']}")

            # 调用事件处理器
            # Call event handler
            if self.event_handler:
                await self.event_handler.on_computer_leave_office(data)

        except Exception as e:
            logger.error(f"Error in _on_computer_leave_office: {e}")

    async def _on_computer_update_config(self, data: UpdateMCPConfigNotification) -> None:
        """
        处理Computer更新配置事件的内部方法
        Internal method to handle Computer update config event
        """
        try:
            computer = data["computer"]
            logger.info(f"Computer {computer} updated config")

            # 调用事件处理器
            # Call event handler
            if self.event_handler:
                await self.event_handler.on_computer_update_config(data)

            # 重新获取工具列表
            # Re-get tools list
            tools_response = await self.get_tools_from_computer(computer)
            await self.process_tools_response(tools_response, computer)

        except Exception as e:
            logger.error(f"Error in _on_computer_update_config: {e}")

    async def process_tools_response(self, response: GetToolsRet, computer: str) -> None:
        """
        异步处理工具响应
        Async process tools response

        Args:
            response: 工具响应数据 / Tools response data
            computer: 计算机ID / Computer ID
        """
        try:
            if tools := response.get("tools"):
                logger.info(f"Received {len(tools)} tools from computer {computer}")

                # 调用事件处理器
                # Call event handler
                if self.event_handler:
                    await self.event_handler.on_tools_received(computer, tools)

        except Exception as e:
            logger.error(f"Error processing tools response: {e}")
