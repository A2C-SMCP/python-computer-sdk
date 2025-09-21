---
description: Computer添加动态管理MCP Server的能力
---

目前在MCP Manager的封装之中，已经添加了对于某一个MCP Server配置的 add_or_update与remove相关能力。但现在这个能力，在 Computer 中没有体现。

Computer是对MCP Manager的高级封装，现在Computer只能在初始化的时候指定全部MCP Server配置，无法动态添加，更新或者移除。你需要为Computer添加这样的能力。

同时你需要注意Computer还有一个能力是MCP Server的配置在Computer中是可以引用inputs的，这一点设计你可以参考 Computer的源码来了解，这是一个类似于VSCode的手段，相关的resolver代码你也可以一并查询并了解其设计模式。

因此在Computer中 动态添加/更新/移除的时候，需要同时利用这个能力，也就是说用户最外层的配置，或者动态使用的配置，也是支持 inputs 解析能力的。