---
description: 开发架构说明
---

本SDK主要是实现 A2C-SMCP 协议。

A2C-SMCP协议主要有三部分：Agent-Server-Computer。三者通过Socket.IO协议实现实时通信。协议的概况在 @docs/index.md （因为文档较长，如无必要不要读取）

Computer主要负责MCP工具的生命周期维护，调度管理等工作。

SMCP协议数据结构与事件的定义，主要集中在：

@a2c_smcp/smpc.py 之中。其定义方式主要使用 TypedDict进行定义。
@a2c_smcp/computer/mcp_clients/model.py 之中。其定义主要是对上者的Pydantic实现，因为在Python进程内，使用Pydantic会有更好的类型管理与数据结构校验的能力。

因此SMCP协议以 @a2c_smcp/smpc.py 为主，以 @a2c_smcp/computer/mcp_clients/model.py 为辅。如果协议有调整与修改，二者均需要进行修改。

如果事件发生变动，需要注意有以下位置需要同步这个变动：

1. Socket.IO注册的事件响应函数，按目前的其它响应函数命令规范，需要进行调整。
2. 测试文件中 Socket.IO 服务器的Mock。因为其名称在 trigger_event 中进行转义，也就是事件响应函数与事件名称有关系，需要同步修改。
3. （未来）A2C-SMCP 信令服务器相关响应函数与测试用例
4. （未来）A2C-SMCP Agent相关响应函数与测试用例

---

当前封装中 @a2c_smcp/computer/mcp_clients/base_client.py 是 MCP Client封装基类，这里面有个重点，因为我们使用了transitions库进行状态管理，因此外界不好代码补全，因此我添加了 @a2c_smcp/computer/mcp_clients/base_client.pyi 类型定义文件。如果是对这个基类有能力上的变动，需要记住 ** 同步修改 pyi 文件**