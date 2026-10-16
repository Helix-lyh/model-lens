# 评测报告 · eval-20261018-20261016T230329-hard · 版本 20261018 · 计分 20261018.s1

每个渠道单独成节，不跨模型合计。主口径是固定分母：每次作答按满分进分母，截断、超时、错误、缺失都记 0 分；“已判百分比”是辅助口径，只除以已判题目的满分。编码、工程、推理分开，没有跨栏总分。
阶段：hard。语言：python,go,typescript。采样 1 次。

## 渠道 cat-jam-free

| 题库 | 版本 | 作答 | 已判 | 通过 | 截断 | 固定分母平均分 | 已判平均分 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| business-coding | 20261018 | 10 | 10 | 3 | 0 | 52.0 | 52.0 |
| business-engineering | 20261018 | 10 | 10 | 0 | 0 | 38.0 | 38.0 |
| business-reasoning | 20261018 | 10 | 10 | 7 | 0 | 70.0 | 70.0 |

### 三栏汇总

| 栏目 | 已判/作答 | 累计得分 | 固定满分 | 得分百分比（固定分母） | 已判满分 | 已判百分比（辅助） | 截断 | 超时 | 其他未判 | 严格通过 | pass@1 | pass@k |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| coding | 10/10 | 104 | 200 | 52.0% | 200 | 52.0% | 0 | 0 | 0 | 3 | 0.3 | 0.3 (k=1) |
| engineering | 10/10 | 76 | 200 | 38.0% | 200 | 38.0% | 0 | 0 | 0 | 0 | 0.0 | 0.0 (k=1) |
| reasoning | 10/10 | 140 | 200 | 70.0% | 200 | 70.0% | 0 | 0 | 0 | 7 | 0.7 | 0.7 (k=1) |

### 分组累计

| 栏目 | 题库 | 版本 | 分组 | 得分 | 满分 | 百分比 |
| --- | --- | --- | --- | ---: | ---: | ---: |
| coding | business-coding | 20261018 | g1 | 16 | 40 | 40.0% |
| coding | business-coding | 20261018 | g2 | 20 | 40 | 50.0% |
| coding | business-coding | 20261018 | g3 | 24 | 40 | 60.0% |
| coding | business-coding | 20261018 | g4 | 20 | 40 | 50.0% |
| coding | business-coding | 20261018 | g5 | 24 | 40 | 60.0% |
| engineering | business-engineering | 20261018 | 得分点 | 129 | 200 | 64.5% |
| engineering | business-engineering | 20261018 | 扣分点 | 53 | 200 | 26.5% |
| engineering | business-engineering | 20261018 | 没测到 | 18 | 200 | 9.0% |
| reasoning | business-reasoning | 20261018 | arrive | 8 | 8 | 100.0% |
| reasoning | business-reasoning | 20261018 | cancelled_n | 8 | 8 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_arrive | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_cancelled_n | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_cost | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_emergency_wait | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_free_sum | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | cf_total | 12 | 12 | 100.0% |
| reasoning | business-reasoning | 20261018 | cost | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | emergency_wait | 8 | 8 | 100.0% |
| reasoning | business-reasoning | 20261018 | free_sum | 8 | 8 | 100.0% |
| reasoning | business-reasoning | 20261018 | last_end | 6 | 18 | 33.3% |
| reasoning | business-reasoning | 20261018 | late_n | 14 | 14 | 100.0% |
| reasoning | business-reasoning | 20261018 | loaded_n | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | peak_cost | 0 | 8 | 0.0% |
| reasoning | business-reasoning | 20261018 | profit | 0 | 12 | 0.0% |
| reasoning | business-reasoning | 20261018 | rejected_n | 6 | 6 | 100.0% |
| reasoning | business-reasoning | 20261018 | total | 14 | 14 | 100.0% |
| reasoning | business-reasoning | 20261018 | total_cost | 8 | 20 | 40.0% |
| reasoning | business-reasoning | 20261018 | waiting_n | 6 | 14 | 42.9% |
| reasoning | business-reasoning | 20261018 | waste_sum | 0 | 8 | 0.0% |

## 逐题

状态列保留原始判定：`pass`／`fail` 是模型判分结果；`error` 等未判状态在固定分母口径下记 0 分，最终得分列写明原因（如“截断（0分）”）。分组累计只统计已判题；已判但没有可用分组的编码、推理按 0 分计入原分组满分；工程题使用得分点、扣分点、没测到。

