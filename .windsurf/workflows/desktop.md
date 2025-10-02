---
description: 桌面模式开发
---

屏幕设计需要统一优化并升级协议

添加Config中的屏幕能力，默认每个屏幕由MCP Server的特定资源表达

MCP Resources需要满足以下协议

* window:// 协议。目前版本仅支持Resources-ListResources直接列举出来的资源，并不支持TemplateResource模式。URI定义在：@a2c_smcp/utils/window_uri.py 

* * host为mcp唯一标识，由mcp自定义，需要保证不与其他mcp重复，建议使用域名格式

路径可以有多个，也就是同一个MCP服务可以暴露多个窗口，但是桌面系统是否会渲染取决于桌面系统的逻辑，这一点MCP开发者无法干预，就比如桌面系统屏幕关闭了，无论MCP想渲染什么，都无法显示，因此开发者需要做好准备就是window并不能保证一定暴露给开发者。

* 查询参数信息如下

    * priority 0-100 数字越大优先级越高，仅仅在自己内部有多个window时，自己与自己比较时才会生效，也就是这个优先级不会侵占别的mcp工具的内容，因此不用刻意调大。priority会影响以及window显示布局，因为大模型输入是一个文本流，因此我们按照优先级越高越靠上的原则来布局，但注意，因为大模型注意力模型的特点，并不是越靠上一定越好，需要根据目前的需求与prompt系统全局考虑。

    * fullscreen bool 是否是全屏模式，如果是全屏模式。则如果Agent调用了此MCP Server提供的工具后，Computer Desktop会尽可能地完整渲染fullscreen指定的window。如果有多个fullscreeen，则仅第一个生效。

---

a2c-smcp 中 Desktop 本质上是按一定规则将各MCP Server提供的符合window_uri的Resources进行整合，形成一个或者多个Desktop组合，其现实产品类似，可以将MCP Server理解我们电脑上安装的软件，软件可以提供自己的窗口，a2c-smcp/computer通过将窗口渲染到自己的Desktop上，通过Desktop暴露给用户。

在目前的Desktop系统中分工如下：

1. 最内层的BaseClient (StdioClient/SSEClient/StreamableClient) 级别，负责按window_uri过滤并提供MCP Server提供的窗口信息。同时注册订阅（目前业务逻辑前提是MCP Server必须开启订阅）
2. 中间层 MCPServerManager 级别，负责管理当前众多Server提供的所有Window信息，管理元数据，比如某个Window归属在哪个server下，因为未来对Windows进行组织（比如排列或者压缩内容时）是需要使用这些元数据的，因此在由最外层触发获取 windows 信息的时候，除了调用Client.list_windows之外，还要维护元数据
3. 最外层 Computer 级别，负责响应远端Agent/外部的调用，从Manager中拿到windows与元数据信息后，结合自身操作历史，进行一些整合与优化操作，目前版本原则如下：
    a. 因为获取到的windows比较多，而且可能来自多个MCP Server