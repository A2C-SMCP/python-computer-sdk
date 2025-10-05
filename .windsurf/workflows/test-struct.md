---
description: 测试架构
---

1. 单元测试文件在： tests/unit_tests/ 之内
2. 集成测试文件在： tests/integration_tests/ 之内
3. 当前使用 poetry 管理环境，因此运行用例时使用 poetry 相关方法
4. 测试文件所在位置与目录和被测试文件相对于 /a2c_smcp 几乎一致
5. 运行poetry的时候注意目录需要保持在当前工作目录
6. 一些集成操作使用poe管理，定义如下：

[tool.poe.tasks]
test = "pytest tests tests/unit_tests tests/integration_tests"
test-cov = "pytest tests -m 'not e2e' --cov a2c_smcp --cov-report=term-missing --cov-fail-under=0 --cov-config=.coveragerc"
test-e2e = "pytest tests -m e2e"
lint = "ruff check --fix ."
format = "ruff format ."

---

e2e 测试

为保证命令行交互界面的运行成功，需要使用e2e测试，保证一些复杂生产交互用例的成功执行。

e2e测试用例位于： tests/e2e/ 之内

e2e 测试模式简介：

1. 使用pexpect运行真实的spawn进程。不需要使用mockeypatch，所有的e2e追求完美复现真实场景
2. computer/agent/server 也需要独立进行e2e测试。
3. computer中如果需要一些常见的可用的真实MCP Server服务器等，可以从 @tests/e2e/computer/configs 去寻找，常用配置均在此记录。多数时候你都需要对配置进行一些自定义，因此多数时候可以参考后再自己写一个可用配置，配合tmppath写入临时文件进行测试。
4. 对于需要验证真实环境中与Socket.IO连接使用的场景测试时，以Computer测试为例，在测试时，需要启动一个真实的Socket.IO服务器，基于@a2c_smcp/server模块来实现，也需要启动一个真实的AgentClient，基于 @a2c_smcp/agent 模块来实现。目前所有的模块其业务实现均是通过标准封装引入。因此可以Mock相应的业务封装来测试不同的场景。唯一需要注意的是，如果测试同步原语的代码能力，需要使用multiprocess模块来进行测试，需要记录的验证数据，你可以挑选合适的信息记录方式来实现，方便后续断言。因为GIL的存在，如果使用thread模块或者其它模式容易造成阻塞。目前有一个参考位于：tests/integration_tests/server/test_namespace_sync.py 仅作参考。

---

测试文件创建原则：

1. 单元测试与集成测试用例分别与 /tests/unit_tests 和 /tests/integration_tests 目录的相对路径保持被测试文件于 /a2c_smcp/ 的相对路径保持一致
2. 如果没有重大必要（比如原测试文件已经非常巨大，同时新的被测试特性相对独立），尽量将新用例合并至 test_{被测试文件名).py 的用例文件之中
3. 如果遇到 test_{被测试文件名}.py 非常巨大（比如超过500行），又或者需要Mock的一些特性与原Mock可能有冲突，不能在一个文件与测试周期。可以创建新测试文件，通过添加特性后缀来表达不同。