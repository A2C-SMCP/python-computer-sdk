---
description: 命令行交互设计方案
---

当前项目使用  typer + rich + prompt_toolkit 开发命令行交互逻辑

我们主要将对Computer的配置，启停管理与状态查询暴露到命令行Cli交互中。而对于Computer的驱动与控制，则交由SocketIO通道，由远端的Agent来负责。

因此基于这个大前提，命令行交互设计方案主要解决以下问题：

1. Computer的启停管理。运行后启动，输入exit/quit或者Ctrl+C停止。停止的时候需要注意调用Computer相关方法，对资源进行清理。
2. Computer的配置管理。启动后，用户中可以通过命令来动态添加/移除/修改，需要注意，一旦配置发生变更，需要触发：server:update_mcp_config 事件，通知远端，让他们各自去处理相应的变化。
3. 过程中一些数据的查询，比如查询当前的工具列表，查询当前连接的MCP Config等等，也就是一些查询型的动作，也可以通过命令行暴露出来，方便调试的时候获取上下文数据
4. 完成 input resolve，目前支持 ${input:xxx} 来定义渲染过程中可用的动态变量，这些变量比如PromptStr是需要通过CLI引导用户录入的，在需要的时候，CLI的使用就是支持随时可以完成渲染。