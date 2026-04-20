# Marco Rottigni 2026-04-08 LUA Workbench test cases

Source: `docs/reference/The Parser Builder.pdf` (Marco Rottigni, April 8, 2026).

Marco ran the LUA Workbench end-to-end against four synthetic log streams
(HELIOS → Observo → AI SIEM) and documented the generated Lua plus the observed
Workbench findings. These four cases are now captured here as regression fixtures
so the harness can replay them and confirm that our validation modules reproduce
the same findings Marco saw in the UI.

Each `<slug>/` subdir contains:

- `sample.json` — one representative event from Marco's test batch
- `parser_config.json` — minimal parser config used to drive the harness
- `generated.lua` — the Lua the Workbench produced at test time
- `expected.json` — the harness findings Marco observed, captured in machine form

| slug | outcome | lint score | OCSF mapping | notable finding |
|---|---|---|---|---|
| `cisco_duo` | FAIL | 64.5 / Fair | 33% / Poor | "time" required field not detected in output assignments |
| `ms_defender_365` | PASS | — | — | rendered correctly in AI SIEM |
| `akamai_cdn` | PASS | — | — | rendered correctly in AI SIEM |
| `akamai_dns` | FAIL | 4.5 / Poor | 67% / Fair | runtime `attempt to call a nil value (method 'match')` |

Use `tests/test_regression_marco_pdf.py` to run these end-to-end through the
harness and verify our modules detect the same classes of issues.
