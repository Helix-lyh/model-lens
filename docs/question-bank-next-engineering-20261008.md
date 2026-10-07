# 活跃工程题册（题库版本 20261008，10 题）

工程题的执行合同：每题实现 `def solve(events)`，按输入顺序返回等长结果；事件对象用 `op` 字段表示接口名（E-07..E-10 的夹具同时提供等价的 `type` 字段）；不得使用网络、文件、工具或子进程。题面只给生产愿望、接口、字段和默认值，以及一句 code 规则：“不同状态或错误使用不同的 `code` 和 `reason`；同一种情况使用相同的 `code`。”不公布码表，不把判定结论写进题面。

迁移价值：每题把实体、租户和事件名替换成另一种生产对象后，仍可用相同的黑盒关系观察状态隔离、幂等和载荷一致性；评分不依赖某个业务术语或内部实现。

每题隐藏评分有 20 条关系。关系成立记正分；双方都有观测但关系不成立记负分；缺字段为空缺。参考实现必须拿满 20 条关系且不触发负分。E-01..E-06 沿用 v3.3 已有题面和参考实现，只在新版本登记；E-07..E-10 为新增题。工程栏独立报告正分、负分、净分和严格通过，不与编码或推理合成。

## E-01 注册和登录（留用 v3.3）

**业务锚点与失败代价。** SaaS 后台登录服务由员工和 API 网关使用；错误的锁定或会话隔离会造成账号接管或业务中断。本题主能力为指令遵循。

**为什么保留。** v3.3 在 booster `T115945` 为 `14−6=8`，仍有状态交错区分度；没有把题面规则写成清单，也没有题外操作。

**题面全文。** 工程题 E-01：为一个 SaaS 管理后台做一套生产级别可用的注册和登录。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)，接收 JSON 兼容的事件列表，返回同长度的 JSON 兼容结果列表。事件按输入顺序处理；每个事件都有 id、op、now（整数）。时间只看事件里的 now。op 为 REGISTER、LOGIN、REQUEST。REGISTER 带 user、password，可以带 generation：不带 generation 是老用户，generation 为 2 是新用户。LOGIN 带 user、password，可以带 request_id 和 client：legacy 是老客户端，current 是新客户端，不带 client 时视为 current。REQUEST 带 session，或者带 session_ref，可以带 client。不带 client 时视为不限制。session_ref 是前面某个 LOGIN 事件的 id，表示用那次登录结果里的 session。LOGIN 成功时，结果里要有后续事件能用的 session。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 注册成功；重复注册；正确登录；未知用户与错误口令的外显一致；失败不回显口令；失败窗口锁定；窗口结束恢复；客户端匹配；客户端不匹配；两次会话不复用；请求成功；伪造会话失败；锁定期 code；恢复后 code；同一 request 重试；账号隔离；旧代际客户端登录被拒；未知事件；每个结果等长；响应不含口令。

**参考行为。** 参考实现维护用户、失败窗口、会话和 request 重放表；同一 request 重放原结果，锁定只影响对应用户，客户端限制只在声明时生效。

## E-02 支付回调接收器（留用 v3.3）

**业务锚点与失败代价。** 商户支付平台接收异步 webhook；错把坏签名、旧版本或附加费当已支付，会造成对账和发货错误。本题主能力为指令遵循。

**为什么保留。** v3.3 在 `T115945` 为 `11−9=2`，下降来自签名、版本、金额和重放同时观察，不是禁项清单。

**题面全文。** 工程题 E-02：做一个生产级别可用的支付通知接收组件，商户要能查订单付没付。事件是对象，带 op。订单由 merchant 和 order 标识。CREATE 带 amount（整数）和 fee_rule：flat 或 surcharge，不带 fee_rule 时视为 flat。CALLBACK 带 amount、state、event_id，可以带 signature 和 notice_version。state 只能是 PAID 或 REFUNDED。notice_version 不带时视为 2。GET 也是一次事件。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 有效签名入账；坏签名不入账；版本解析；旧通知处理；附加费金额；商户隔离；订单隔离；已付查询；未付查询；退款查询；重复 event_id；旧版本或坏签名不消耗 event_id；乱序不倒退；重放 code；查询载荷；重复 query；未知订单；每个结果等长；状态 code 区分；金额一致。

**参考行为。** 参考实现按商户与订单保存状态、金额和已见过的 event_id；判断顺序为订单不存在、旧版本通知、签名不符、event_id 重复、金额不符，最后才是状态迁移。旧版本或坏签名的回调不占用 event_id。

