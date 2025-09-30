# -*- coding: utf-8 -*-
# filename: test_namespace_sync.py
# @Time    : 2025/09/30 23:42
# @Author  : A2C-SMCP
"""
中文：针对 `a2c_smcp/server/sync_namespace.py` 的同步命名空间集成测试。
English: Integration tests for SyncSMCPNamespace in `a2c_smcp/server/sync_namespace.py`.

说明：
- 仅在本测试包使用的 `_local_sync_server.py` 启动同步 Socket.IO 服务器。
- 使用 werkzeug 在独立线程中运行 WSGI 服务器。
"""
import socket
import threading
import time
from collections.abc import Generator
from typing import Any

import pytest
from socketio import Client, Namespace
from werkzeug.serving import make_server

from a2c_smcp.smcp import (
    ENTER_OFFICE_NOTIFICATION,
    GET_TOOLS_EVENT,
    JOIN_OFFICE_EVENT,
    LEAVE_OFFICE_EVENT,
    LEAVE_OFFICE_NOTIFICATION,
    SMCP_NAMESPACE,
    TOOL_CALL_EVENT,
    UPDATE_CONFIG_EVENT,
)
from tests.integration_tests.server._local_sync_server import create_local_sync_server


@pytest.fixture
def sync_server_port() -> int:
    """
    中文：查找可用端口。
    English: Find an available TCP port.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def startup_and_shutdown_local_sync_server(sync_server_port: int) -> Generator[Namespace, Any, None]:
    sio, ns, wsgi_app = create_local_sync_server()
    # 禁用监控任务避免关闭时出错
    sio.eio.start_service_task = False

    server = make_server("localhost", sync_server_port, wsgi_app, threaded=True)

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    try:
        yield ns
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _join_office(client: Client, role: str, office_id: str, name: str) -> None:
    ok, err = client.call(
        JOIN_OFFICE_EVENT,
        {"role": role, "office_id": office_id, "name": name},
        namespace=SMCP_NAMESPACE,
    )
    assert ok and err is None


def test_enter_and_broadcast_sync(startup_and_shutdown_local_sync_server, sync_server_port: int) -> None:
    agent = Client()
    computer = Client()

    enter_events: list[dict] = []

    @agent.on(ENTER_OFFICE_NOTIFICATION, namespace=SMCP_NAMESPACE)
    def _on_enter(data: dict):  # noqa: ANN001
        enter_events.append(data)

    agent.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    office_id = "office-sync-s1"
    _join_office(agent, role="agent", office_id=office_id, name="robot-S1")

    computer.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    _join_office(computer, role="computer", office_id=office_id, name="comp-S1")

    time.sleep(0.2)
    assert enter_events, "Agent 应收到 ENTER_OFFICE_NOTIFICATION"

    agent.disconnect()
    computer.disconnect()


def test_leave_and_broadcast_sync(startup_and_shutdown_local_sync_server, sync_server_port: int) -> None:
    agent = Client()
    computer = Client()

    leave_events: list[dict] = []

    @agent.on(LEAVE_OFFICE_NOTIFICATION, namespace=SMCP_NAMESPACE)
    def _on_leave(data: dict):  # noqa: ANN001
        leave_events.append(data)

    agent.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    office_id = "office-sync-s2"
    _join_office(agent, role="agent", office_id=office_id, name="robot-S2")

    computer.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    _join_office(computer, role="computer", office_id=office_id, name="comp-S2")

    ok, err = computer.call(LEAVE_OFFICE_EVENT, {"office_id": office_id}, namespace=SMCP_NAMESPACE)
    assert ok and err is None

    time.sleep(0.2)
    assert leave_events, "Agent 应收到 LEAVE_OFFICE_NOTIFICATION"

    agent.disconnect()
    computer.disconnect()


def test_get_tools_success_sync(startup_and_shutdown_local_sync_server: Namespace, sync_server_port: int) -> None:
    """测试同步环境下获取工具列表，使用多线程避免阻塞"""

    # 共享数据结构（添加computer_sid字段）
    shared_data: dict = {
        "computer_sid": None,
        "error": None,
        "lock": threading.Lock(),  # 添加线程锁
    }
    # 用于同步的事件
    computer_ready = threading.Event()
    call_completed = threading.Event()

    def run_computer_client():
        """在独立线程中运行Computer客户端"""
        computer = Client()

        @computer.on(GET_TOOLS_EVENT, namespace=SMCP_NAMESPACE)
        def _on_get_tools(data: dict):  # noqa: ANN001
            return {
                "tools": [
                    {
                        "name": "echo",
                        "description": "echo text",
                        "params_schema": {"type": "object"},
                        "return_schema": None,
                    },
                ],
                "req_id": data["req_id"],
            }

        try:
            computer.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
            office_id = "office-sync-s3"
            _join_office(computer, role="computer", office_id=office_id, name="comp-S3")

            # 安全写入SID
            with shared_data["lock"]:
                shared_data["computer_sid"] = computer.get_sid(namespace=SMCP_NAMESPACE)

            computer_ready.set()  # 通知Computer客户端已准备好
            call_completed.wait(timeout=20)
        except Exception as e:
            with shared_data["lock"]:
                shared_data["error"] = f"Computer客户端错误: {str(e)}"
            pytest.fail("Computer初始化失败，线程运行异常")
        finally:
            try:
                computer.disconnect()
            except Exception:
                pass

    def run_agent_client():
        """在独立线程中运行Agent客户端"""
        agent = Client()

        try:
            agent.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
            office_id = "office-sync-s3"
            _join_office(agent, role="agent", office_id=office_id, name="robot-S3")

            if not computer_ready.wait(timeout=2):
                pytest.fail("Computer客户端连接超时")

            # 检查错误并获取SID
            with shared_data["lock"]:
                if shared_data["error"]:
                    pytest.fail(shared_data["error"])
                computer_sid = shared_data["computer_sid"]

            if not computer_sid:
                pytest.fail("未获取到Computer SID")

            # 确保Computer客户端完全连接后再进行调用
            time.sleep(0.2)
            # 使用共享的computer_sid执行调用
            res = agent.call(
                GET_TOOLS_EVENT,
                {"computer": computer_sid, "robot_id": agent.get_sid(SMCP_NAMESPACE), "req_id": "req-sync-1"},
                namespace=SMCP_NAMESPACE,
                timeout=15,
            )
            call_completed.set()
            assert isinstance(res, dict), f"期望返回dict，实际返回: {type(res)}"
            assert res.get("tools") and res["tools"][0]["name"] == "echo"
        except Exception as e:
            print(f"AgentRun Error: {e}")
            pytest.fail("AgentRun发生异常")
        finally:
            agent.disconnect()

    # 启动线程
    computer_thread = threading.Thread(target=run_computer_client, daemon=True)
    agent_thread = threading.Thread(target=run_agent_client, daemon=True)

    computer_thread.start()
    agent_thread.start()

    # 等待完成
    assert call_completed.wait(timeout=15), "调用未完成"
    computer_thread.join(timeout=2)
    agent_thread.join(timeout=2)


def test_update_config_broadcast_sync(startup_and_shutdown_local_sync_server, sync_server_port: int) -> None:
    agent = Client()
    computer = Client()

    received = {"count": 0}

    @agent.on("notify:update_config", namespace=SMCP_NAMESPACE)
    def _on_update(data: dict):  # noqa: ANN001
        received["count"] += 1

    agent.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    office_id = "office-sync-s4"
    _join_office(agent, role="agent", office_id=office_id, name="robot-S4")

    computer.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    _join_office(computer, role="computer", office_id=office_id, name="comp-S4")

    computer.call(UPDATE_CONFIG_EVENT, {"computer": computer.get_sid(namespace=SMCP_NAMESPACE)}, namespace=SMCP_NAMESPACE)

    time.sleep(0.2)
    assert received["count"] >= 1

    agent.disconnect()
    computer.disconnect()


def test_tool_call_forward_sync(startup_and_shutdown_local_sync_server, sync_server_port: int) -> None:
    """测试同步环境下工具调用转发，使用多线程避免阻塞"""
    agent = Client()
    computer = Client()

    received = {"count": 0, "data": None}
    call_result: dict = {"error": None}
    # 用于同步的事件
    computer_ready = threading.Event()
    call_completed = threading.Event()

    @computer.on(TOOL_CALL_EVENT, namespace=SMCP_NAMESPACE)
    def _on_tool_call(data: dict):  # noqa: ANN001
        received["count"] += 1
        received["data"] = data

    def run_computer_client():
        """在独立线程中运行Computer客户端"""
        try:
            computer.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
            office_id = "office-sync-s5"
            _join_office(computer, role="computer", office_id=office_id, name="comp-S5")
            computer_ready.set()  # 通知Computer客户端已准备好

            # 等待调用完成
            call_completed.wait(timeout=20)
        except Exception as e:
            call_result["error"] = f"Computer客户端错误: {str(e)}"
            computer_ready.set()
        finally:
            try:
                computer.disconnect()
            except Exception:
                pass

    # 先连接Agent客户端
    agent.connect(f"http://localhost:{sync_server_port}", namespaces=[SMCP_NAMESPACE], socketio_path="/socket.io")
    office_id = "office-sync-s5"
    _join_office(agent, role="agent", office_id=office_id, name="robot-S5")

    # 启动Computer客户端线程
    computer_thread = threading.Thread(target=run_computer_client, daemon=True)
    computer_thread.start()

    try:
        # 等待Computer客户端准备好
        if not computer_ready.wait(timeout=10):
            pytest.fail("Computer客户端连接超时")

        if call_result["error"]:
            pytest.fail(call_result["error"])

        # 确保Computer客户端完全连接后再进行调用
        time.sleep(0.2)

        # 执行Agent工具调用
        res = agent.call(
            TOOL_CALL_EVENT,
            {
                "robot_id": agent.get_sid(SMCP_NAMESPACE),
                "computer": computer.get_sid(SMCP_NAMESPACE),
                "tool_name": "echo",
                "params": {"text": "hi"},
                "req_id": "req-sync-2",
                "timeout": 5,
            },
            namespace=SMCP_NAMESPACE,
            timeout=15,
        )

        # 同步命名空间返回固定确认信息
        assert isinstance(res, dict) and res.get("status") == "sent"

        # 等待Computer端接收事件
        time.sleep(0.5)
        assert received["count"] == 1, f"Computer应该收到1次工具调用事件，实际收到{received['count']}次"

        # 验证接收到的数据
        assert received["data"] is not None
        assert received["data"]["tool_name"] == "echo"
        assert received["data"]["params"]["text"] == "hi"

    finally:
        call_completed.set()
        computer_thread.join(timeout=5)
        agent.disconnect()
