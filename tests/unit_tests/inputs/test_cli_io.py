# -*- coding: utf-8 -*-
# filename: test_cli_io.py
# @Time    : 2025/9/21 17:09
# @Author  : JQQ
# @Email   : jiaqia@qknode.com
# @Software: PyCharm

import json

import pytest

from a2c_smcp_cc.inputs.cli_io import ainput_pick, ainput_prompt, arun_command


@pytest.mark.asyncio
async def test_ainput_prompt_returns_default_on_interrupt(monkeypatch):
    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            raise EOFError()

    # patch PromptSession constructor to return dummy
    import a2c_smcp_cc.inputs.cli_io as cli_io

    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())

    value = await ainput_prompt("Enter:", default="def", password=True)
    assert value == "def"


@pytest.mark.asyncio
async def test_ainput_prompt_uses_default_on_empty(monkeypatch):
    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            return ""

    import a2c_smcp_cc.inputs.cli_io as cli_io

    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())

    value = await ainput_prompt("Enter:", default="hello")
    assert value == "hello"


@pytest.mark.asyncio
async def test_ainput_prompt_returns_value(monkeypatch):
    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            return "world"

    import a2c_smcp_cc.inputs.cli_io as cli_io

    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())

    value = await ainput_prompt("Enter:")
    assert value == "world"


@pytest.mark.asyncio
async def test_ainput_pick_single_happy_path(monkeypatch):
    inputs = iter(["1"])  # pick index 1

    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            return next(inputs)

    import a2c_smcp_cc.inputs.cli_io as cli_io

    # silence console printing by replacing console.print with no-op
    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())
    monkeypatch.setattr(cli_io.console, "print", lambda *a, **k: None)

    picked = await ainput_pick("Pick one", ["a", "b", "c"], multi=False)
    assert picked == "b"


@pytest.mark.asyncio
async def test_ainput_pick_multi_with_dedup_and_order(monkeypatch):
    inputs = iter(["2,0,2,0"])  # picks ["c","a","c","a"] -> dedup to ["c","a"]

    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            return next(inputs)

    import a2c_smcp_cc.inputs.cli_io as cli_io

    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())
    monkeypatch.setattr(cli_io.console, "print", lambda *a, **k: None)

    picked = await ainput_pick("Pick multi", ["a", "b", "c"], multi=True)
    assert picked == ["c", "a"]


@pytest.mark.asyncio
async def test_ainput_pick_default_on_interrupt_and_empty(monkeypatch):
    # first raise KeyboardInterrupt then return empty; both should yield default
    calls = {"n": 0}

    class DummySession:
        async def prompt_async(self, *args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise KeyboardInterrupt()
            return ""

    import a2c_smcp_cc.inputs.cli_io as cli_io

    monkeypatch.setattr(cli_io, "PromptSession", lambda: DummySession())
    monkeypatch.setattr(cli_io.console, "print", lambda *a, **k: None)

    picked = await ainput_pick("Pick one", ["a", "b"], default_index=1, multi=False)
    assert picked == "b"

    # empty input path
    calls["n"] = 0
    picked2 = await ainput_pick("Pick one", ["a", "b"], default_index=0, multi=True)
    assert picked2 == ["a"]


@pytest.mark.asyncio
async def test_arun_command_raw_and_lines_and_json():
    # raw
    out = await arun_command("echo hello", parse="raw")
    # macOS echo appends newline; function strips
    assert out == "hello"

    # lines
    out_lines = await arun_command("printf 'a\\nb\\n'", parse="lines")
    assert out_lines == ["a", "b"]

    # json success
    js = {"x": 1, "y": [1, 2]}
    cmd = "python - <<'PY'\nimport json,sys; print(json.dumps(%s))\nPY" % json.dumps(js)
    out_json = await arun_command(cmd, parse="json")
    assert out_json == js


@pytest.mark.asyncio
async def test_arun_command_timeout_and_error():
    # timeout
    with pytest.raises(TimeoutError):
        await arun_command("sleep 2", timeout=0.1)

    # non-zero exit -> RuntimeError
    with pytest.raises(RuntimeError):
        await arun_command("bash -c 'exit 7'")
