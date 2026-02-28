# ST-013 Governance Request Lifecycle State Model

**Story:** ST-013  
**Task:** TASK-ST-013-02  
**Date:** 2026-02-28

## Export request states

- `requested` -> `accepted`, `cancelled`
- `accepted` -> `processing`, `cancelled`
- `processing` -> `completed`, `failed`, `cancelled`
- `failed` -> `processing`, `cancelled`
- `completed` -> terminal
- `cancelled` -> terminal

## Deletion request states

- `requested` -> `accepted`, `rejected`, `cancelled`
- `accepted` -> `processing`, `cancelled`
- `processing` -> `completed`, `failed`, `cancelled`
- `failed` -> `processing`, `cancelled`
- `completed` -> terminal
- `rejected` -> terminal
- `cancelled` -> terminal

## Data model guarantees

- Request creation is idempotent by `idempotency_key` unique constraints.
- Status changes write append-only status history rows.
- Governance audit events are immutable append-only records.
- Request tables enforce user identity referential integrity through `governance_user_identities(user_id)`.
- Deletion SLA observability is enabled via required `due_at` for accepted/processing/completed/failed states.
