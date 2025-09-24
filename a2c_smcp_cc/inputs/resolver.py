"""
文件名: resolver.py
作者: JQQ
创建日期: 2025/9/18
最后修改日期: 2025/9/18
版权: 2023 JQQ. All rights reserved.
依赖: prompt_toolkit, rich
描述:
  中文: inputs 解析器定义与实现。按需根据 id 解析三类输入：promptString、pickString、command。
  English: Input resolvers. Lazily resolve three kinds of inputs by id: promptString, pickString, command.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from a2c_smcp_cc.inputs.cli_io import ainput_pick, ainput_prompt, arun_command
from a2c_smcp_cc.mcp_clients.model import (
    MCPServerCommandInput,
    MCPServerInput,
    MCPServerPickStringInput,
    MCPServerPromptStringInput,
)
from a2c_smcp_cc.utils.logger import logger


class InputNotFoundError(KeyError):
    pass


class InputResolver:
    """
    中文: 输入解析器，支持基于 id 的惰性解析与结果缓存。
    English: Input resolver with lazy per-id resolution and result cache.
    """

    def __init__(self, inputs: Iterable[MCPServerInput]) -> None:
        self._inputs = {i.id: i for i in inputs}
        self._cache: dict[str, Any] = {}

    def clear_cache(self, key: str | None = None) -> None:
        if key is None:
            self._cache.clear()
        else:
            self._cache.pop(key, None)

    def get_cached_value(self, input_id: str) -> Any | None:
        """
        中文: 获取指定 id 的已解析缓存值；不存在时返回 None。
        English: Get cached value of given id; return None if not present.
        """
        return self._cache.get(input_id)

    def set_cached_value(self, input_id: str, value: Any) -> bool:
        """
        中文: 设置指定 id 的缓存值；仅当该 id 在 inputs 定义中存在时生效，返回是否成功。
        English: Set cached value for given id; only works if id exists in inputs. Returns success flag.
        """
        if input_id not in self._inputs:
            return False
        self._cache[input_id] = value
        return True

    def delete_cached_value(self, input_id: str) -> bool:
        """
        中文: 删除指定 id 的缓存值，返回是否删除发生。
        English: Delete cached value for given id, returns whether deletion happened.
        """
        if input_id in self._cache:
            self._cache.pop(input_id, None)
            return True
        return False

    def list_cached_values(self) -> dict[str, Any]:
        """
        中文: 返回当前所有 inputs 的缓存值快照（浅拷贝）。
        English: Return a snapshot (shallow copy) of all cached input values.
        """
        return dict(self._cache)

    async def aresolve_by_id(self, input_id: str) -> Any:
        if input_id in self._cache:
            return self._cache[input_id]
        cfg = self._inputs.get(input_id)
        if not cfg:
            raise InputNotFoundError(input_id)

        if isinstance(cfg, MCPServerPromptStringInput):
            value = await self._aresolve_prompt(cfg)
        elif isinstance(cfg, MCPServerPickStringInput):
            value = await self._aresolve_pick(cfg)
        elif isinstance(cfg, MCPServerCommandInput):
            value = await self._aresolve_command(cfg)
        else:  # pragma: no cover
            logger.warning(f"未知输入类型: {type(cfg)} / Unknown input type")
            value = None

        self._cache[input_id] = value
        return value

    async def _aresolve_prompt(self, cfg: MCPServerPromptStringInput) -> str:
        msg = cfg.description or f"请输入 {cfg.id} / Please input {cfg.id}"
        pwd = bool(cfg.password)
        return await ainput_prompt(msg, password=pwd, default=cfg.default)

    async def _aresolve_pick(self, cfg: MCPServerPickStringInput) -> str:
        msg = cfg.description or f"请选择 {cfg.id} / Please pick {cfg.id}"
        options = cfg.options or []
        default_index = None
        if cfg.default is not None and cfg.default in options:
            default_index = options.index(cfg.default)
        picked = await ainput_pick(msg, options, default_index=default_index, multi=False)
        return picked or (cfg.default or "")

    async def _aresolve_command(self, cfg: MCPServerCommandInput) -> Any:
        # 约定: command 为完整可执行字符串，由 shell 执行。args 如存在，暂不拼接，后续可扩展。
        return await arun_command(cfg.command, shell=True, parse="raw")
