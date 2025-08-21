# filename: main.py
# @Time    : 2025/8/17 16:52
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm
import json

from mcp import Tool
from pydantic import TypeAdapter

from a2c_smcp_cc.mcp_clients.manager import MCPServerManager
from a2c_smcp_cc.mcp_clients.model import MCPServerConfig
from a2c_smcp_cc.socketio.smcp import SMCPTool
from a2c_smcp_cc.socketio.types import AttributeValue
from a2c_smcp_cc.utils.logger import logger


class Computer:
    def __init__(self, mcp_manager: MCPServerManager, config: list[MCPServerConfig] | None = None) -> None:
        self.mcp_manager = mcp_manager
        self._config = config or []

    def run(self) -> None: ...

    @property
    def config(self) -> list[MCPServerConfig]:
        """获取配置"""
        return self._config

    async def aget_available_tools(self) -> list[SMCPTool]:
        """
        获取可用工具列表

        Returns:
            list[SMCPTool]: 工具列表
        """
        # 从Manager获取全部工具
        tools = [t async for t in self.mcp_manager.available_tools()]

        def convert_tool(t: Tool) -> SMCPTool:
            """将MCP工具定义转换为SMCP工具定义"""
            meta = {}
            if t.meta:
                for k, v in t.meta.items():
                    if not TypeAdapter(AttributeValue).validate_python(v):
                        try:
                            meta[k] = json.dumps(v)
                        except Exception as e:
                            logger.error(f"无法序列化工具元数据{k}:{v}", exc_info=e)
                            meta[k] = str(v)
                    else:
                        meta[k] = v
            if t.annotations:
                meta["MCP_TOOL_ANNOTATION"] = t.annotations.model_dump(mode="json")
            return SMCPTool(name=t.name, description=t.description, params_schema=t.inputSchema, return_schema=t.outputSchema, meta=t.meta)

        mcp_tools = [convert_tool(t) for t in tools]
        return mcp_tools
