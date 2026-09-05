# Schema versioning convention

Persistent serialized contracts live under `schemas/` and are authoritative.

- Schema files use the form `<contract>.vN.schema.json`.
- `$id` ends with the same `/vN` version identifier as the filename.
- Released schema versions are immutable. Backward-incompatible changes create a new major schema file instead of changing the meaning of an existing field.
- `schemaVersion` values use the matching decimal string (`"1"` for `v1`).
- Fixtures under `fixtures/schemas/` are named `<contract>.vN.valid.json` or `<contract>.vN.invalid.json` and are checked by `pnpm schema:validate`.
- Unknown medical or registration state must be represented explicitly; validators must not silently assume defaults such as identity registration or millimetres.
