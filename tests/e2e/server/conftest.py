# -*- coding: utf-8 -*-
# filename: conftest.py
# @Time    : 2025/10/05 14:10
# @Author  : JQQ
# @Email   : jqq1716@gmail.com
# @Software: PyCharm
"""
中文: e2e Server 测试公共夹具。启动真实 Socket.IO HTTP 服务器，并提供 Agent 与 Computer 真实客户端。
English: Common fixtures for e2e Server tests. Boots a real Socket.IO HTTP server and provides real Agent/Computer clients.
"""

from __future__ import annotations

import contextlib
import multiprocessing
import socket
import time
from collections.abc import Iterator
from typing import Any

import pytest
import socketio
from socketio import Namespace, Server, WSGIApp
from werkzeug.serving import make_server

from a2c_smcp.server import SyncSMCPNamespace
from a2c_smcp.server.sync_auth import SyncAuthenticationProvider
from a2c_smcp.smcp import SMCP_NAMESPACE


# ============================================================================
# 中文: 本地同步服务器创建函数（从 _local_sync_server.py 复制而来）
# English: Local sync server creation functions (copied from _local_sync_server.py)
# ============================================================================


class _PassSyncAuth(SyncAuthenticationProvider):
    """中文: 测试用的放行认证提供者 / English: Permissive auth provider for testing"""

    def get_agent_id(self, sio: Server, environ: dict) -> str:  # type: ignore[override]
        return "test-agent"

    def authenticate(self, sio: Server, agent_id: str, auth: dict | None, headers: list) -> bool:  # type: ignore[override]
        return True

    def has_admin_permission(self, sio: Server, agent_id: str, secret: str) -> bool:  # type: ignore[override]
        return True


class LocalSyncSMCPNamespace(SyncSMCPNamespace):
    """中文: 同步命名空间，继承自正式实现，仅替换认证 / English: Sync namespace with test auth"""

    def __init__(self) -> None:
        super().__init__(auth_provider=_PassSyncAuth())
        # 可选：记录操作 / Optional: record operations
        self.client_operations_record: dict[str, tuple[str, Any]] = {}

    def on_connect(self, sid: str, environ: dict, auth: dict | None = None) -> bool:  # type: ignore[override]
        ok = super().on_connect(sid, environ, auth)
        self.client_operations_record[sid] = ("connect", None)
        return ok


def create_local_sync_server() -> tuple[Server, Namespace, WSGIApp]:
    """中文: 创建同步 Socket.IO Server 并注册本地命名空间 / English: Create sync Socket.IO Server with local namespace"""
    sio = Server(
        cors_allowed_origins="*",
        ping_timeout=60,
        ping_interval=25,
        async_handlers=True,  # 如果想使用 call 方法，则必定需要将此参数设置为True / Required for call method
        always_connect=True,
    )
    ns = LocalSyncSMCPNamespace()
    sio.register_namespace(ns)
    app = WSGIApp(sio, socketio_path="/socket.io")
    return sio, ns, app


# ============================================================================
# 中文: 多进程服务器启动函数 / English: Multiprocess server startup
# ============================================================================


def _run_server_process(port: int, ready_event: multiprocessing.synchronize.Event) -> None:
    """
    中文: 在独立进程中运行服务器
    English: Run server in a separate process
    """
    try:
        sio, ns, wsgi_app = create_local_sync_server()
        # 禁用监控任务避免关闭时出错 / Disable monitoring task to avoid shutdown errors
        sio.eio.start_service_task = False

        server = make_server("127.0.0.1", port, wsgi_app, threaded=True)

        # 通知主进程服务器已准备好 / Notify main process that server is ready
        ready_event.set()

        # 运行服务器 / Run server
        server.serve_forever()
    except Exception as e:
        print(f"服务器进程错误 / Server process error: {e}")
        ready_event.set()  # 即使出错也要设置事件，避免主进程无限等待 / Set event even on error


@contextlib.contextmanager
def run_http_server() -> Iterator[tuple[str, int]]:
    """
    中文: 启动一个基于多进程的同步 Socket.IO Server（真实 HTTP 服务），返回 (host, port)。
    English: Start a multiprocess sync Socket.IO server over real HTTP, return (host, port).
    """
    # 选取随机可用端口 / pick a free port
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    host, port = sock.getsockname()
    sock.close()

    # 创建进程间通信事件 / Create inter-process communication event
    ready_event = multiprocessing.Event()

    # 启动服务器进程 / Start server process
    server_process = multiprocessing.Process(
        target=_run_server_process,
        args=(port, ready_event),
        daemon=True,
    )
    server_process.start()

    # 等待服务器准备好 / Wait for server to be ready
    if not ready_event.wait(timeout=10):
        server_process.terminate()
        server_process.join(timeout=2)
        raise RuntimeError("服务器进程启动超时 / Server process startup timeout")

    # 额外等待确保端口完全可用 / Extra wait to ensure port is fully available
    time.sleep(0.3)

    try:
        yield host, port
    finally:
        # 终止服务器进程 / Terminate server process
        if server_process.is_alive():
            server_process.terminate()
            server_process.join(timeout=3)

        # 如果进程仍然存活，强制杀死 / Force kill if still alive
        if server_process.is_alive():
            server_process.kill()
            server_process.join(timeout=1)


@pytest.fixture(scope="session")
def server_endpoint() -> Iterator[str]:
    """
    中文: 提供形如 http://127.0.0.1:PORT 的服务端地址。
    English: Provide server endpoint like http://127.0.0.1:PORT
    """
    with run_http_server() as (host, port):
        yield f"http://{host}:{port}"


@contextlib.contextmanager
def _socketio_client(url: str) -> Iterator[socketio.Client]:
    """
    中文: 创建并连接一个真实 socketio.Client，自动断开与关闭。
    English: Create and connect a real socketio.Client, auto cleanup.
    """
    client = socketio.Client()
    client.connect(
        url,
        socketio_path="/socket.io",
        namespaces=[SMCP_NAMESPACE],
        transports=["polling"],  # 仅使用轮询，避免WSGI环境的WebSocket升级失败 / force polling to avoid websocket upgrade under WSGI
        wait=True,
        wait_timeout=10,
    )
    try:
        yield client
    finally:
        with contextlib.suppress(Exception):
            client.disconnect()


@pytest.fixture()
def agent_client(server_endpoint: str) -> Iterator[socketio.Client]:
    """
    中文: 已连接到 Server 的 Agent 客户端（同步）。
    English: Connected Agent client (sync).
    """
    with _socketio_client(server_endpoint) as c:
        yield c


@pytest.fixture()
def computer_client(server_endpoint: str) -> Iterator[socketio.Client]:
    """
    中文: 已连接到 Server 的 Computer 客户端（同步）。
    English: Connected Computer client (sync).
    """
    with _socketio_client(server_endpoint) as c:
        yield c
