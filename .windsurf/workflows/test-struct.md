---
description: 测试架构
---

1. 单元测试文件在： tests/unit_tests/ 之内
2. 集成测试文件在： tests/integration_tests/ 之内
3. 当前使用 poetry 管理环境，因此运行用例时使用 poetry 相关方法
4. 测试文件所在位置与目录和被测试文件相对于 /a2c_smcp_cc 几乎一致
5. 运行poetry的时候注意目录需要保持在当前工作目录
6. 一些集成操作使用poe管理，定义如下：

[tool.poe.tasks]
test = "pytest tests"
test-cov = "pytest tests --cov a2c_smcp_cc --cov-report=term-missing --cov-fail-under=0 --cov-config=.coveragerc"
lint = "ruff check --fix ."
format = "ruff format ."

---

e2e 测试

为保证命令行交互界面的运行成功，需要使用e2e测试，保证一些复杂生产交互用例的成功执行。

