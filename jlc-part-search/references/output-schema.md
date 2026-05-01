# Output Schema Notes

The schema separates catalog search from exact-part facts.

## Stage 1: filter

`filter` output must not include `selected` or final `enet_fields`.

Required top-level fields:

- `stage`
- `status`
- `query`
- `required_constraints`
- `preferred_constraints`
- `candidates`
- `next_required_action`
- `availability_note`

Candidate fields:

- `rank`
- `lcsc`
- `mpn`
- `manufacturer`
- `package`
- `summary`
- `stock`
- `library_type`
- `product_url`
- `datasheet_pdf`
- `score`
- `matched_constraints`
- `uncertain_constraints`
- `failed_constraints`
- `evidence_source`

## Stage 2: detail

`detail` returns facts for one explicit identifier. If an exact MPN maps to multiple LCSC numbers, return `ambiguous_identifier` and candidates instead of choosing.

## Stage 2: enet

`enet` may emit ENET-compatible fields for one explicit unique part:

- `LCSC`
- `MPN`
- `Manufacturer`
- `Package`
- `footprintName`
- `footprintUuid`

It must not modify files.
