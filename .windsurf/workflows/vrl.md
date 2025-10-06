---
description: 基于VRL的ToolCallRet Refromat方案
---

现在A2C协议是为了方便Agent-Computer之间的通信。Computer的能力来源是MCP Server，集成MCP Server有很多好处，比如说直接使用Anthropic提供的MCP SDKs，能降低我们自研SDK的成本与压力，尽快上线；同时方便能力提供者，使其可以做到一处开发，多处使用。但这样的方案有一个难点需要攻克：

** 因为开发者开发MCP Server是为了提供自身的能力给Agent，因此其工具返回的数据格式往往是多样化的，MCP Server SDK要求仅仅约束了最外层的结构与一些元数据，但对于其内部Tool Call真实返回的数据往往无能为力，这一点在MCP协议设计上它也没有强制要求的必要，因此业界一直如此研发。**

但Agent使用这些工具的时候有一个难点，就是Agent必须提前知道工具的返回结构，这点利用MCP协议可以正常获取，同时因为Agent有其“智能”特性，可以动态提取结果并使用。可如果我们还想在界面中渲染工具返回这就变得非常困难了，因为界面渲染的结构与页面元素是确定的。很多时候因为字段名称不同等等细节问题导致提供并渲染数据时非常困难，比如要渲染一个结果列表，是list[str]，但是其key值，有的MCP工具是 "items"，另一个工具是 "itemArray"，这就导致了不同的MCP Server需要做不同的适配，如果这个适配工具放到前端工程中，无疑会耦合发布流程。

因此我们希望以一种更合理的方案来实现，起初我们设计了如下字段：

```python
class ToolMeta(TypedDict, total=False):
    auto_apply: NotRequired[bool | None]
    # 不同MCP工具返回值并不统一，虽然其满足MCP标准的返回格式，但具体的原始内容命名仍然无法避免出现不一致的情况。通过object_mapper可以方便
    # 前端对其进行转换，以使用标准组件渲染解析。
    ret_object_mapper: NotRequired[dict | None]
    # 工具别名，与 model.ToolMeta.alias 对齐，用于解决不同 Server 下工具重名冲突
    # Tool alias, align with model.ToolMeta.alias, used to resolve name conflicts across servers
    alias: NotRequired[str | None]
```

通过开源的一个前端库 object_mapper 配合 ret_object_mapper 定义进行解耦。这能一定程度上解决数据结构与Key值离散带来的问题，但这无法解决一些诸如“简单运算”，“时间转换”等常见的数据处理的需求。

在生产部署过程中，我们使用Vector进行日志采集，其中VRL的设计非常吸引我，它基于Rust，非常快速，同时又是开源的，可惜它没有提供Python SDK，但通过阅读源码，我发现它提供了一个JS版本的SDK，我大胆尝试使用PyO3，使用相似的技术原理将VRL提供了一个Python SDK，目前已经发布至PyPi

---

# vrl-python
VRL Python SDK Project

基于PyO3封装的Vector Remap Language (VRL) Python SDK

## Python 开发者快速使用指南 / Quick Start for Python Developers

> 包名（PyPI）：`vrl-python` ；导入模块：`vrl_python`

### 安装 / Install

```bash
# 使用 pip（推荐） / Use pip (recommended)
pip install vrl-python

# 使用 uv / Use uv
uv add vrl-python

# 使用 Poetry / Use Poetry
poetry add vrl-python
```

> 运行环境 / Requirements：Python >= 3.8

### 快速开始 / Quick Start

```python
# 中文：从 vrl_python 导入 VRLRuntime，并运行一个最小示例
# English: Import VRLRuntime from vrl_python and run a minimal example
from vrl_python import VRLRuntime

runtime = VRLRuntime()  # 中文：使用默认UTC；English: uses UTC by default

program = ".field = \"value\""  # 中文：设置字段；English: set a field
event = {}  # 中文：输入事件；English: input event

result = runtime.execute(program, event)
print(result.processed_event)  # {'field': 'value'}
```

### 一次性执行（便捷方法） / One-shot execution (convenience)

```python
# 中文：无需先创建实例，直接编译+执行
# English: compile+execute in one call without creating an instance
from vrl_python import VRLRuntime

result = VRLRuntime.run('.greeting = "hello"', {})
print(result.processed_event)  # {'greeting': 'hello'}
```

### 语法检查 / Syntax Check

```python
# 中文：仅检查语法，不执行
# English: check syntax only, no execution
from vrl_python import VRLRuntime

diagnostic = VRLRuntime.check_syntax('.parsed = parse_json(.message)')
if diagnostic is None:
    print('✅ 语法正确 / Syntax OK')
else:
    print('❌ 发现错误 / Errors found:', diagnostic.messages)
    print(diagnostic.formatted_message)
```

---

✅ pyproject.toml - 添加 vrl-python 依赖
✅ a2c_smcp/smcp.py - 添加 vrl 字段定义（TypedDict）
✅ a2c_smcp/computer/mcp_clients/model.py - 添加 vrl 字段、验证器和常量
✅ a2c_smcp/computer/mcp_clients/manager.py - 集成 VRL 转换逻辑
