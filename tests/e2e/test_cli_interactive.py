"""
文件名: test_cli_interactive.py
作者: JQQ
创建日期: 2025/9/22
最后修改日期: 2025/9/22
版权: 2023 JQQ. All rights reserved.
依赖: pytest, pexpect
描述:
  中文: 通过 pexpect 驱动真实进程的交互式 CLI e2e 测试用例。
  English: End-to-end tests for interactive CLI driven by pexpect against a real process.
"""

from __future__ import annotations

import re

import pytest

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")


@pytest.mark.e2e
def test_enter_does_nothing(cli_proc: pexpect.spawn) -> None:
    """
    中文: 在 a2c> 下按回车，应该不打印帮助，直接返回到下一次提示符。
    English: Pressing Enter at a2c> should do nothing and return to the next prompt without printing help.
    """
    child = cli_proc

    # 发送空回车 / send empty Enter
    child.sendline("")
    child.expect("a2c> ")

    # 获取这次 expect 之前的输出内容 / capture output before the prompt
    output = child.before or ""

    # 不应出现帮助标题 / should not contain help title
    assert "可用命令 / Commands" not in output
    assert re.search(r"\bCommands\b", output) is None


@pytest.mark.e2e
def test_help_shows_table(cli_proc: pexpect.spawn) -> None:
    """
    中文: 输入 help 或 ? 能展示帮助表格。
    English: Typing help or ? should display the help table.
    """
    child = cli_proc

    # 请求帮助 / ask for help
    child.sendline("help")
    # 等到下一次提示符，期间应输出帮助表格 / wait for prompt again
    child.expect("a2c> ")
    output = child.before or ""

    assert "可用命令 / Commands" in output
    assert "status" in output and "tools" in output and "quit" in output

    # 再用 ? 验证一次 / verify with ? again
    child.sendline("?")
    child.expect("a2c> ")
    output2 = child.before or ""
    assert "可用命令 / Commands" in output2
