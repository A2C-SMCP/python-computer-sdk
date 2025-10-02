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

