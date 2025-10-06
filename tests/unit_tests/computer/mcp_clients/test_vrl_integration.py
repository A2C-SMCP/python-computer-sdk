# -*- coding: utf-8 -*-
# filename: test_vrl_integration.py
# @Time    : 2025/10/6 14:30
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm

"""
VRL集成测试 / VRL Integration Tests

测试VRL脚本在MCP Server配置中的语法检查和工具返回值转换功能。
Tests VRL script syntax validation and tool return value transformation in MCP Server config.
"""

import json

import pytest
from mcp import StdioServerParameters
from mcp.types import CallToolResult, TextContent
from polyfactory.factories.pydantic_factory import ModelFactory

from a2c_smcp.computer.mcp_clients.model import A2C_VRL_TRANSFORMED, StdioServerConfig


def test_vrl_syntax_validation_success():
    """测试VRL语法验证成功 / Test VRL syntax validation success"""
    # 有效的VRL脚本
    # Valid VRL script
    valid_vrl = '.result = "success"'
    
    config = StdioServerConfig(
        name="test_server",
        disabled=False,
        forbidden_tools=[],
        tool_meta={},
        vrl=valid_vrl,
        server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
    )
    
    assert config.vrl == valid_vrl


def test_vrl_syntax_validation_failure():
    """测试VRL语法验证失败 / Test VRL syntax validation failure"""
    # 无效的VRL脚本
    # Invalid VRL script
    invalid_vrl = "this is not valid vrl syntax!!!"
    
    with pytest.raises(ValueError, match="VRL语法错误"):
        StdioServerConfig(
            name="test_server",
            disabled=False,
            forbidden_tools=[],
            tool_meta={},
            vrl=invalid_vrl,
            server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
        )


def test_vrl_none_or_empty_allowed():
    """测试VRL字段允许为None或空字符串 / Test VRL field allows None or empty string"""
    # None值应该被接受
    # None should be accepted
    config1 = StdioServerConfig(
        name="test_server",
        disabled=False,
        forbidden_tools=[],
        tool_meta={},
        vrl=None,
        server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
    )
    assert config1.vrl is None
    
    # 空字符串应该被接受
    # Empty string should be accepted
    config2 = StdioServerConfig(
        name="test_server",
        disabled=False,
        forbidden_tools=[],
        tool_meta={},
        vrl="",
        server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
    )
    assert config2.vrl == ""


def test_vrl_transformation_result_format():
    """测试VRL转换结果的存储格式 / Test VRL transformation result storage format"""
    # 模拟一个CallToolResult
    # Mock a CallToolResult
    result = CallToolResult(
        content=[TextContent(text="test result", type="text")],
        isError=False,
    )
    
    # 模拟VRL转换后的数据
    # Mock VRL transformed data
    transformed_data = {
        "status": "success",
        "message": "transformed",
        "data": {"key": "value"}
    }
    
    # 按照实现逻辑，转换后的数据应该被JSON序列化存储
    # According to implementation, transformed data should be JSON serialized
    result.meta = {A2C_VRL_TRANSFORMED: json.dumps(transformed_data, ensure_ascii=False)}
    
    # 验证存储格式
    # Verify storage format
    assert A2C_VRL_TRANSFORMED in result.meta
    assert isinstance(result.meta[A2C_VRL_TRANSFORMED], str)
    
    # 验证可以反序列化
    # Verify it can be deserialized
    restored = json.loads(result.meta[A2C_VRL_TRANSFORMED])
    assert restored == transformed_data


def test_vrl_complex_script():
    """测试复杂的VRL脚本 / Test complex VRL script"""
    # 一个更复杂的VRL脚本，包含多个操作
    # A more complex VRL script with multiple operations
    complex_vrl = """
    .status = "processed"
    .timestamp = now()
    .transformed = true
    """
    
    config = StdioServerConfig(
        name="test_server",
        disabled=False,
        forbidden_tools=[],
        tool_meta={},
        vrl=complex_vrl,
        server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
    )
    
    assert config.vrl == complex_vrl


def test_vrl_with_conditional_logic():
    """测试带条件逻辑的VRL脚本 / Test VRL script with conditional logic"""
    # VRL支持条件逻辑
    # VRL supports conditional logic
    conditional_vrl = """
    if .isError == true {
        .status = "error"
    } else {
        .status = "success"
    }
    """
    
    config = StdioServerConfig(
        name="test_server",
        disabled=False,
        forbidden_tools=[],
        tool_meta={},
        vrl=conditional_vrl,
        server_parameters=ModelFactory.create_factory(StdioServerParameters).build(),
    )
    
    assert config.vrl == conditional_vrl
