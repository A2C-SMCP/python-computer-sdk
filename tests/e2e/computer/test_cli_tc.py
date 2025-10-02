"""
文件名: test_cli_tc.py
作者: JQQ
创建日期: 2025/10/02
最后修改日期: 2025/10/02
版权: 2023 JQQ. All rights reserved.
依赖: pytest, pexpect
描述:
  中文:
    - 端到端验证交互式 CLI 的 `tc` 命令，针对真实 stdio MCP server（direct_execution.py）。
    - 通过写入 server 配置文件并使用 `server add @file` + `start <name>` 启动。
    - 为避免二次确认阻断，使用 `tool_meta.hello.auto_apply=true` 开启自动执行。
    - 发送 `tc` 的 JSON 负载（与 Socket.IO 一致的 `ToolCallReq` 结构），期望输出包含工具返回文本。

  English:
    - E2E test for interactive CLI `tc` against real stdio MCP server (direct_execution.py).
    - Start server via config file and `server add @file` + `start <name>`.
    - Enable `tool_meta.hello.auto_apply=true` to bypass confirm gate.
    - Send `tc` JSON payload (Socket.IO-compatible `ToolCallReq`) and expect tool output text.

测试要点与断言:
  1) 成功添加并启动名为 `e2e-tc` 的 stdio 服务器
  2) `tools` 输出包含 `hello`
  3) 发送 `tc`（tool_name 使用 `e2e-tc/hello` 以确保路由）后输出包含 `Hello, E2E!`
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.e2e.computer.utils import expect_prompt_stable, strip_ansi

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")


@pytest.mark.e2e
def test_tc_call_hello(cli_proc: pexpect.spawn, tmp_path: Path) -> None:
    """
    中文: 通过 `tc` 调用 `hello` 工具，并校验结果文本。
    English: Call `hello` tool via `tc` and assert result text.
    """
    child = cli_proc

    # 1) 写入 server 配置文件（打开 auto_apply），指向 direct_execution.py
    server_cfg = {
        "name": "e2e-tc",
        "type": "stdio",
        "disabled": False,
        "forbidden_tools": [],
        "tool_meta": {"hello": {"auto_apply": True}},
        "server_parameters": {
            "command": "python",
            "args": [
                "tests/integration_tests/computer/mcp_servers/direct_execution.py",
            ],
            "env": None,
            "cwd": None,
            "encoding": "utf-8",
            "encoding_error_handler": "strict",
        },
    }
    cfg_path = tmp_path / "server_e2e_tc.json"
    cfg_path.write_text(json.dumps(server_cfg, ensure_ascii=False), encoding="utf-8")

    # 2) 添加配置并启动
    child.sendline(f"server add @{cfg_path}")
    expect_prompt_stable(child, quiet=0.6, max_wait=15.0)
    child.sendline("start e2e-tc")
    expect_prompt_stable(child, quiet=0.6, max_wait=15.0)

    # 3) 确认工具已可见（tools 列表应包含 hello）
    child.sendline("tools")
    tools_out = expect_prompt_stable(child, quiet=0.6, max_wait=12.0)
    assert "hello" in strip_ansi(tools_out)

    # 4) 构造 tc 负载，工具名使用原始 MCP 工具名（不加前缀）。
    #    中文: Manager 会在所有已启动 server 中解析该工具名；我们前一步已确认 tools 中包含 hello。
    #    English: Manager resolves plain tool name across active servers; tools list already contains 'hello'.
    tc_payload = {
        "robot_id": "bot-e2e",
        "req_id": "req-e2e-hello",
        "computer": "ignored",
        "tool_name": "hello",
        "params": {"name": "E2E"},
        "timeout": 10,
    }

    child.sendline(f"tc {json.dumps(tc_payload, ensure_ascii=False)}")
    out = expect_prompt_stable(child, quiet=0.8, max_wait=20.0)
    out = strip_ansi(out)

    # 5) 断言包含调用结果文本
    assert "Hello, E2E!" in out, f"unexpected tc output:\n{out}"
