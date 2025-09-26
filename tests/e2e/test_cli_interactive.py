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
import time

import pytest

pexpect = pytest.importorskip("pexpect", reason="e2e tests require pexpect; install with `pip install pexpect`.")

# 中文: ANSI 控制序列匹配与去除工具，避免 prompt_toolkit 的控制序列影响断言
# English: ANSI control-sequence helpers to avoid prompt_toolkit artifacts breaking assertions
ANSI = r"(?:\x1b\[[0-?]*[ -/]*[@-~])*"
PROMPT_RE = re.compile(ANSI + r"a2c>" + ANSI)
HELP_TITLE_RE = re.compile(ANSI + r".*可用命令 / Commands.*", re.S)


def strip_ansi(s: str) -> str:
    """
    中文: 去除 ANSI 控制序列，返回纯文本。
    English: Strip ANSI control sequences and return plain text.
    """
    return re.sub(ANSI, "", s)


@pytest.mark.e2e
def test_enter_does_nothing(cli_proc: pexpect.spawn) -> None:
    """
    中文: 在 a2c> 下按回车，应该不打印帮助，直接返回到下一次提示符。
    English: Pressing Enter at a2c> should do nothing and return to the next prompt without printing help.
    """
    child = cli_proc

    # 发送空回车 / send empty Enter
    child.sendline("")
    child.expect(PROMPT_RE)

    # 获取这次 expect 之前的输出内容 / capture output before the prompt
    output = strip_ansi(child.before or "")

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
    # 先等待帮助标题出现，再等待提示符，避免 child.before 为空 / wait for help title first, then the prompt
    child.expect(HELP_TITLE_RE)
    # 给渲染/注册留一点时间 / allow a short time for render/registration
    time.sleep(1.0)
    child.expect(PROMPT_RE)
    output = strip_ansi(child.before or "")

    assert "server add <json|@file>" in output
    assert "socket connect" in output

    # 再用 ? 验证一次 / verify with ? again
    child.sendline("?")
    child.expect(HELP_TITLE_RE)
    # 给渲染/注册留一点时间 / allow a short time for render/registration
    time.sleep(1.0)
    child.expect(PROMPT_RE)
    output2 = strip_ansi(child.before or "")
    assert "server add <json|@file>" in output2
