# Domain Docs

## Before exploring, read these

- `CONTEXT.md` at the repo root; or
- `CONTEXT-MAP.md` at the repo root if it exists, then each relevant context's `CONTEXT.md`; and
- relevant ADRs under `docs/adr/`.

If these files do not exist, proceed silently. The domain-modeling workflow creates them when terminology or decisions are resolved.

## File structure

This is a single-context repository:

```
/
├── CONTEXT.md
├── docs/adr/
└── src/
```

## Use the glossary's vocabulary

Use terms defined in `CONTEXT.md` in issues, proposals, and tests. If an ADR conflicts with a proposed change, surface the conflict rather than silently overriding it.
