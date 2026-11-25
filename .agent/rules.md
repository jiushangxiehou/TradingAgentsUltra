# .agent/rules.md — Project Covenant (D3)

> The project covenant: abstraction limits, dependency constraints, test
> independence, the safety-critical change rule, and context freshness. Changes
> to this file are human-only.

## Covenants
1. **Abstraction limits.** No module reaches into another module's internals;
   only the module's public interface may be used. Legal interface violations
   are structural-constraint defects.
2. **Dependency constraints.** A module may depend only on modules lower in the
   architecture and on the declared data/LLM adapters (advisory). No circular
   dependencies. New third-party deps need an ADR.
3. **Test independence.** Every feature has at least **one negative test** (a
   test that fails when the feature is absent / the invariant is violated),
   in addition to positive tests. Tests must not depend on one another.
4. **Safety-critical changes require an architecture decision + human approval.**
   Changing `src/guardrail.py`, any invariant, or the trust boundary must go
   through an ADR and be approved by a human; CI blocks the change without it.
5. **Context freshness.** When a requirement in `docs/req/requirements.yaml`
   changes, the relevant rules must be updated within **one sprint** of that
   change, or the drift is a defect (see `docs/debt-register.md`).

6. **No secrets in artefacts.** Never write API keys, tokens or credentials into
   the repository, transcripts, reports or logs. Scan before publishing.
7. **Quote evidence, not memory.** A report or review must quote the command
   output/path it relies on; do not reconstruct a test count or baseline result
   from recollection.
8. **Formatting requirements are requirements.** “Point 12” means 12-point font
   size, not a report section; the report must satisfy the stated page/word
   constraints.
9. **Baseline drift is a decision.** Editing a pinned file, or merging a branch
   that does, requires an ADR or a declared override; the verifier is not to be
   weakened to make the tree pass.
10. **Every merge leaves a record.** A merge that changes a requirement, module
    boundary, test or gate updates the relevant D4 record; a template is not a
    completed review.