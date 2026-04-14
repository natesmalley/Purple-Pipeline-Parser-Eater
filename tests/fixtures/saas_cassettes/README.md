# SaaS API Cassettes

## Why these exist

Plan Phase 4.A regression gate. Before refactoring `components/observo_client.py`
URL paths or `build_pipeline_json` payload shape, we captured the SaaS REST
wire format into these JSON files so the refactor has a ground-truth reference
it can be asserted against.

The SaaS API is `https://p01-api.observo.ai/gateway/v1/*`. All endpoints live
under `/gateway/v1/`. The earlier URL string `{base_url}/pipelines` in
`components/observo_client.py` (lines ~290, 313, 329 before the Phase 4.B fix)
was wrong -- it predates anyone reading `observo docs/pipeline.md` carefully.

## What's in here

| File | Endpoint | Source |
| --- | --- | --- |
| `transform_lua_script.json` | `POST /gateway/v1/transform` | `observo docs/transform.md:11` + `observo docs/lua-script.md:15-24` |
| `pipeline_deserialize.json` | `POST /gateway/v1/deserialize-pipeline` | `observo docs/pipeline.md:3-60` |
| `pipeline_action.json` | `PATCH /gateway/v1/pipeline/action` | `observo docs/pipeline.md:80-86` |

Each cassette has:

* `_source` -- which doc file + line range the shape was derived from
* `_endpoint` -- HTTP method + path (canonical SaaS URL)
* `_notes` -- anything load-bearing about the interpretation
* `_incomplete` -- `true` if the doc only documents the response and we had to
  guess the request body; such cassettes should be replaced with a real
  HTTP recording ASAP
* `request` -- the request body shape
* `response` -- the response body shape

## How to regenerate from observo docs/

1. Read the relevant `observo docs/*.md` file.
2. Find the OpenAPI JSON blob for the endpoint.
3. Extract the request/response schemas and the example shapes.
4. Translate into a JSON object that matches what our client will serialize.
5. Update `_source` to point at the new section/line range.

## How to replace with real HTTP recordings

Once a sandbox SaaS tenant becomes available:

1. Capture real `POST /gateway/v1/transform` etc. with `pytest --record-mode` +
   a cassette library, or with a transparent HTTP proxy.
2. Scrub auth tokens, tenant IDs, and any PII from the captured JSON.
3. Overwrite the corresponding cassette file with the recording.
4. Flip `_incomplete` to `false` and update `_source` to note the real-capture
   timestamp.
5. Run `pytest tests/test_observo_saas_payload.py tests/test_observo_deploy_end_to_end.py`
   -- any shape drift will fail loudly and drive the follow-up code fix.

## Scope

These cassettes target the **SaaS REST control plane** only
(`p01-api.observo.ai/gateway/v1/*`). They do **not** describe the standalone
dataplane YAML wire format used by `./dataplane --config file.yaml`. The
standalone dataplane lives in a separate code path (Phase 5 territory) and
must not be reconciled against these cassettes.
