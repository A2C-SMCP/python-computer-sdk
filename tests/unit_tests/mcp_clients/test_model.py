# -*- coding: utf-8 -*-
# filename: test_model.py
# @Time    : 2025/8/18 13:35
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm

import pytest
from mcp import StdioServerParameters
from mcp.client.session_group import SseServerParameters, StreamableHttpParameters
from polyfactory.factories.pydantic_factory import ModelFactory

from a2c_smcp_cc.mcp_clients.model import (
    BaseMCPServerConfig,
    MCPServerConfig,
    SseServerConfig,
    StdioServerConfig,
    StreamableHttpServerConfig,
    ToolMeta,
)


# ----------- 工厂类生成测试数据 -----------
class ToolMetaFactory(ModelFactory):
    __model__ = ToolMeta

    @classmethod
    def auto_apply(cls) -> bool | None:
        return cls.__random__.choice([True, False, None])

    @classmethod
    def alias(cls) -> str | None:
        return cls.__random__.choice([None, f"alias_{cls.__random__.randint(1, 100)}"])


class BaseMCPServerConfigFactory(ModelFactory):
    __model__ = BaseMCPServerConfig
    __random_seed__ = 42  # 固定随机种子保证可重复性

    @classmethod
    def name(cls) -> str:
        return f"server_{cls.__random__.randint(1, 100)}"

    @classmethod
    def disabled(cls) -> bool:
        return cls.__random__.choice([True, False])

    @classmethod
    def forbidden_tools(cls) -> list:
        return [f"tool_{i}" for i in range(cls.__random__.randint(0, 5))]

    @classmethod
    def tool_meta(cls) -> dict:
        meta = {}
        tools = ToolMetaFactory.batch(size=cls.__random__.randint(1, 3))
        for index, tool_meta in enumerate(tools):
            meta[f"tool_{index}"] = tool_meta
        return meta


# 使用模拟参数创建子类工厂
class StdioServerConfigFactory(BaseMCPServerConfigFactory):
    __model__ = StdioServerConfig

    @classmethod
    def server_parameters(cls) -> StdioServerParameters:
        return ModelFactory.create_factory(StdioServerParameters).build()


class SseServerConfigFactory(BaseMCPServerConfigFactory):
    __model__ = SseServerConfig

    @classmethod
    def server_parameters(cls) -> SseServerParameters:
        return ModelFactory.create_factory(SseServerParameters).build()


class StreamableHttpServerConfigFactory(BaseMCPServerConfigFactory):
    __model__ = StreamableHttpServerConfig

    @classmethod
    def server_parameters(cls) -> StreamableHttpParameters:
        return ModelFactory.create_factory(StreamableHttpParameters).build()


# ----------- 测试用例 -----------
@pytest.mark.parametrize(
    "factory",
    [ToolMetaFactory, BaseMCPServerConfigFactory, StdioServerConfigFactory, SseServerConfigFactory, StreamableHttpServerConfigFactory],
)
def test_model_creation(factory):
    """测试模型实例是否能正确创建"""
    instance = factory.build()
    assert isinstance(instance, factory.__model__)


def test_tool_meta_extra_fields():
    """测试ToolMeta的extra字段功能"""
    data = {"auto_apply": True, "extra_field": "value", "another_field": 42}
    tool_meta = ToolMeta(**data)

    # 验证额外字段被保留
    assert tool_meta.extra_field == "value"
    assert tool_meta.another_field == 42


def test_server_config_inheritance():
    """测试服务器配置类的继承关系"""
    stdio_config = StdioServerConfigFactory.build()
    assert isinstance(stdio_config, BaseMCPServerConfig)
    assert isinstance(stdio_config.server_parameters, StdioServerParameters)

    sse_config = SseServerConfigFactory.build()
    assert isinstance(sse_config, BaseMCPServerConfig)
    assert isinstance(sse_config.server_parameters, SseServerParameters)

    http_config = StreamableHttpServerConfigFactory.build()
    assert isinstance(http_config, BaseMCPServerConfig)
    assert isinstance(http_config.server_parameters, StreamableHttpParameters)


def test_mcp_config_union():
    """测试MCPServerConfig类型别名接受所有子类型"""
    servers: list[MCPServerConfig] = [
        StdioServerConfigFactory.build(),
        SseServerConfigFactory.build(),
        StreamableHttpServerConfigFactory.build(),
    ]

    assert len(servers) == 3
    assert all(isinstance(s, (StdioServerConfig, SseServerConfig, StreamableHttpServerConfig)) for s in servers)


@pytest.mark.parametrize(
    "field, value",
    [
        ("name", 123),  # 错误类型
        ("disabled", "Test"),  # 类型不匹配
        ("forbidden_tools", [1, 2, 3]),  # 列表项类型错误
        ("tool_meta", {"key": "invalid"}),  # 值类型错误
    ],
)
def test_validation_errors(field, value):
    """测试基础模型的验证错误"""
    data = {"name": "valid_name", "disabled": False, "forbidden_tools": [], "tool_meta": {}, field: value}

    with pytest.raises(ValueError):
        BaseMCPServerConfig(**data)


def test_tool_meta_ret_mapper():
    """测试ToolMeta中ret_object_mapper的特殊处理"""
    mapper = {"field": "mapped_field", "nested": {"key": "value"}}
    tool_meta = ToolMeta(alias=None, auto_apply=None, ret_object_mapper=mapper)
    assert tool_meta.ret_object_mapper == mapper
