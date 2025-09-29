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

目前我们的主要任务是将Server代码从之前的业务代码中抽取出来，在这个 a2c-smcp 项目中进行独立封装。当下的难点如下：

1. 业务代码中有一些自己的实现，比如认证，未来每个使用方其认证方式肯定是自己实现，因此我们a2c-smcp关于这种问题的处理，我的思路是留下 @abstractmethod 让使用者自己实现，如果你有更好的方案可以推荐给我，我们来应用。
2. 在业务代码中维护一个标准协议往往有滞后性，这也是为什么我们需要将协议独立并维护SDK的原因，因此我给你的业务参考代码中可能相较于当前项目中的 @smcp.py 中的定义会有些滞后，但应该以当前项目中的 @smcp.py 实际协议为准，如果有拿不准的可以问我。

Server的逻辑比Computer要简单很多，但也要保持良好的代码组织习惯。目前Server的封装是独立一个Namespace进行开发，使用者可以将这个Namespace挂载到其实际的Socket.IO服务上，目前封装不提供完整的Socket.IO服务器，因为服务器多数特性与业务相关，我们因此不做要求，我们封装最合适的逻辑单元就是一个Namespace。但在测试过程中可能需要Mock一个服务器。

---