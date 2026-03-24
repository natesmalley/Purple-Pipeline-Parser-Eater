# Dataset Fixture Model (PR-1)

## Goal
Define dataset-first harness inputs using a stable fixture layout, separate from Lua execution mechanics.

## Stable Layout

```text
dataset_root/
  metadata.json
  cases/
    010-<name>.json
    020-<name>.json
    ...
```

## Contracts
- `metadata.json` contains dataset-level metadata only (for example: `dataset_id`, `parser_name`, `vendor`, `product`).
- `cases/*.json` contains per-case event inputs and expected-behavior metadata.
- Case traversal order is deterministic: sorted by case filename.
- Execution logic should consume ordered case events from the dataset model, not raw filesystem traversal.

## Compatibility and Scope
- This milestone introduces dataset loading/model boundaries only.
- No Lua execution behavior changes are included in PR-1.
- Backward compatibility remains preserved.
