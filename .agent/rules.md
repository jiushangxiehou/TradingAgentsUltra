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

(TODO: expand as the project's rules crystallise.)