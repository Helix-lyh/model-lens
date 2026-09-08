# 题库 v2.1 设计与参考答案

本版改写24道非编码题：12道真实标准知识、8道指令遵循（architecture 4、reasoning 4）、4道多步推理/架构。保留54 raw、78展开实例、四域及原难度矩阵；coding及既有新增hard06–09不动。8道指令题是同一协议的不同实例，测条件分支与严格输出，但共享模板带来相关性，不能视作八个独立能力证据。后续应在固定版本之外建设异构协议候选集。

知识题选择冷门稳定RFC，不把虚构封闭规则当作知识；题目不提供待考事实。出处已通过RFC Editor页面逐项核实：1982§3、2308§4–5、3597§4–5、2782字段定义、5952§4、4648§3.5/5/6/10。当前知识覆盖偏DNS/编码标准，并非完整世界知识抽样；领域扩展属于后续校准。

内容题允许JSON键顺序改变和单一围栏；类型严格，数组顺序和规范化字符串有实际含义。指令题明确要求原始单行紧凑JSON，grader.strict_response=true，评分器需原样传递；fixture只使用沙箱现有复制的_structured及标准库，不导入仓库包。满点才通过，各字段给部分分；schema或协议失败不可满分。模型单题单次、无工具；机械评分，不调用被测模型或LLM裁判。

参考答案和错误样例是固定版本资产；修改题面、fixture或等价规则后必须升版本，不可与旧分数直接比较。以下错误样例将首字段置null（破坏关键结果或分支）；自动测试另逐字段变异、类型混淆、重复键、额外键及格式攻击。设计不保证deepseek-flash降到30–40%，该目标需实测校准。

## knowledge-easy-01

最长零串平局必须选首个，十六进制小写。

参考答案：
```json
{"address":"2001:db8::1:0:0:1"}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"address":null}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc5952

## knowledge-medium-01

服务不可用与目标禁止别名两个独立事实。

参考答案：
```json
{"service":"UNAVAILABLE","alias_allowed":false}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"service":null,"alias_allowed":false}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc2782

## knowledge-hard-01

回绕与半空间不可比较，不能用普通整数排序。

参考答案：
```json
{"relations":["NEWER","OLDER","UNDEFINED","EQUAL"],"add_250_10":4}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"relations":null,"add_250_10":4}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc1982

## knowledge-hard-02

负TTL取最小再老化，NXDOMAIN不按QTYPE隔离。

参考答案：
```json
{"ttl":240,"nxdomain_key":["QNAME","QCLASS"],"nodata_key":["QNAME","QTYPE","QCLASS"]}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"ttl":null,"nxdomain_key":["QNAME","QCLASS"],"nodata_key":["QNAME","QTYPE","QCLASS"]}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc2308

## knowledge-hard-03

区分字节长度与hex字符长度及未知类型压缩禁令。

参考答案：
```json
{"type":"TYPE65400","rdata":"\\# 3 00ff10","compress_names":false}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"type":null,"rdata":"\\# 3 00ff10","compress_names":false}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc3597

## knowledge-hard-04

两种字母表与未使用位，不混同base64与base64url。

参考答案：
```json
{"base64url":"_w==","base32":"74======","pad_bits_zero":true}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"base64url":null,"base32":"74======","pad_bits_zero":true}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc4648

## knowledge-hard-05

孤立零不压缩，等长首段压缩，全零特例。

参考答案：
```json
{"addresses":["2001:db8:0:1:2:3:4:5","2001::2:0:0:3:4","::"]}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"addresses":null}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc5952

## knowledge-extreme-01

最大允许增量与半空间边界不能混为一谈。

参考答案：
```json
{"after_first":4,"after_second":32771,"third_defined":false,"second_relation":"NEWER"}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"after_first":null,"after_second":32771,"third_defined":false,"second_relation":"NEWER"}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc1982

## knowledge-extreme-02

负缓存跨类型差异与独立老化。

参考答案：
```json
{"x_hit":true,"y_hit":false,"x_remaining":30,"y_a_remaining":40}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"x_hit":null,"y_hit":false,"x_remaining":30,"y_a_remaining":40}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc2308

## knowledge-extreme-03

零权重不等于从候选组删除，优先级高于权重。

参考答案：
```json
{"first":["b","c"],"next":["a"],"weight_scope":"SAME_PRIORITY","target_alias":"FORBIDDEN"}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"first":null,"next":["a"],"weight_scope":"SAME_PRIORITY","target_alias":"FORBIDDEN"}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc2782