## E-03 库存预占（留用）

**业务锚点与失败代价。** 电商库存服务给订单编排器提供可用量查询和预占；错把保留池或过期批次算成可售，会造成超卖或发货缺货。本题主能力为指令遵循。

**为什么保留。** 历史 `T112527` 为 `7−4=3`，已有可观察状态交错；题面不写锁定次数或状态码，适合作为工程栏中段，不再通过增加禁项压分。

**题面全文。** 工程题 E-03：做一个生产级别可用的库存预占组件，要能查某个买家现在能买多少。事件是对象，带 op，并带 tenant 和 sku。STOCK 带 quantity、pool、batch，可以带 expire_at。pool 是 open 或 holdback。batch 是 old 或 new。RESERVE 带 quantity、reservation_id、buyer、now。buyer 是 new 或 returning。GET 带 buyer 和 now，结果里用 available 表示这个买家此刻能买的件数。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 库存登记；可用量；预占成功；同一 reservation 再预占时可用量不变、code 与首次不同；数量不足原子失败；负数拒绝；零数量后再预占；跨租户隔离；跨 SKU 隔离；多次预占叠加；保留池对新客不可见；保留池对回头客可见；过期旧批次不计入可用量；新批次仍可用；新客不能占用保留池；回头客可以占用保留池；过期与不足的 code 区分；保留池余量；STOCK 与 RESERVE 的 code 区分；结果等长。

**参考行为。** 按租户和 SKU 保存批次，每个批次记池、批次类型、数量和到期时刻；可用量只累计对该买家可见的批次。预占按批次顺序扣减，`reservation_id` 首次结果固定；数量不是正整数时记拒绝，可用量不足时再区分「过期」与「不足」两种 code。

## E-04 文档抹除和审计留存（留用）

**业务锚点与失败代价。** 隐私服务处理用户删除请求，同时给财务和审计留下必要记录；删除正文失败会产生合规风险，删除账务会破坏对账。本题主能力为指令遵循。

**为什么保留。** 历史 `T112527` 为 `12−8=4`，覆盖租户边界、删除与留存两条不同观测；题面不声称具体存储实现。

**题面全文。** 工程题 E-04：做一个生产级别可用的文档归档组件，文档可以写入和抹掉，财务要能核对入账。事件是对象，带 op，并带 tenant 和 doc_id。PUT 带 content，可以带 amount 和 retention。retention 是 normal 或 hold，不带时视为 normal。ERASE 带 request_id。READ 带 role：user 或 auditor。结果里可以带 amount。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 评分器里有 20 条关系，题面不列这些关系。和旧稿不同的三件事：金额是累加不是覆盖；同一个 request 再次抹除时 code 与首次不同；结果等长不是单独的一条得分。

**参考行为。** 参考实现把正文和审计金额分开。PUT 把正数 amount 累加进账，不是覆盖成最后一次的金额。ERASE 后正文不可读，金额仍在。同一个 request_id 再抹一次，code 是 duplicate，不是第一次的 erased。auditor 读到的是累加后的金额。

## E-05 异步任务调度（留用）

**业务锚点与失败代价。** 多租户 worker 调度器处理依赖、重试和取消；错误会重复副作用、把过期回报当成成功，或无视依赖提前执行。本题主能力为指令遵循。

**为什么保留。** 历史 `T112527` 为 `11−9=2`；它能观察依赖、迟到回报和配额的组合，不靠把日志拉长。

**题面全文。** 工程题 E-05：做一个生产级别可用的多租户异步任务组件，工人会回报执行结果。事件是对象，带 op、tenant 和 task_id。SUBMIT 可以带 depends_on，值是同一租户的另一个 task_id。UPDATE 带 action：start、complete、fail 或 cancel，并带 protocol 和 attempt。protocol 不带时视为 2。GET 也是一次事件。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 提交后进入排队；领取后进入执行；重复 GET 稳定；重复回报；取消后可查询；依赖未完成不能领取；依赖完成后可领取；过期回报不改状态；失败后可重新领取；连续失败达上限后拒绝领取；失败任务不算完成；完成后再回报无效；取消后回报；未知任务；忙碌与拒绝的 code 区分；同种失败的 code 一致；重试后重新开始；SUBMIT 与 GET 的 code 区分；跨租户隔离；结果等长。

