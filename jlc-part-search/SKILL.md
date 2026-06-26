---
name: jlc-part-search
description: "Search the JLC/LCSC/SZLCSC/JLCPCB/EasyEDA component catalog with a mandatory two-stage workflow: first filter broad requirements into candidate parts, then fetch detailed facts and ENET-compatible fields only for one explicit LCSC number or exact MPN. Use when Codex needs 嘉立创/LCSC part numbers, datasheet PDF links, product links, EasyEDA footprint/symbol metadata, or structured component facts for later BOM/ENET work. Do not use this skill to modify .enet files or validate a circuit design."
---

# JLC Part Search

Use this skill to query 嘉立创/LCSC component availability and return verifiable part facts. The default source is `domestic`, which uses SZLCSC domestic public catalog data first and emits RMB/CNY price fields when present. This skill is intentionally split into two mandatory stages so Codex does not confuse "found in the catalog" with "suitable for the design".

## Mandatory Workflow

1. Run `filter` for broad user requirements.
2. Present the ranked candidates and their evidence gaps.
3. Only after a specific `Cxxxxxx` LCSC code or exact MPN is chosen, run `detail` or `enet`.

Catalog availability is not design validation. If a requirement is not directly supported by returned catalog parameters, product text, or datasheet metadata, mark it as unverified.

## Commands

Run the bundled CLI with `uv run`:

```bash
uv run python ~/.codex/skills/jlc-part-search/scripts/jlc_parts.py filter "10k 1% 0402 resistor"
uv run python ~/.codex/skills/jlc-part-search/scripts/jlc_parts.py detail C25804
uv run python ~/.codex/skills/jlc-part-search/scripts/jlc_parts.py enet C25804
uv run python ~/.codex/skills/jlc-part-search/scripts/jlc_parts.py datasheet C25804 --output-dir ./datasheets
```

The CLI defaults to `--source domestic`. Use `--source auto` only when domestic sources are insufficient and overseas/public fallback behavior is explicitly acceptable.

`filter` is stage 1. It searches the catalog and returns possible candidates only:

- never returns `selected`
- never returns final `enet_fields`
- never claims a candidate satisfies the design
- never treats no catalog result as proof that the design is impossible

`detail` is stage 2. It fetches facts for one explicit LCSC code or exact MPN:

- does not perform broad requirement search
- does not switch to another candidate automatically
- returns product URL, datasheet PDF URL, stock/library hints, RMB/CNY price tiers when available, parameters, and EasyEDA metadata when available

`enet` is stage 2 formatting for one explicit part. It returns ENET-compatible fields only; it does not create, patch, or overwrite `.enet` files.

`datasheet` is a stage 2 download command for one explicit LCSC code or exact MPN:

- does not perform broad requirement search
- does not switch to another candidate automatically
- downloads only the resolved part's `datasheet_pdf`
- defaults to `./datasheets` and returns the written PDF path in JSON
- does not modify catalog data, `.enet` files, or user design files

## Output Contract

`filter` returns JSON with:

- `stage: "filter"`
- `status`: `candidates`, `no_catalog_match`, or `no_verified_candidates`
- `query`
- inferred `required_constraints` and `preferred_constraints`
- `candidates[]` with `lcsc`, `mpn`, `manufacturer`, `package`, `stock`, `price_currency`, `price_tiers`, `min_order_qty`, `unit`, `library_type`, URLs, score, matched/uncertain/failed constraints
- `next_required_action: "run_detail_for_one_candidate"`

`detail` returns JSON with:

- `stage: "detail"`
- `status`: `detail`, `ambiguous_identifier`, or `no_catalog_match`
- one explicit part's facts when unique
- no final `enet_fields`

`enet` returns JSON with:

- `stage: "enet"`
- `status: "enet_fields"` when unique
- `selected` part summary
- `enet_fields`: `LCSC`, `MPN`, `Manufacturer`, `Package`, `footprintName`, `footprintUuid`
- `evidence`: product and datasheet URLs

`datasheet` returns JSON with:

- `stage: "datasheet"`
- `status`: `downloaded`, `exists`, `no_datasheet`, `no_catalog_match`, `ambiguous_identifier`, `invalid_datasheet_url`, `download_failed`, or `not_pdf`
- `selected` part summary when a unique part resolves
- `datasheet_pdf`, `file_path`, `bytes`, and `content_type` when available

Read `references/api-notes.md` before changing API behavior. Read `references/output-schema.md` before changing JSON field names.

## Validation

After changing this skill, run:

```bash
uv run python ~/.codex/skills/.system/skill-creator/scripts/quick_validate.py ~/.codex/skills/jlc-part-search
uv run python ~/.codex/skills/jlc-part-search/scripts/jlc_parts.py self-test
```

Use live `filter`, `detail`, and `enet` commands only when network access is available.
