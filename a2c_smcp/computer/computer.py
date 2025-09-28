# 文件名: main.py
# @Time    : 2025/8/17 16:52
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm

"""
计算机管理模块 Computer
==============================

该模块定义了 Computer 类，用于管理 MCP 服务器的生命周期、工具获取等功能。

This module defines the Computer class, which manages the lifecycle of MCP servers and provides tool retrieval functions.

类和方法均采用 Google 风格注释（中英文双语）。
All classes and methods use Google style docstrings (bilingual: Chinese and English).

依赖 Dependencies:
    - mcp
    - pydantic
    - a2c_smcp_cc.mcp_clients.manager
    - a2c_smcp_cc.mcp_clients.model
    - a2c_smcp_cc.socketio.smcp
    - a2c_smcp_cc.socketio.types
    - a2c_smcp_cc.utils.logger
"""

import json
from collections.abc import Callable
from typing import Any

from mcp import Tool
from mcp.types import CallToolResult, TextContent
from prompt_toolkit import PromptSession
from pydantic import TypeAdapter

from a2c_smcp.computer.base import BaseComputer
from a2c_smcp.computer.inputs.render import ConfigRender
from a2c_smcp.computer.inputs.resolver import InputNotFoundError, InputResolver
from a2c_smcp.computer.mcp_clients.manager import MCPServerManager
from a2c_smcp.computer.mcp_clients.model import MCPServerConfig, MCPServerInput
from a2c_smcp.computer.socketio.smcp import SMCPTool
from a2c_smcp.computer.socketio.types import AttributeValue
from a2c_smcp.computer.utils.logger import logger