**参考行为。** 参考实现为每个任务保存状态、失败次数和当前 attempt。领取除了依赖，还看任务是否已在执行、是否已取消或已成功、失败次数是否已到 4、attempt 是否变化。连续失败 4 次后再领取会拒绝。回报必须带当前 attempt 才算有效。取消只作用于排队中或执行中的任务。

## E-06 配置发布和回滚（留用）

**业务锚点与失败代价。** 发布服务让值班工程师在多环境审批、灰度和回滚之间切换；错误发布会让生产环境读取未审批配置。本题主能力为指令遵循。

**为什么保留。** v3.3 在 `T115945` 为 `12−8=4`；审批、环境、字符串布尔值和回滚后的重新发布能产生真实负向观察。题外 `APPROVE/ROLLBACK` 已从计分场景清除。

**题面全文。** 工程题 E-06：做一个生产级别可用的配置发布组件，配置按环境发布，并且可以回到旧版本。事件是对象，带 op、env 和 key。PROPOSE 带 version、value，可以带 request_id、min_client 和 approved。version、min_client 是整数，min_client 不带时视为 1。PUBLISH 带 version，也可以带 rollback_to。READ 可以带 client（整数），不带时视为不限制。读到已发布的内容时，把那份内容放在 value 里。每个事件的结果都是对象，里面要有 code 和 reason。不同的状态、不同的错误使用不同的 code 和 reason；同一种情况使用相同的 code。评测会把你的代码写入 solution.py，并执行 from solution import solve。必须提供 def solve(events)。它接收 JSON 兼容的事件列表，按输入顺序处理，返回同样长度的 JSON 兼容结果列表。不得使用网络、文件、工具或子进程。不要输出解释，只输出一个 python 代码围栏。

**可机械判分的 20 点。** 提案；版本重复；审批真值；审批假值；未审批发布；审批发布；环境隔离；回滚；回滚后读；回滚后重新发布；request_id 隔离；字符串 false；省略 approved；重复 publish；未知版本；READ 缺失；READ 载荷；code 区分；结果等长；状态重放。

**参考行为。** 参考实现按环境保存版本、审批和当前指针。`approved` 只有布尔 true 可以发布；省略和显式 false 都不能发布，两者的 code 不必相同。回滚不删除提案，也不清除已通过的审批，回滚后可以直接再次发布该版本。

## E-07 冷链出库和温度窗口

**业务锚点与失败代价。** 冷链仓库根据温度观测决定订单是否可出库；错误放行会导致整批货损和召回。本题主能力为指令遵循。

**为什么更难。** 同一次出库请求同时受批次状态、温度窗口和订单幂等影响；读接口暴露的只是行为结果，模型不能靠返回统一错误蒙混。

**题面全文。** 做一个生产级别可用的冷链出库闸门。事件为 `BATCH {batch,temp_min,temp_max}`、`SHIP {batch,order,qty,request_id,temp}`、`HOLD {batch,request_id}`、`READ {batch}`。qty 为正整数，temp 为整数；`temp` 缺省时使用最近一次 BATCH 的温度。返回 `code`、`reason`，成功 SHIP 可带 `available`。同一情况使用相同的 `code` 和 `reason`，不同状态或错误使用不同的 `code` 和 `reason`。实现 `def solve(events)`，按顺序处理并返回等长结果；不得使用网络、文件、工具或子进程。

**可机械判分的 20 点。** 批次登记；温度上下界；缺省温度；数量不足；SHIP 扣减；同 order 重试；request 重试；HOLD；HOLD 后 SHIP；HOLD 后 READ；未知批次；负数；跨批次隔离；温度变化；失败不扣库存；成功 available；code 区分；结果等长；重复 BATCH；状态一致。

**参考行为。** BATCH 更新批次温度但不重置库存；HOLD 只冻结当前可用量，SHIP 只能使用未被 HOLD 的数量；同一 request 返回首次结果。

## E-08 退款争议和证据窗口

**业务锚点与失败代价。** 支付争议服务根据原交易、证据上传和窗口状态决定是否提交；错过证据窗口会造成不可逆拒付损失。本题主能力为指令遵循。

**为什么更难。** 原交易和争议状态分开，证据窗口按事件时间关闭；同一 evidence_id 的重试必须保持结果，不能把任意错误都映射成一个拒绝。