| 题库 | 渠道 | 题 | 语言 | 状态 | 阶段分 | 最终得分 | 原因 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| business-coding | cat-jam-free | CP-09 | python | fail | g1 0.0（0/4）；g2 100.0（4/4）；g3 100.0（4/4）；g4 0.0（0/4）；g5 100.0（4/4） | 60.0（12.0/20） | tests_failed |
| business-coding | cat-jam-free | CP-10 | python | pass | g1 100.0（4/4）；g2 100.0（4/4）；g3 100.0（4/4）；g4 100.0（4/4）；g5 100.0（4/4） | 100.0（20.0/20） | ok |
| business-coding | cat-jam-free | CP-11 | python | pass | g1 100.0（4/4）；g2 100.0（4/4）；g3 100.0（4/4）；g4 100.0（4/4）；g5 100.0（4/4） | 100.0（20.0/20） | ok |
| business-coding | cat-jam-free | CP-12 | python | pass | g1 100.0（4/4）；g2 100.0（4/4）；g3 100.0（4/4）；g4 100.0（4/4）；g5 100.0（4/4） | 100.0（20.0/20） | ok |
| business-coding | cat-jam-free | CP-13 | go | fail | g1 0.0（0/4）；g2 0.0（0/4）；g3 0.0（0/4）；g4 0.0（0/4）；g5 0.0（0/4） | 0.0（0.0/20） | tests_failed |
| business-coding | cat-jam-free | CP-14 | go | fail | g1 100.0（4/4）；g2 100.0（4/4）；g3 100.0（4/4）；g4 100.0（4/4）；g5 0.0（0/4） | 80.0（16.0/20） | tests_failed |
| business-coding | cat-jam-free | CP-15 | go | fail | - | 0.0（0/20） | execution_error |
| business-coding | cat-jam-free | CP-16 | typescript | fail | g1 0.0（0/4）；g2 0.0（0/4）；g3 0.0（0/4）；g4 0.0（0/4）；g5 0.0（0/4） | 0.0（0.0/20） | tests_failed |
| business-coding | cat-jam-free | CP-17 | typescript | fail | g1 0.0（0/4）；g2 0.0（0/4）；g3 100.0（4/4）；g4 0.0（0/4）；g5 100.0（4/4） | 40.0（8.0/20） | tests_failed |
| business-coding | cat-jam-free | CP-18 | typescript | fail | g1 0.0（0/4）；g2 0.0（0/4）；g3 0.0（0/4）；g4 100.0（4/4）；g5 100.0（4/4） | 40.0（8.0/20） | tests_failed |
| business-engineering | cat-jam-free | E-01 | - | fail | 得分点 12/20；扣分点 4/20；没测到 4 | 40.0（8/20） | content_mismatch |
| business-engineering | cat-jam-free | E-02 | - | fail | 得分点 12/20；扣分点 8/20；没测到 0 | 20.0（4/20） | content_mismatch |
| business-engineering | cat-jam-free | E-03 | - | fail | 得分点 7/20；扣分点 4/20；没测到 9 | 15.0（3/20） | content_mismatch |
| business-engineering | cat-jam-free | E-04 | - | fail | 得分点 13/20；扣分点 7/20；没测到 0 | 30.0（6/20） | content_mismatch |
| business-engineering | cat-jam-free | E-05 | - | fail | 得分点 11/20；扣分点 9/20；没测到 0 | 10.0（2/20） | content_mismatch |
| business-engineering | cat-jam-free | E-06 | - | fail | 得分点 14/20；扣分点 6/20；没测到 0 | 40.0（8/20） | content_mismatch |
| business-engineering | cat-jam-free | E-07 | - | fail | 得分点 16/20；扣分点 4/20；没测到 0 | 60.0（12/20） | content_mismatch |
| business-engineering | cat-jam-free | E-08 | - | fail | 得分点 15/20；扣分点 5/20；没测到 0 | 50.0（10/20） | content_mismatch |
| business-engineering | cat-jam-free | E-09 | - | fail | 得分点 13/20；扣分点 3/20；没测到 4 | 50.0（10/20） | content_mismatch |
| business-engineering | cat-jam-free | E-10 | - | fail | 得分点 16/20；扣分点 3/20；没测到 1 | 65.0（13/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-09 | - | fail | last_end 0.0（0/12）；waiting_n 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-10 | - | pass | total_cost 100.0（8/8）；rejected_n 100.0（6/6）；cf_cost 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-11 | - | pass | free_sum 100.0（8/8）；loaded_n 100.0（6/6）；cf_free_sum 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-12 | - | pass | total 100.0（8/8）；late_n 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-13 | - | pass | cancelled_n 100.0（8/8）；last_end 100.0（6/6）；cf_cancelled_n 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-14 | - | fail | total_cost 0.0（0/12）；peak_cost 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-15 | - | pass | emergency_wait 100.0（8/8）；waiting_n 100.0（6/6）；cf_emergency_wait 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-16 | - | fail | profit 0.0（0/12）；waste_sum 0.0（0/8） | 0.0（0/20） | content_mismatch |
| business-reasoning | cat-jam-free | NX-17 | - | pass | arrive 100.0（8/8）；cost 100.0（6/6）；cf_arrive 100.0（6/6） | 100.0（20/20） | ok |
| business-reasoning | cat-jam-free | NX-18 | - | pass | late_n 100.0（8/8）；total 100.0（6/6）；cf_total 100.0（6/6） | 100.0（20/20） | ok |