class Computer(BaseComputer[PromptSession]):
    def __init__(
        self,
        inputs: set[MCPServerInput] | None = None,
        mcp_servers: set[MCPServerConfig] | None = None,
        auto_connect: bool = True,
        auto_reconnect: bool = True,
        confirm_callback: Callable[[str, str, str, dict], bool] | None = None,
        input_resolver: InputResolver | None = None,
    ) -> None:
        """
        初始化 Computer 实例
        Initialize Computer instance

        MCP Server使用set来管理配置项，注意配置项基类里有定义，如果配置name相同表示完全相同（重写了__hash__方法）

        The MCP Server configuration is in the form of a dictionary to help users reduce the possibility of duplicate
        configuration, and it is recommended to use the name of the MCP Server as the key to avoid duplicate
        configuration. Of course, if there is a special design that requires the name to be repeated, you can
        customize the dictionary value to avoid this limitation

        Args:
            inputs (set[MCPServerInput] | None): MCP服务器输入项配置集合（以 id 唯一、基于 set 去重）。MCP server input config set.
            mcp_servers (set[MCPServerConfig] | None): MCP服务器配置集合。MCP server config set.
            auto_connect (bool): 是否自动连接。Whether to auto connect.
            auto_reconnect (bool): 是否自动重连。Whether to auto reconnect.
            confirm_callback (Callable[[str, str, str, dict], bool] | None): 工具调用二次确认回调
        """
        self.mcp_manager: MCPServerManager | None = None
        self._inputs: set[MCPServerInput] = set(inputs or set())
        self._mcp_servers: set[MCPServerConfig] = set(mcp_servers or set())
        self._auto_connect = auto_connect
        self._auto_reconnect = auto_reconnect
        self._confirm_callback = confirm_callback
        # 中文: 按需解析器与渲染器（惰性解析 inputs，保持配置不可变）
        # English: Lazy input resolver and renderer (on-demand inputs, keep config immutable)
        self._input_resolver = input_resolver or InputResolver(self._inputs)
        self._config_render = ConfigRender()

    async def boot_up(self, *, session: PromptSession | None = None) -> None:
        """
        启动计算机，初始化 MCP 服务器管理器。
        Boot up the computer and initialize the MCP server manager.

        1. 将 self._mcp_servers 逐个进行 model_dump 拿到dict配置，然后配合 self._inputs 进行ConfigRender。因为在具体配置中可能存在动态变量
            的引用。需要在此消解
        2. 通过当前类的 _resolve_prompt_string _resolve_pick_string _resolve_command 等方法对 MCPServerInput 做解析拿到最终结果进行替换
        3. 对于 self._mcp_servers 配置的符合变量提取模式但没有提供对应 input 定义时，不做任何处理，使用原值传递。
        """
        self.mcp_manager = MCPServerManager(auto_connect=self._auto_connect, auto_reconnect=self._auto_reconnect)
        # 中文: 对每个 Server 配置执行：model_dump -> 按需渲染(遇到占位符才解析 input) -> 重新校验生成不可变对象
        # English: For each server config: model_dump -> on-demand render (resolve inputs only when referenced) ->
        #          model_validate to rebuild immutable object
        validated_servers: list[MCPServerConfig] = []

        async def _resolve_input_by_id(input_id: str) -> Any:
            try:
                return await self._input_resolver.aresolve_by_id(input_id, session=session)
            except InputNotFoundError:
                # 未找到输入项，按要求保留原始输出并打印警告
                logger.warning(f"未定义的输入占位符: {input_id} / Undefined input placeholder: {input_id}")
                raise

        # 注意: 假设 self._mcp_servers 为 Iterable[MCPServerConfig]
        for server_cfg in self._mcp_servers:
            try:
                raw = server_cfg.model_dump(mode="json")
                rendered = await self._config_render.arender(raw, _resolve_input_by_id)
                validated = type(server_cfg).model_validate(rendered)
                validated_servers.append(validated)
            except Exception as e:
                logger.error(f"配置渲染或校验失败: {getattr(server_cfg, 'name', 'unknown')} - {e}")
                # 按稳妥策略: 保留原配置继续
                validated_servers.append(server_cfg)

        await self.mcp_manager.ainitialize(validated_servers)

    async def _arender_and_validate_server(
        self, server: MCPServerConfig | dict[str, Any], *, session: PromptSession | None = None
    ) -> MCPServerConfig:
        """
        动态渲染并校验单个 MCP 服务器配置，支持原始字典或模型实例。
        Render and validate a single MCP server config dynamically, supporting raw dict or model instance.

        规则 Rules:
          - 使用 ConfigRender 对包含 ${input:...} 的占位符进行惰性渲染，解析时依赖当前 InputResolver。
          - 渲染后使用 Pydantic 校验并生成不可变模型对象（确保最终为类型安全且不可变）。

        Args:
          - server (MCPServerConfig | dict[str, Any]): 待处理的配置，可以是 Pydantic 模型或原始字典。| The config to process, can be
                a Pydantic model or a raw dict.
          - session (PromptSession | None, optional): 若渲染过程中需要交互式输入解析，使用的 Prompt 会话；可为空表示静默解析。 |
                Prompt session used for interactive resolving during rendering; can be None for silent resolving.

        Returns:
          - MCPServerConfig:
            中文: 通过渲染与校验后的不可变配置对象。
            English: The immutable config object after rendering and validation.

        Raises:
          - InputNotFoundError:
            中文: 当渲染中引用了未定义的 input 占位符时抛出（异常会被向上抛，由调用者决定回退策略）。
            English: Raised when an undefined input placeholder is referenced during rendering (propagated to caller).
          - Exception:
            中文: 其他渲染/校验阶段发生的异常，将被记录日志并继续向上抛出。
            English: Other exceptions during render/validation are logged and re-raised.

        Notes:
          - 中文: 若传入的是字典，将使用 TypeAdapter(MCPServerConfig) 进行模型解析；若为模型实例，则按其具体类型进行校验。
          - English: If input is a dict, TypeAdapter(MCPServerConfig) is used; if it's a model instance, its concrete type validates.
        """

        # 中文: 根据 input_id 解析输入值，未定义时抛出 InputNotFoundError
        # English: Resolve input value by input_id; raise InputNotFoundError if not defined
        async def _resolve_input_by_id(input_id: str) -> Any:
            try:
                return await self._input_resolver.aresolve_by_id(input_id, session=session)
            except InputNotFoundError:
                logger.warning(f"未定义的输入占位符: {input_id} / Undefined input placeholder: {input_id}")
                # 透传异常到上层，由上层决定是否回退或继续
                raise

        try:
            if isinstance(server, dict):
                raw = server
                rendered = await self._config_render.arender(raw, _resolve_input_by_id)
                # 使用 TypeAdapter 将 union 类型解析为具体模型
                validated = TypeAdapter(MCPServerConfig).validate_python(rendered)
            else:
                raw = server.model_dump(mode="json")
                rendered = await self._config_render.arender(raw, _resolve_input_by_id)
                validated = type(server).model_validate(rendered)
            return validated
        except Exception as e:
            name = (server.get("name") if isinstance(server, dict) else getattr(server, "name", "unknown")) or "unknown"
            logger.error(f"动态渲染/校验MCP配置失败: {name} - {e}")
            raise e

    async def aadd_or_aupdate_server(self, server: MCPServerConfig | dict[str, Any], *, session: PromptSession | None = None) -> None:
        """
        动态添加或更新某个MCP Server配置（支持 inputs 占位符解析）。
        Add or update a MCP Server config dynamically (supports inputs placeholder resolving).

        Args:
            session (PromptSession | None): Computer管理Session
            server (MCPServerConfig | dict[str, Any]): 待添加/更新的配置，可为模型或原始字典。
        """
        # 确保 manager 已初始化
        if self.mcp_manager is None:
            self.mcp_manager = MCPServerManager(auto_connect=self._auto_connect, auto_reconnect=self._auto_reconnect)

        validated = await self._arender_and_validate_server(server, session=session)
        await self.mcp_manager.aadd_or_aupdate_server(validated)

    async def aremove_server(self, server_name: str, *, session: PromptSession | None = None) -> None:
        """
        动态移除某个MCP Server配置。
        Remove a MCP Server config dynamically.

        Args:
            server_name (str): 配置名称。
        """
        if not self.mcp_manager:
            # 未初始化则无操作
            logger.warning("MCP 管理器尚未初始化，忽略移除操作 / MCP manager not initialized, skip remove")
            return
        await self.mcp_manager.aremove_server(server_name)

    def update_inputs(self, inputs: set[MCPServerInput], *, session: PromptSession | None = None) -> None:
        """
        更新 inputs 定义，并清空解析缓存。
        Update inputs definition and clear resolver cache.

        注意：更新 inputs 只会影响后续的渲染，不会自动对已激活的配置进行重新渲染/重启。
        如需应用到已存在的服务，可结合 aadd_or_aupdate_server 重新提交配置达到热更新效果。
        """
        self._inputs = set(inputs or set())
        # 复用传入或已有的会话，以便后续解析共享同一 Session
        # Reuse provided or existing session so subsequent resolving shares the same session
        sess = session or getattr(self._input_resolver, "session", None)
        self._input_resolver = InputResolver(self._inputs, session=sess)
        # 清理缓存，确保后续渲染使用最新 inputs
        self._input_resolver.clear_cache()

    def add_or_update_input(self, input_cfg: MCPServerInput, *, session: PromptSession | None = None) -> None:
        """
        按 id 动态新增或更新单个 input。
        Add or update a single input by id dynamically.

        规则 Rules:
          - 以 input.id 为唯一键，存在则替换，不存在则追加
          - 重新构建 InputResolver 并清空对应缓存，确保后续渲染拿到最新值
        """
        if not input_cfg or not getattr(input_cfg, "id", None):
            logger.warning("无效的 input 配置，忽略 / Invalid input config, skip")
            return

        # 由于 __hash__ 与 __eq__ 基于 id，先丢弃再添加可实现“更新”
        self._inputs.discard(input_cfg)
        self._inputs.add(input_cfg)

        # 重新初始化解析器以应用最新定义，并清理该 id 的缓存
        sess = session or getattr(self._input_resolver, "session", None)
        self._input_resolver = InputResolver(self._inputs, session=sess)
        self._input_resolver.clear_cache(input_cfg.id)

    def remove_input(self, input_id: str, *, session: PromptSession | None = None) -> bool:
        """
        按 id 移除单个 input，返回是否删除成功。
        Remove a single input by id. Returns whether deletion happened.
        """
        if not input_id:
            return False

        removed = False
        target = None
        for existed in self._inputs:
            if existed.id == input_id:
                target = existed
                break
        if target is not None:
            self._inputs.discard(target)
            removed = True

        # 重新初始化解析器，并清理该 id 的缓存（如果有）
        sess = session or getattr(self._input_resolver, "session", None)
        self._input_resolver = InputResolver(self._inputs, session=sess)
        self._input_resolver.clear_cache(input_id)
        return removed

    def get_input(self, input_id: str, *, session: PromptSession | None = None) -> MCPServerInput | None:
        """
        获取指定 id 的 input 定义（只读）。
        Get input definition by id (read-only).
        """
        if not input_id:
            return None
        for existed in self._inputs:
            if existed.id == input_id:
                return existed
        return None

    def list_inputs(self, *, session: PromptSession | None = None) -> tuple[MCPServerInput, ...]:
        """
        列出当前全部 inputs（不可变）。
        List all current inputs (immutable).
        """
        return tuple(self._inputs)

    # ------------------------
    # 当前 inputs 值（缓存）增删改查 / CRUD for current input values (cache)
    # ------------------------
    def get_input_value(self, input_id: str, *, session: PromptSession | None = None) -> Any | None:
        """
        中文: 获取指定 id 的当前已解析值（来自缓存）。若尚未解析，则返回 None。
        English: Get current resolved value for given id from cache. Returns None if not resolved yet.
        """
        return self._input_resolver.get_cached_value(input_id)

    def set_input_value(self, input_id: str, value: Any, *, session: PromptSession | None = None) -> bool:
        """
        中文: 设置指定 id 的当前值（写入缓存）。仅当该 id 在 inputs 定义中存在时生效，返回是否成功。
        English: Set current value for given id (write to cache). Only works if id exists in inputs; returns success.
        """
        return self._input_resolver.set_cached_value(input_id, value)

    def remove_input_value(self, input_id: str, *, session: PromptSession | None = None) -> bool:
        """
        中文: 删除指定 id 的当前缓存值，返回是否删除发生。
        English: Delete current cached value for given id. Returns whether deletion happened.
        """
        return self._input_resolver.delete_cached_value(input_id)

    def list_input_values(self, *, session: PromptSession | None = None) -> dict[str, Any]:
        """
        中文: 列出所有已解析的 inputs 当前值（缓存快照）。若无则返回空字典。
        English: List all resolved input values (cache snapshot). Returns empty dict if none.
        """
        return self._input_resolver.list_cached_values()

    def clear_input_values(self, input_id: str | None = None, *, session: PromptSession | None = None) -> None:
        """
        中文: 清空所有或指定 id 的输入值缓存。
        English: Clear all cached values or the specified id.
        """
        self._input_resolver.clear_cache(input_id)

    async def shutdown(self, *, session: PromptSession | None = None) -> None:
        """
        关闭计算机，关闭 MCP 服务器管理器。
        Shutdown the computer and close the MCP server manager.
        """
        if self.mcp_manager:
            await self.mcp_manager.aclose()
        self.mcp_manager = None

    async def __aenter__(self) -> "Computer":
        """
        异步上下文进入方法。
        Async context enter method.

        Returns:
            Computer: 当前实例。Current instance.
        """
        await self.boot_up()
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        """
        异步上下文退出方法。
        Async context exit method.

        Args:
            exc_type (type[BaseException] | None): 异常类型。Exception type.
            exc_val (BaseException | None): 异常值。Exception value.
            exc_tb (object | None): 异常追踪。Exception traceback.
        """
        await self.shutdown()

    @property
    def mcp_servers(self) -> tuple[MCPServerConfig, ...]:
        """
        获取 MCP 服务器配置（不可变）。
        Get MCP server config (immutable).

        Returns:
            tuple[MCPServerConfig, ...]: 配置字典。Config dict.
        """
        return tuple(self._mcp_servers)

    @property
    def inputs(self) -> tuple[MCPServerInput, ...]:
        """
        获取 MCP 服务配置中的动态字段定义（不可变视图）。内部以 set 管理，返回 tuple 快照。
        Get Inputs in MCP server config (immutable view). Internally managed as a set, returns a tuple snapshot.

        Returns:
            tuple[MCPServerInput, ...]: 动态字段定义。Inputs
        """
        return tuple(self._inputs)

    async def aget_available_tools(self) -> list[SMCPTool]:
        """
        获取可用工具列表。
        Get available tools list.

        Returns:
            list[SMCPTool]: 工具列表。Tool list.
        """
        # 从Manager获取全部工具
        tools = [t async for t in self.mcp_manager.available_tools()]

        def is_attr(v: Any) -> bool:
            """
            判断值是否为简单属性。
            Check if value is a simple attribute.

            Args:
                v (Any): 待检测值。Value to check.

            Returns:
                bool: 是否为简单属性。Whether it is simple attribute.
            """
            try:
                TypeAdapter(AttributeValue).validate_python(v)
                return True
            except Exception as e:
                logger.debug(f"非简单属性:{v}", exc_info=e)
                return False

        def convert_tool(t: Tool) -> SMCPTool:
            """
            将 MCP 工具定义转换为 SMCP 工具定义。
            Convert MCP tool definition to SMCP tool definition.

            Args:
                t (Tool): MCP 工具。MCP tool.

            Returns:
                SMCPTool: SMCP 工具。SMCP tool.
            """
            meta = {}
            if t.meta:
                for k, v in t.meta.items():
                    if not is_attr(v):
                        try:
                            meta[k] = json.dumps(v)
                        except Exception as e:
                            logger.error(f"无法序列化工具元数据{k}:{v}", exc_info=e)
                            meta[k] = str(v)
                    else:
                        meta[k] = v
            if t.annotations:
                meta["MCP_TOOL_ANNOTATION"] = t.annotations.model_dump(mode="json")
            return SMCPTool(name=t.name, description=t.description, params_schema=t.inputSchema, return_schema=t.outputSchema, meta=meta)

        mcp_tools = [convert_tool(t) for t in tools]
        return mcp_tools

    async def aexecute_tool(self, req_id: str, tool_name: str, parameters: dict, timeout: float | None = None) -> CallToolResult:
        """
        调用工具。主要通过Manager实现对MCP Server的调用，但是在此进行比如auto_apply的判断，如果有需要用户二次确认的设计，在此实现。二次确认
            的方法由初始化时注入

        Args:
            req_id (str): 请求ID
            tool_name (str): 工具名称
            parameters (str): 工具调用参数
            timeout (float | None): 超时时间限制

        Returns:
            CallToolResult: MCP协议的标准返回
        """
        server_name, tool_name = await self.mcp_manager.avalidate_tool_call(tool_name, parameters)
        server_config = self.mcp_manager.get_server_config(server_name)
        if server_config.tool_meta.get(tool_name) and server_config.tool_meta[tool_name].auto_apply:
            return await self.mcp_manager.acall_tool(server_name, tool_name, parameters, timeout)
        else:
            # 除非明确允许 auto_apply 否则均需要调用二次确认回调进行确认
            if self._confirm_callback:
                try:
                    apply = self._confirm_callback(req_id, server_name, tool_name, parameters)
                except TimeoutError:
                    return CallToolResult(
                        content=[TextContent(text="当前工具需要用户二次确认是否可以调用，当前确认超时。", type="text")], isError=True
                    )
                except Exception as e:
                    logger.error(f"工具确认回调，调用失败:{e}")
                    return CallToolResult(
                        content=[TextContent(text=f"在工具调用二次确认时发生异常，异常信息：{e}", type="text")], isError=True
                    )
                if apply:
                    return await self.mcp_manager.acall_tool(server_name, tool_name, parameters, timeout)
                else:
                    return CallToolResult(content=[TextContent(text="工具调用二次确认被拒绝，请稍后再试", type="text")])
            else:
                return CallToolResult(
                    content=[
                        TextContent(
                            text="当前工具需要调用前进行二次确认，但客户端目前没有实现二次确认回调方法。请联系用户反馈此问题", type="text"
                        )
                    ],
                    isError=True,
                )
