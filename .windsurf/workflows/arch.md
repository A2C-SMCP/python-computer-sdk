---
description: 开发架构说明
---

本SDK主要是实现 A2C-SMCP 协议。

A2C-SMCP协议主要有三部分：Agent-Server-Computer。三者通过Socket.IO协议实现实时通信。协议的概况在 @docs/index.md （因为文档较长，如无必要不要读取）

---

Computer主要负责MCP工具的生命周期维护，调度管理等工作。其代码封装在 @a2c_smcp/computer 之下

SMCP协议数据结构与事件的定义，主要集中在：

@a2c_smcp/smpc.py 之中。其定义方式主要使用 TypedDict进行定义。
@a2c_smcp/computer/mcp_clients/model.py 之中。其定义主要是对上者的Pydantic实现，因为在Python进程内，使用Pydantic会有更好的类型管理与数据结构校验的能力。

因此SMCP协议以 @a2c_smcp/smpc.py 为主，以 @a2c_smcp/computer/mcp_clients/model.py 为辅。如果协议有调整与修改，二者均需要进行修改。

如果事件发生变动，需要注意有以下位置需要同步这个变动：

1. Socket.IO注册的事件响应函数，按目前的其它响应函数命令规范，需要进行调整。
2. 测试文件中 Socket.IO 服务器的Mock。因为其名称在 trigger_event 中进行转义，也就是事件响应函数与事件名称有关系，需要同步修改。
3. （未来）A2C-SMCP 信令服务器相关响应函数与测试用例
4. （未来）A2C-SMCP Agent相关响应函数与测试用例

当前封装中 @a2c_smcp/computer/mcp_clients/base_client.py 是 MCP Client封装基类，这里面有个重点，因为我们使用了transitions库进行状态管理，因此外界不好代码补全，因此我添加了 @a2c_smcp/computer/mcp_clients/base_client.pyi 类型定义文件。如果是对这个基类有能力上的变动，需要记住 ** 同步修改 pyi 文件**

---

Server主要负责中央信令服务器，负责维护Computer/Agent元数据信息，信号传输转发消息，或者将收到的一些消息转换为Notification广播出去，不同的动作其处理方式不一，大概就这三种。其主要代码在：@a2c_smcp/server 目录下

1. 认证系统：创建了AuthenticationProvider抽象基类和DefaultAuthenticationProvider默认实现
2. 基础架构：实现了BaseNamespace抽象基类，提供通用连接管理和认证功能
3. SMCP Namespace：完整实现了SMCPNamespace，包含所有SMCP协议事件处理方法
4. 类型定义：创建了完整的类型系统，包括Session类型和工具函数
5. 工具函数：实现了房间管理相关的工具函数
6. 测试用例：创建了完整的测试用例，展示了使用方法
7. 文档：在docs/server.md中添加了详细的使用文档

文件结构：
a2c_smcp/server/auth.py - 认证系统
a2c_smcp/server/base.py - 基础Namespace
a2c_smcp/server/namespace.py - SMCP协议实现
a2c_smcp/server/types.py - 类型定义
a2c_smcp/server/utils.py - 工具函数
tests/unit_tests/server/ - 测试用例
docs/server.md - 使用文档

需要注意，关于 @a2c_smcp/server 的封装，我们提供了同步原语与异步原语两种模式，后续所有的业务需求改动与变动，均需要同步体现在同步与异步版本之中。

---

Agent模块主要也是一个Socket.IO Client的封装。与Server类似，也提供同步+异步两种模式的封装。同时因为当前项目Agent封装不是重点，因此与Server一样，仅预留需要提供的Agent能力接口即可，具体实现由使用方来进行实现。

当前我们Agent Client在业务系统中做了实现，我们需要将这些实现从业务系统中抽象出来，统一放到当前项目内 (@a2c_smcp/agent) 管理。