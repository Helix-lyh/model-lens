"""worldkit：由可插拔规则模块组成的推理题系统——求解、复核、门禁、渲染与冻结。

设计确认单见 docs/worldkit.md。题族（family）负责状态机与规则语义；引擎只负责枚举择支、字典序目标、
门禁和渲染。独立复核器放在 worldkit/oracles/，禁止 import 引擎与题族代码。
"""
