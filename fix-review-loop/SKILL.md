---
name: fix-review-loop
description: Repeatedly diagnose, fix, verify, and review a code problem until no actionable issue remains or the work reaches a genuine technical decision point. Use when the user wants the agent to keep iterating on a bug or failing behavior, re-review its own changes after each fix, and stop only when the loop is clean or a route choice requires user input.
---

# Fix Review Loop

Use this skill when the user wants a closed-loop repair workflow instead of a
single-pass fix.

The loop is:

1. reproduce or define the failure
2. identify the most likely root cause
3. make the smallest credible fix
4. run focused verification
5. review the changed area again for regressions, edge cases, and missing tests
6. repeat if a new actionable issue is found

Do not stop after the first patch unless the verification and re-review are
both clean.

## Start Conditions

Before coding, establish at least one of these:

- a failing test
- a reproducible command
- a concrete incorrect behavior
- a precise code-review finding

If none exist, first tighten the problem statement and inspect the codebase
until the failure is concrete.

## Operating Rules

- Prefer the smallest fix that explains the failure.
- After each fix, review the change like a skeptical reviewer.
- Look for:
  - behavioral regressions
  - broken assumptions
  - edge cases
  - missing or weak tests
  - contract mismatches
  - error handling gaps
- If a new problem is discovered and is actionable, fix it in the same loop.
- If a new problem requires a product or architecture choice, stop and
  escalate with options.

## Verification Rules

After every meaningful change, run the narrowest useful verification first:

- the failing test
- the closest targeted test file
- a specific build or lint command
- a focused reproduction command

Then broaden verification only as needed.

Never claim the loop is complete without reporting what was run and what
remains unverified.

## Review Pass Requirements

Each review pass must answer:

1. Does the fix actually address the original failure?
2. Did the fix create a nearby regression?
3. Is there an adjacent edge case left uncovered?
4. Is there a missing test that should now exist?
5. Is the current implementation still the smallest coherent change?

If any answer reveals an actionable defect, continue the loop.

## Stop Conditions

Stop only when one of these is true:

1. The original issue is fixed, verification is green, and re-review finds no
   further actionable defect.
2. The next step depends on a real technical route choice that the user should
   make.
3. The remaining blocker is external:
   - missing credentials
   - unavailable environment
   - irreproducible failure
   - dependency or infrastructure outage
4. Further iteration would require speculative redesign rather than concrete
   bug fixing.

## Escalation Format

When stopping because of a technical choice, present:

- the decision point
- option A
- option B
- tradeoff of each
- the recommended option
- what work is blocked on that choice

Do not continue coding past a genuine route fork without user confirmation.

## Output Style

Give brief progress updates during the loop.

At the end, report:

- what was fixed
- what verification ran
- what the re-review found
- whether the loop stopped cleanly or due to a decision point
- any residual risk

## Good Trigger Phrases

This skill should trigger on requests like:

- "fix this bug and keep reviewing until it's clean"
- "don't stop after one patch, re-check your own changes"
- "iterate until there are no more issues or you need a decision from me"
- "run a fix-review loop"

## Example Prompt

Use this workflow:

Fix the reported problem in a loop. After each fix, run focused verification
and then review the changes again for regressions, edge cases, and missing
tests. If you find another actionable problem, fix it and repeat. Stop only
when the loop is clean or when the next step depends on a real technical route
choice that requires user input.
