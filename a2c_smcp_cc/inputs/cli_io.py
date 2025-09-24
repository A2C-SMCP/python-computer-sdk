"""
文件名: cli_io.py
作者: JQQ
创建日期: 2025/9/18
最后修改日期: 2025/9/18
版权: 2023 JQQ. All rights reserved.
依赖: prompt_toolkit, rich
描述:
  中文: 命令行交互 I/O 抽象，提供异步的提示输入、密码输入、选项选择与命令执行封装。
  English: CLI interactive I/O abstraction. Provides async prompt input, password input,
           pick options and command execution wrappers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from prompt_toolkit import PromptSession
from prompt_toolkit.patch_stdout import patch_stdout
from rich.table import Table

from a2c_smcp_cc.utils import console as console_util


async def ainput_prompt(message: str, *, password: bool = False, default: str | None = None) -> str:
    """
    中文: 提示用户输入字符串；当 password=True 时进行掩码输入。
    English: Prompt user for a string input; when password=True, mask the input.
    """
    session = PromptSession()
    # 中文: 为避免与交互命令提示符 `a2c>` 同行导致光标错位，这里强制在新行开始用户输入提示。
    # English: To avoid cursor misalignment with the interactive 'a2c>' prompt, start input on a fresh line.
    prompt_text = "\n" + f"{message} " + (f"[default: {repr(default)}] " if default is not None else "")
    # 中文: 使用 raw 模式减少 prompt_toolkit 与上层输出的干扰。
    # English: Use raw mode to reduce interference with upper-level outputs.
    with patch_stdout(raw=True):
        try:
            value = await session.prompt_async(prompt_text, is_password=password)
        except (EOFError, KeyboardInterrupt):
            return default or ""
    if value == "" and default is not None:
        return default
    return value


async def ainput_pick(
    message: str,
    options: list[str] | tuple[str, ...],
    *,
    default_index: int | None = None,
    multi: bool = False,
) -> None | list[str] | str | list[Any]:
    """
    中文: 让用户以序号选择一个或多个字符串。
    English: Let user pick one or multiple strings by index.
    """
    if not options:
        return [] if multi else ""

    table = Table(title=message)
    table.add_column("#", justify="right")
    table.add_column("Option", overflow="fold")
    for idx, opt in enumerate(options):
        table.add_row(str(idx), opt)
    console_util.console.print(table)

    tip = "输入序号，多个用逗号分隔" if multi else "输入序号"
    if default_index is not None and 0 <= default_index < len(options):
        tip += f"（默认: {default_index}）"

    session = PromptSession()
    while True:
        # 中文: 与 ainput_prompt 相同，强制换行并启用 raw 模式，避免与 `a2c>` 同行。
        # English: Same as ainput_prompt: force newline and raw mode to avoid sharing line with 'a2c>'.
        with patch_stdout(raw=True):
            try:
                raw = await session.prompt_async("\n" + f"{tip}: ")
            except (EOFError, KeyboardInterrupt):
                if default_index is not None and 0 <= default_index < len(options):
                    return [options[default_index]] if multi else options[default_index]
                return [] if multi else ""

        raw = raw.strip()
        if raw == "" and default_index is not None and 0 <= default_index < len(options):
            return [options[default_index]] if multi else options[default_index]

        try:
            if multi:
                idxs = [int(x.strip()) for x in raw.split(",") if x.strip() != ""]
                if any(i < 0 or i >= len(options) for i in idxs):
                    console_util.console.print("[yellow]序号越界，请重试 / Index out of range, please retry[/yellow]")
                    continue
                picked = [options[i] for i in idxs]
                # 去重保持顺序
                seen: set[str] = set()
                result: list[str] = []
                for p in picked:
                    if p not in seen:
                        seen.add(p)
                        result.append(p)
                return result
            else:
                idx = int(raw)
                if idx < 0 or idx >= len(options):
                    console_util.console.print("[yellow]序号越界，请重试 / Index out of range, please retry[/yellow]")
                    continue
                return options[idx]
        except ValueError:
            console_util.console.print("[yellow]请输入有效的数字 / Please enter valid number(s)[/yellow]")


async def arun_command(
    command: str,
    *,
    cwd: str | None = None,
    timeout: float | None = None,
    shell: bool = True,
    parse: str = "raw",
) -> Any:
    """
    中文: 异步执行命令并返回结果，支持超时、工作目录与解析模式。
    English: Run a command asynchronously with timeout, cwd, and parse modes.
    parse: 'raw' | 'lines' | 'json'
    """
    if shell:
        create = asyncio.create_subprocess_shell
        args = command
    else:
        create = asyncio.create_subprocess_exec
        # 简化处理：当 shell=False 时仅将 command 作为可执行名，不拆分参数
        args = command

    proc = await create(
        args,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        if timeout:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        else:
            stdout, stderr = await proc.communicate()
    except TimeoutError:
        try:
            proc.kill()
        except Exception:
            pass
        raise TimeoutError(f"Command timeout: {command}") from None

    rc = proc.returncode
    out = stdout.decode(errors="ignore") if stdout else ""
    err = stderr.decode(errors="ignore") if stderr else ""
    if rc != 0:
        # 保留原始输出，交由上层决定是否继续
        raise RuntimeError(f"Command failed (rc={rc}): {command}\nSTDERR: {err.strip()}")

    out = out.strip()
    if parse == "lines":
        return [line for line in out.splitlines() if line.strip() != ""]
    if parse == "json":
        import json

        try:
            return json.loads(out)
        except Exception:
            # 回退为原始文本
            return out
    return out
