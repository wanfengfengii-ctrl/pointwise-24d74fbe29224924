# 岚桥绝缘复检台账

晨班工艺员从试验记录取得各分支的概率与耗时，登记 A 初检站和 B 确认站的流程。站员按修订号发行两份证据。夜班接线员按实收件固定当轮接线，班长在站库下线后核定截止前的完结比例和永不完结比例，用于决定是否加开复检工位。次班更正试验依据后，仍可领取原排班报告及回执。

## 运行

使用 Python 3.11 和标准库，在项目根目录运行。

```sh
python3 -B check_project.py
python3 -B -m retest.demo
```

`check_project.py` 由控制台物化，执行 `tests` 包中的完整 unittest 回归。演示读取 `examples/` 的日常与勘误数据并在临时目录建库，输出实测报告。日常样例在第 1、3 拍累计完成 1/2、3/4，勘误后分别为 0、3/4，两版均最终必完结。

## Python 接口

存储类接受空闲的 `sqlite3.Connection`。站端用 `RevisionStore` 和 `EvidenceRegistry`，中心用 `ManifestStore` 和 `ReportLedger`。初次使用及重开均可调用各自的 `initialize()`。连接由调用者关闭。写入接口持有自己的事务，已有事务须由调用者先结束。

```python
from retest.revisions.model import RevisionDraft, Transition, TrialSource
from retest.revisions.registry import register
from retest.revisions.storage import RevisionStore
from retest.evidence.issue import issue
from retest.evidence.registry import EvidenceRegistry
from retest.wiring.binding import bind
from retest.wiring.ports import PortRef
from retest.wiring.storage import ManifestStore
from retest.analysis.review import ReviewRequest, review
from retest.reports.ledger import ReportLedger
from retest.reports.retrieve import get
```

- `register(revisions, draft) -> Revision` 固定 `RevisionDraft(station, revision_id, source, entries, exits, transitions, predecessor=None)`。`TrialSource(work_order, round_id, trial_id)` 保存上游出处。入口映射到私有状态名。`Transition(target, probability, ticks, is_exit=False)` 的目标为私有状态，`is_exit=True` 时为公开出口。概率可用 `Fraction`、整数或 `Fraction` 可解析的字符串。每个状态的分支和为 1。拍数为非负整数。勘误用新号和本站已有前版号登记。
- `issue(revisions, issued, station, revision_id) -> str` 按原号取得修订并返回 V1 JSON 正文。`EvidenceRegistry.read(piece_id)` 领取原件。件号是规范 JSON 内容的 SHA-256 摘要，可核对正文与件号的一致性。上游出处来自站端登记。正文携带逐公开入口、逐出口的首出序列和永久留站质量。`decode_evidence(body)` 可离线读取 `StationEvidence`。`ExitSeries.coefficients_through(n)` 返回从第 0 到第 n 拍的质量，`total_mass()` 返回该出口的最终质量。
- `bind(manifests, manifest_id, source, bodies, connections) -> Manifest` 固定两站同工单同轮的原始正文及接线出处。`connections` 是 `(PortRef(件号, 出口名), 目的地)` 对序列。目的地为 `PortRef(件号, 入口名)` 或 `None`，后者表示完结。各出口恰好出现一次。入口与出口按方向解析，同名端口可通过件号区分。
- `review(manifests, ledger, ReviewRequest(manifest_id, start, deadline)) -> IssuedReport` 核定并签发。`start` 是实际公开入口，`deadline` 是非负整数，包含该拍。再次入站从接线指定入口开始。截止时仍允许零拍接续。`snapshot.on_time` 和 `snapshot.never_complete` 为 `Fraction`，逾期但最终完成的质量为 `1 - on_time - never_complete`。报告快照携带原请求、双件出处及接线。`receipt.report_id` 是本中心账簿的签发号。
- `get(ledger, report_id) -> IssuedReport` 按号领取原快照及回执。读取无需站库和分析求解器。未知修订、站件、接线和报告以 `KeyError` 表示。非法数据或身份冲突以 `ValueError` 表示。SQLite 写入错误会传给调用者，签发事务撤回本次定稿和回执。

站端求解在首次到达公开出口时结束计时。中心按剩余拍数累计完结概率，用精确方程结清同拍接续，并另行核算最终可完结质量。回归覆盖等边缘换时、长尾首出、串行接线、重入、同拍可退出循环、永久互返、站内滞留、错件拒绝、回执拒写及原号交班。演示和测试使用固定输入及临时工作目录。
