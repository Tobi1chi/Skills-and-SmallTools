# CDL Review Checklists

Use these checks to validate CDL as a representation. They do not replace
domain-specific electrical design review.

## Syntax And Structure

- [ ] Every block uses `## [Label] intent text`.
- [ ] Every component declaration has at least RefDes and PartValue.
- [ ] Connection statements use only `~~`, `-->`, or `==`.
- [ ] Parameters use `RefDes : key=value` syntax.
- [ ] Special annotations use component-level or pin-level `!` syntax.
- [ ] Comments use `//`.

## Declarations And References

- [ ] Every component referenced by a connection is declared.
- [ ] Every pin reference uses a declared component designator.
- [ ] No component pin appears on two different named nets unless explicitly
      identified as an unresolved conflict.
- [ ] Every named net has enough members to explain its purpose, or a `// CHECK`
      marks why it is currently single-node.
- [ ] Rail names used with `==` are standard within the document or declared
      with `rail:` when metadata is needed.

## Consistency

- [ ] The same intended signal uses the same net name across all blocks.
- [ ] Different intended signals do not reuse one net name.
- [ ] `-->` net names match any `~~` extensions of the same net.
- [ ] Generated or omitted net names do not hide cross-block connections.
- [ ] Block boundaries minimize unnecessary cross-block nets.
- [ ] Large blocks are split when they are no longer easy to inspect.

## Unknowns And Annotations

- [ ] Every uncertain value, pin, part, or connection is marked with `// CHECK`.
- [ ] Every `// CHECK` has a corresponding open question.
- [ ] Intentionally unconnected pins are marked with `! NC`.
- [ ] Optional or population-dependent components are marked with `! DNP` or
      `! OPT` when known.
- [ ] Test or probe points are marked with `! TP` when the source identifies
      them as such.

## Logical Netlist Readiness

- [ ] Components can be listed without ambiguity.
- [ ] Nets can be generated from connection statements without interpreting
      prose.
- [ ] Direction metadata from `-->` is not required to infer connectivity.
- [ ] Parameters and annotations can be preserved separately from topology.
- [ ] EDA-specific pin numbers, footprints, and library mappings are not assumed
      unless explicitly provided outside CDL.

## Domain Review Handoff

Move these out of CDL review and into schematic/domain review when they matter:

- Whether the topology is electrically correct for the product.
- Whether values, tolerances, ratings, sequencing, timing, or protection choices
  are appropriate.
- Whether datasheet requirements are satisfied.
- Whether layout, thermal, EMC, safety, or manufacturing constraints are met.
