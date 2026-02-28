# ST-005 Task Index — Evidence-Grounded Summarization + Quality Gate

- Story: [ST-005 — Evidence-Grounded Summarization + Quality Gate](../../ST-005-evidence-grounded-summarization-and-quality-gate.md)
- Requirement Links: MVP §4.3(2-4), FR-4, FR-7(3), NFR-4, NFR-7

## Ordered Checklist

- [x] [TASK-ST-005-01](TASK-ST-005-01.md) — Summary/Evidence Persistence Schema
- [x] [TASK-ST-005-02](TASK-ST-005-02.md) — Summarization Output Contract
- [ ] [TASK-ST-005-03](TASK-ST-005-03.md) — Claim Evidence Attachment
- [ ] [TASK-ST-005-04](TASK-ST-005-04.md) — Quality Gate and Append-Only Publish Path
- [ ] [TASK-ST-005-05](TASK-ST-005-05.md) — ST-005 Verification and Evidence Retrieval Coverage

## Dependency Chain

- TASK-ST-005-01 -> TASK-ST-005-02
- TASK-ST-005-01 -> TASK-ST-005-03
- TASK-ST-005-02 -> TASK-ST-005-03
- TASK-ST-005-02 -> TASK-ST-005-04
- TASK-ST-005-03 -> TASK-ST-005-04
- TASK-ST-005-03 -> TASK-ST-005-05
- TASK-ST-005-04 -> TASK-ST-005-05

## Validation Commands

- `pytest -q`
