# 评测报告 · eval-20261018-20261016T231849-hard · 版本 20261018 · 计分 20261018.s1

每个渠道单独成节，不跨模型合计。主口径是固定分母：每次作答按满分进分母，截断、超时、错误、缺失都记 0 分；“已判百分比”是辅助口径，只除以已判题目的满分。编码、工程、推理分开，没有跨栏总分。
阶段：hard。语言：python,go,typescript。采样 3 次。

## 渠道 cat-jam-free

| 题库 | 版本 | 作答 | 已判 | 通过 | 截断 | 固定分母平均分 | 已判平均分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| business-reasoning | 20261018 | 30 | 30 | 21 | 0 | 75.7 | 75.7 |

### 三栏汇总

| 栏目 | 已判/作答 | 累计得分 | 固定满分 | 得分百分比（固定分母） | 已判满分 | 已判百分比（辅助） | 截断 | 超时 | 其他未判 | 严格通过 | pass@1 | pass@k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| reasoning | 30/30 | 454 | 600 | 75.7% | 600 | 75.7% | 0 | 0 | 0 | 21 | 0.7 | 0.8 (k=3) |

### 分组累计

| 栏目 | 题库 | 版本 | 分组 | 得分 | 满分 | 百分比 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| reasoning | business-reasoning | 20261018 | arrive | 24 | 24 | 100.0% |
| reasoning | business-reasoning | 20261018 | cancelled_n | 24 | 24 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_arrive | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_cancelled_n | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_cost | 12 | 18 | 66.7% |
| reasoning | business-reasoning | 20261018 | cf_emergency_wait | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_free_sum | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_total | 36 | 36 | 100.0% |
| reasoning | business-reasoning | 20261018 | cost | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | emergency_wait | 24 | 24 | 100.0% |
| reasoning | business-reasoning | 20261018 | free_sum | 24 | 24 | 100.0% |
| reasoning | business-reasoning | 20261018 | last_end | 42 | 54 | 77.8% |
| reasoning | business-reasoning | 20261018 | late_n | 42 | 42 | 100.0% |
| reasoning | business-reasoning | 20261018 | loaded_n | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | peak_cost | 8 | 24 | 33.3% |
| reasoning | business-reasoning | 20261018 | profit | 0 | 36 | 0.0% |
| reasoning | business-reasoning | 20261018 | rejected_n | 18 | 18 | 100.0% |
| reasoning | business-reasoning | 20261018 | total | 42 | 42 | 100.0% |
| reasoning | business-reasoning | 20261018 | total_cost | 24 | 60 | 40.0% |
| reasoning | business-reasoning | 20261018 | waiting_n | 26 | 42 | 61.9% |
| reasoning | business-reasoning | 20261018 | waste_sum | 0 | 24 | 0.0% |

## 逐题

状态列保留原始判定：`pass`／`fail` 是模型判分结果；`error` 等未判状态在固定分母口径下记 0 分，最终得分列写明原因（如“截断（0分）”）。分组累计只统计已判题；已判但没有可用分组的编码、推理按 0 分计入原分组满分；工程题使用得分点、扣分点、没测到。

| 题库 | 渠道 | 题 | 语言 | 状态 | 阶段分 | 最终得分 | 原因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| business-reasoning | cat-jam-free | NX-09 | - | pass | last_end 100.0（12/12）；waiting_n 100.0（8/8） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-09 | - | fail | last_end 100.0（12/12）；waiting_n 0.0（0/8） | 60.0（12/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-09 | - | fail | last_end 0.0（0/12）；waiting_n 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-10 | - | pass | total_cost 100.0（8/8）；rejected_n 100.0（6/6）；cf_cost 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-10 | - | pass | total_cost 100.0（8/8）；rejected_n 100.0（6/6）；cf_cost 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-10 | - | fail | total_cost 100.0（8/8）；rejected_n 100.0（6/6）；cf_cost 0.0（0/6） | 70.0（14/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-11 | - | pass | free_sum 100.0（8/8）；loaded_n 100.0（6/6）；cf_free_sum 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-11 | - | pass | free_sum 100.0（8/8）；loaded_n 100.0（6/6）；cf_free_sum 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-11 | - | pass | free_sum 100.0（8/8）；loaded_n 100.0（6/6）；cf_free_sum 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-12 | - | pass | total 100.0（8/8）；late_n 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-12 | - | pass | total 100.0（8/8）；late_n 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-12 | - | pass | total 100.0（8/8）；late_n 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-13 | - | pass | cancelled_n 100.0（8/8）；last_end 100.0（6/6）；cf_cancelled_n 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-13 | - | pass | cancelled_n 100.0（8/8）；last_end 100.0（6/6）；cf_cancelled_n 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-13 | - | pass | cancelled_n 100.0（8/8）；last_end 100.0（6/6）；cf_cancelled_n 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-14 | - | fail | total_cost 0.0（0/12）；peak_cost 100.0（8/8） | 40.0（8/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-14 | - | fail | total_cost 0.0（0/12）；peak_cost 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-14 | - | fail | total_cost 0.0（0/12）；peak_cost 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-15 | - | pass | emergency_wait 100.0（8/8）；waiting_n 100.0（6/6）；cf_emergency_wait 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-15 | - | pass | emergency_wait 100.0（8/8）；waiting_n 100.0（6/6）；cf_emergency_wait 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-15 | - | pass | emergency_wait 100.0（8/8）；waiting_n 100.0（6/6）；cf_emergency_wait 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-16 | - | fail | profit 0.0（0/12）；waste_sum 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-16 | - | fail | profit 0.0（0/12）；waste_sum 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-16 | - | fail | profit 0.0（0/12）；waste_sum 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-17 | - | pass | arrive 100.0（8/8）；cost 100.0（6/6）；cf_arrive 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-17 | - | pass | arrive 100.0（8/8）；cost 100.0（6/6）；cf_arrive 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-17 | - | pass | arrive 100.0（8/8）；cost 100.0（6/6）；cf_arrive 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-18 | - | pass | late_n 100.0（8/8）；total 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-18 | - | pass | late_n 100.0（8/8）；total 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-18 | - | pass | late_n 100.0（8/8）；total 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