## knowledge-extreme-04

标准Base32尾组与填充；排除hex变体。

参考答案：
```json
{"encodings":["MY======","MZXQ====","MZXW6==="],"alphabet_last":"7","bits_per_symbol":5}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"encodings":null,"alphabet_last":"7","bits_per_symbol":5}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc4648

## knowledge-extreme-05

未知RR空数据与长度单位，不能把hex长度当字节数。

参考答案：
```json
{"lengths":[0,4],"hex_digits":[0,8],"empty_valid":true,"type_731":"TYPE731"}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"lengths":null,"hex_digits":[0,8],"empty_valid":true,"type_731":"TYPE731"}`。不通过，因为关键字段为null。

出处：https://www.rfc-editor.org/rfc/rfc3597

## architecture-hard-01

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["c","a"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["c","a"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}`。不通过，因为关键字段为null。

## architecture-hard-02

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["z","x"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":1}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["z","x"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":1}`。不通过，因为关键字段为null。

## architecture-hard-03

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["q"],"trace":["DENY","TAKE","DUP","LIMIT"],"remaining":4}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["q"],"trace":["DENY","TAKE","DUP","LIMIT"],"remaining":4}`。不通过，因为关键字段为null。

## architecture-hard-04

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"IMPOSSIBLE","conflict":["R0","R9"]}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"conflict":["R0","R9"]}`。不通过，因为关键字段为null。

## reasoning-hard-01

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["o","m"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":0}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["o","m"],"trace":["TAKE","LIMIT","TAKE","DUP"],"remaining":0}`。不通过，因为关键字段为null。

## reasoning-hard-02

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["w","u"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["w","u"],"trace":["TAKE","DENY","TAKE","DUP"],"remaining":0}`。不通过，因为关键字段为null。

## reasoning-hard-03

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"IMPOSSIBLE","conflict":["R0","R9"]}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"conflict":["R0","R9"]}`。不通过，因为关键字段为null。

## reasoning-hard-04

优先级、首次拒绝占号、逆序投影、引文隔离及不可满足分支。

参考答案：
```json
{"status":"OK","kept":["x","z"],"trace":["TAKE","TAKE","LIMIT","DUP"],"remaining":1}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。原始响应须为单行紧凑JSON，键顺序如下，无首尾空白或围栏。

错误样例：`{"status":null,"kept":["x","z"],"trace":["TAKE","TAKE","LIMIT","DUP"],"remaining":1}`。不通过，因为关键字段为null。

## architecture-extreme-01

拒绝占号、部分冲正与后续余额相互作用。

参考答案：
```json
{"actions":["APPLY","FUNDS","DUP","APPLY","APPLY","REFUND_LIMIT","APPLY"],"balance":7,"refundable_a":9,"seen":["a","b","c","d","e","f"]}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"actions":null,"balance":7,"refundable_a":9,"seen":["a","b","c","d","e","f"]}`。不通过，因为关键字段为null。

## architecture-extreme-03

fencing与CAS先后顺序及失败不得抬高token。

参考答案：
```json
{"actions":["ACCEPT","STALE","CONFLICT","ACCEPT","ACCEPT"],"token":10,"version":6,"value":50}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"actions":null,"token":10,"version":6,"value":50}`。不通过，因为关键字段为null。

## reasoning-extreme-01

依赖、互斥和约束删除后的真实最优值变化。

参考答案：
```json
{"base_indices":[1,3,4],"base_value":18,"changed_indices":[0,2],"changed_value":19,"delta":1}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"base_indices":null,"base_value":18,"changed_indices":[0,2],"changed_value":19,"delta":1}`。不通过，因为关键字段为null。

## reasoning-extreme-05

等长路径计数与删边后的路径重排。

参考答案：
```json
{"path":["A","B","D"],"cost":5,"count":5,"changed_path":["A","B","E","D"],"changed_cost":5,"changed_count":3}
```

等价规则：JSON 对象键顺序不计；数组顺序、类型及字符串精确；内容题可单一围栏。

错误样例：`{"path":null,"cost":5,"count":5,"changed_path":["A","B","E","D"],"changed_cost":5,"changed_count":3}`。不通过，因为关键字段为null。

