# 完整扫描时窗核报

夜班用同一试件已经核实完整的扫描记录更新排班判断。README.md 说明现用的修订、站件、接线和签报接口。以下约定用于新增的扫描核报。

## 修订与实收

- 在 `retest.revisions.model.Transition(target, probability, ticks, is_exit=False, scan=None)` 末尾增加可选 `scan`。名称为非空白字符串，`None` 表示此分支无扫描。登记、重开读回及显式选版均保留标记。读取既有修订时，未记录标记的分支视作 `scan=None`。
- `retest.evidence.issue.issue(revisions, issued, station, revision_id, *, version=1)` 保留原调用。版本只能取非布尔整数 `1` 或 `2`。默认 V1 沿用原格式和首离站口径，忽略扫描。`version=2` 按实际指定修订发行带扫描证据的固定原件，即使该修订没有扫描。原件仍可由 `EvidenceRegistry.read(piece_id)` 领取。
- V2 JSON 沿用 `version`、`kind`、`id`、`origin`、`body` 外层字段，`version` 为 `2`，`kind` 为 `station-evidence`。件号沿用 V1 的规范 JSON 摘要约定。`origin` 沿用原有修订与试验出处字段。`body` 的证据表示由实现决定，须足以保全公开入口、出口与扫描后的走向。私有工序名称和原试验明细留站。
- `retest.evidence.encoding.decode_evidence(body)` 继续读取旧件，也读取新版并提供 `piece_id` 和 `origin`。新版实收须离线核对件号、证据结构、内部引用及质量守恒。坏正文或校验失败以 `ValueError` 拒收，接线不得留下半件。
- `bind` 用原参数和 `PortRef` 固定同工单同轮的两个不同站点。站件必须同版，V1 与 V2 混收时抛 `ValueError`。原件、接线及出处的固定规则沿用 README.md。

## 核报与领取

- 在 `retest.analysis.review` 提供 `ScanReviewRequest(manifest_id, start, observed_through, scans, deadline)`，交给原 `review(manifests, ledger, request)`。`start` 为实际固定的公开入口。从该入口第 0 拍开始。`observed_through` 为 C，`deadline` 为 D，均为非布尔整数且 `0 ≤ C ≤ D`。
- `scans` 为 `(tick, name)` 的列表或元组，元素可用二元列表或元组。拍数为 `[0,C]` 内非布尔整数并按时间非降序排列，名字为非空白字符串。同一拍保留实录顺序，可重复或无任何记录。合法但模型中从未出现的名字仍可作为观测请求。
- 每条分支在本次耗时结束时发生其扫描。分支离站时，先计该分支的扫描，再按固定接线于同拍接续或完结。再次入站从接线指定入口开始，累计时间继续。扫描相容指路径在闭区间 `[0,C]` 内的全部扫描与观测逐项一致。首次一致后同拍多出的扫描仍排除该路径。若路径在窗内无限扫描，则与任何有限实录均不相容。某条路径已完结、仍在途或永久静默时，只要窗内扫描完全相符，均计入支持。C 拍之后的扫描不影响相容性。
- 支持为相容路径的总概率。按期为相容且在 D 拍及之前完结的概率除以支持。永不完结为相容且始终未到达接线完结点的概率除以支持。两项计算使用同一支持。数值均用 `Fraction`。支持为零时仍签存报告和同号回执，两项条件值均为 `None`。
- `review` 继续返回 `IssuedReport`。条件报告的 `snapshot` 沿用 `manifest`、`origins`、`start`、`deadline`、`on_time`、`never_complete`，增 `observed_through`、`scans`、`support`。`scans` 存独立的二元组元组。关闭源库并重开中心后，`get(ledger, report_id)` 可领回原观测、条件结果、原接线、双件出处和回执。定稿和回执一并签存，任一写入失败都撤回本次签存。
- 原 `ReviewRequest` 继续用于双 V1 站件，原报告可直接读取。`ScanReviewRequest` 只接受双 V2 站件。非法请求、错端口或版本不适用时抛 `ValueError`，未知接线沿用 `KeyError`，拒绝不生成报告或回执。

## 样例与核验

`examples/scan.json` 给出完整站端模型、接线和观测。`models` 的键为样例修订号，`rows` 的分支顺序为 `[目标, 概率, 拍数, 是否离站, 扫描名]`，同组站件使用同一工单和轮次。`cases` 用 `a` 选择 A 修订，B 固定用 `confirmation`。`wiring` 内的端点先用 `[站名, 端口名]` 表示，实收时换成对应件号。`null` 目的地为完结点。每例从 A 的 `in` 开始。`v1` 依次为按期和永不完结，`v2` 依次为支持、条件按期和条件永不完结。

`fast-order` 和 `slow-order` 的首出分布相同。同一完整扫描 R、X、Y 分别指向快、慢路径，条件按期为 1 和 0，支持均为 1/2。`window-edge` 在第 1 拍扫 R 后有四条等重支路。该拍完结、该拍多扫 X、第 3 拍完结和永久静默各占 1/4。观测只有 R 时支持为 3/4，条件按期及条件永不完结均为 1/3。`silent-return` 可同拍静默跨站任意次后完结，单个 R 支持为 1。`marked-return` 把回流接至每次都扫 R 的入口，两个 R 恰需一次回流，支持为 1/4。`empty-window` 和 `no-support` 分别展示合法空窗与零支持签报。

当前可运行 `python3 -B check_scan_fixture.py`，它投影掉扫描，关闭站端连接后核对冻结 V1 的结果及存档。交付时沿用 `.pointwise-runtime.json`，让 `verify` 同时执行完整原回归和新增条件核验，让 `demo` 展示一次真实的断源签报及按号领取。条件核验应覆盖样例结果、错版或非法请求拒绝、回执写入失败时无半件，以及中心重开后按原号领取。