**题面全文。** 做一个生产级别可用的退款争议服务。事件为 `CASE {case,order,deadline}`、`EVIDENCE {case,evidence_id,kind,at,request_id}`、`SUBMIT {case,at,request_id}`、`READ {case}`。kind 缺省为 `receipt`。返回 `code`、`reason`，READ 可带 `available` 表示尚未提交的证据数。同一情况使用相同的 `code` 和 `reason`，不同状态或错误使用不同的 `code` 和 `reason`。实现 `def solve(events)`，按顺序处理并返回等长结果；不得使用网络、文件、工具或子进程。

**可机械判分的 20 点。** CASE 登记；重复 CASE；证据唯一；证据类型；deadline 边界；迟到证据；提交前证据计数；提交成功；提交后证据；重复提交；未知 case；request 重试；跨 case 隔离；缺省 kind；失败占 request；READ 状态；READ available；code 区分；结果等长；状态不可倒退。

**参考行为。** 证据在 `at<deadline` 时可接受，提交在 `at<=deadline` 时可执行；提交后 case CLOSED，迟到或重复证据不改变计数。

## E-09 设备租约与维护切换

**业务锚点与失败代价。** IoT 平台把设备租约交给边缘 worker；错误续租会让维护中的设备继续接收命令。本题主能力为指令遵循。

**为什么更难。** 租约状态、维护状态和 worker 绑定同时变化；续租请求可能来自旧 worker，且过期清理和重放必须可观察。

**题面全文。** 做一个生产级别可用的设备租约服务。事件为 `CLAIM {device,worker,ttl,request_id,at}`、`RENEW {device,worker,ttl,request_id,at}`、`MAINTAIN {device,enabled,request_id,at}`、`READ {device,at}`。ttl 为正整数，enabled 缺省为 true。返回 `code`、`reason`，成功 CLAIM/RENEW 可带 `available` 表示剩余秒数。 同一情况使用相同的 `code` 和 `reason`，不同状态或错误使用不同的 `code` 和 `reason`。实现 `def solve(events)`，按顺序处理并返回等长结果；不得使用网络、文件、工具或子进程。

**可机械判分的 20 点。** 首次 claim；租约到期边界；同 worker renew；旧 worker renew；维护开启；维护关闭；维护期 claim；维护期 renew；TTL 计算；重复 request；失败占 request；设备隔离；worker 隔离；READ 有效；READ 过期；READ 维护；available；code 区分；结果等长；状态恢复。

**参考行为。** 每次事件先按 at 清理过期租约。维护开启时不能新认领或续租，原租约的到期时间还在。关闭维护后原租约如果没过期，仍然有效，不要求重新 CLAIM。

## E-10 账单草稿和税率版本

**业务锚点与失败代价。** 财务系统在账单出具前累积项目并按税率版本计算总额；错误混用税率会造成发票和收入确认错误。本题主能力为指令遵循。

**为什么更难。** 草稿、出具和作废是不同状态；税率在出具时冻结，之后税率更新只影响新草稿，重复项目和重放要分别可见。

**题面全文。** 做一个生产级别可用的账单草稿服务。事件为 `RATE {region,version,bps}`、`DRAFT {invoice,item,region,net,request_id}`、`ISSUE {invoice,request_id}`、`VOID {invoice,request_id}`、`READ {invoice}`。bps 为非负整数，region 缺省为 `default`，net 为正整数。返回 `code`、`reason`，ISSUE 可带 `tax`、`gross`。同一情况使用相同的 `code` 和 `reason`，不同状态或错误使用不同的 `code` 和 `reason`。实现 `def solve(events)`，按顺序处理并返回等长结果；不得使用网络、文件、工具或子进程。

**可机械判分的 20 点。** 税率登记；版本选择；区域默认；草稿累积；重复 item；出具税额；向下取整；出具冻结税率；出具后 RATE 不变金额；重复 ISSUE；VOID；VOID 后 READ；VOID 后 ISSUE；未知 invoice；request 重试；失败占 request；READ 载荷；code 区分；结果等长；多区域隔离。

**参考行为。** 草稿保存每个 item。ISSUE 取该 region 已登记 bps 的最大值，不是版本号最大的那条，并按这个税率冻结。税额为 `floor(net*bps/10000)` 的逐项和。VOID 不删除草稿，只改变状态。

## 工程栏自检

E-01..E-06 有旧实测证据，保留理由分别写在题目中；E-07..E-10 只提出行为愿望，没有预先公布判定码表。E-01..E-06 是三个操作，E-07..E-10 的操作以各题题面全文为准。隐藏用例只能调用题面列出的操作。参考实现须在本地先验证 20−0，再用上一轮答卷重放；新题未跑模型前不声称能把工程栏调到 30%--40%。
