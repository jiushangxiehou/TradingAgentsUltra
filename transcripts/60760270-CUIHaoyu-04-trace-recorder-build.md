# D5 Session 04 — Trace Recorder Build and Integration

- **Student:** CUI Haoyu (60760270)
- **Stage:** 4 of 5 — trace-recorder implementation and full-suite integration
- **Scope:** REQ-TRACEABILITY (with the guardrail already green from session 03)
- **Harness:** OpenCode v2.2.5
- **Session ID:** `ses_df1d8beb5ffew1CtRBZR9YPTIg`
- **Model:** `custom-foundry/CS5351/DeepSeek-V4-Flash`
- **Started:** 2026-11-24 15:23:03 UTC
- **Outcome:** `succeeded`
- **Messages:** 18
- **Working directory:** `C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app`

> Tool-output policy: user/assistant text is verbatim; tool calls and inputs are
> reproduced; `read` results are summarized to their first line; other tool
> results are capped at 4,000 characters with a truncation marker. The complete
> raw session is the sibling `.session.json` export.
>
> **Annotation legend:** `TASK` = stage goal; `APPROVE` / `REJECT` / `REDIRECT` / `AUTHORIZE` / `RESOLVE` = student intervention, each with its rationale. Annotations are added by the student reviewer after the session and are not part of the agent's output.

---

## Turn 1 — Student

> **[INTERVENTION — AUTHORIZE (scope and acceptance)]** The student limits this build to `src/trace_recorder.py`, forbids any edit to the tests or the guardrail, and fixes the three acceptance commands. Rationale: the tests encode the approved T1-T9 conditions; allowing test edits would erase the evidence boundary established in session 03, and the guardrail must remain untouched while the second component is built.

> **[TASK — trace-recorder build]** The student requires the implementation to satisfy the existing test contract rather than adapting the contract to the implementation. Rationale: the implementation must be driven by the approved acceptance conditions, not the reverse.

"You are the coding agent for our CS5351 team project. This session is the BUILD stage, part 2: implement the trace recorder. Do NOT modify tests, the guardrail, docs, or any out-of-scope file.

Read AGENTS.md, test/offline/test_traceability.py, src/guardrail.py (for module style and docstring conventions), and the approved architecture decisions below.

The test file test/offline/test_traceability.py is the acceptance contract. Do not weaken or edit it.

Implement ONLY src/trace_recorder.py (T-A, ADR-003, REQ-TRACEABILITY, INV-TRACE-COMPLETENESS):
- Frozen dataclasses: DataSnapshot(snapshot_id, data_source, fetch_timestamp), TraceLink(link_id, assertion_id, referenced_data_snapshot_id, critical), AuditFinding(assertion_id, reason, referenced_data_snapshot_id), AuditReport(traceable, checked_links, resolved_links, findings).
- DataSnapshot, TraceLink, and AuditReport need to_dict() (the tests call it; this is the approved minimal extension).
- TraceRecorder with record_snapshot(*, snapshot_id, data_source, fetch_timestamp), record_assertion(*, assertion_id, referenced_data_snapshot_id, critical), record_final_decision(*, decision_id, referenced_snapshot_ids), audit(), render_table().
- critical is keyword-only with NO default. No links()/snapshots() accessors.
- link_id is content-derived from (assertion_id, referenced_data_snapshot_id); duplicate link -> TraceError, never overwrite. Duplicate snapshot_id -> TraceError. A second record_final_decision -> TraceError.
- fetch_timestamp must be UTC ISO-8601, tz-aware, zero offset, parseable by datetime.fromisoformat; invalid -> TraceError and not stored.
- record_assertion never drops a link: a dangling snapshot is stored and surfaces as DANGLING_SNAPSHOT in audit().
- audit() audits recorded assertions only; it cannot detect a critical assertion never passed to record_assertion. The module docstring must state this boundary in the phrases the test checks, and the one-snapshot-per-assertion workaround (distinct assertion ids for multi-evidence).
- audit() counts N from recorded critical links and M as resolved links; traceable requires all critical links resolved, at least one final-decision reference, and no findings. Use the exact finding reasons the tests assert (DANGLING_SNAPSHOT, UNKNOWN_FINAL_REFERENCE, NO_FINAL_DECISION, NO_EVIDENCE; others as needed).
- render_table() returns one row per recorded link in insertion order, with keys assertion_id, link_id, critical, referenced_data_snapshot_id, data_source, fetch_timestamp; every cell non-empty.
- In-memory only; no clock, no uuid, no network, no LLM imports. Allowed imports: dataclasses, enum, typing, hashlib, datetime (parsing only), __future__.

Run:
1. `python -m pytest test/offline/test_traceability.py -m offline -q` -> all pass.
2. `python -m pytest test/offline/test_guardrail.py test/offline/test_traceability.py -m offline -q` -> all pass.
3. `python -m pytest -q --continue-on-collection-errors` -> only the 3 pre-existing failures (live_prose, context_budget, termination), no new failures.

STOP at STOP 3 with the full src/trace_recorder.py content and verbatim output. Do not modify tests or any other file. If a test cannot be satisfied without an interface change, stop and report rather than weakening the test."

### Coding Agent

I'll start by reading the required context files.

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\AGENTS.md"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\AGENTS.md, lines 1-95

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\test\\offline\\test_traceability.py"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\test_traceability.py, lines 1-716

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\src\\guardrail.py"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\guardrail.py, lines 1-390

### Coding Agent

Now let me check the surrounding structure and any existing trace_recorder stub.

**Tool call — `glob`**

Input:
```json
{
  "pattern": "src/*.py"
}
```

Result:
```text
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\termination_controller.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\structured_debater.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\guardrail.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\context_assembler.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\trace_recorder.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\__init__.py
```

**Tool call — `glob`**

Input:
```json
{
  "pattern": "test/**/*.py"
}
```

Result:
```text
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\test_termination.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\test_guardrail.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\test_context_budget.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\test_traceability.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\offline\__init__.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\live\test_live_prose.py
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\test\live\__init__.py
```

**Tool call — `shell`**

Input:
```json
{
  "command": "ls src test test/offline 2>&1; python --version"
}
```

Result:
```text
src:
__init__.py
__pycache__
context_assembler.py
guardrail.py
structured_debater.py
termination_controller.py
trace_recorder.py

test:
live
offline

test/offline:
__init__.py
__pycache__
test_context_budget.py
test_guardrail.py
test_termination.py
test_traceability.py
Python 3.14.7

```

### Coding Agent

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\src\\trace_recorder.py"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\trace_recorder.py, lines 1-1

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\src\\__init__.py"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\__init__.py, 0 lines

### Coding Agent

Let me look at the approved architecture decisions and governing docs.

**Tool call — `glob`**

Input:
```json
{
  "pattern": "docs/**/*.md"
}
```

Result:
```text
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\review-memo.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\bug-diary.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\debt-register.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\memory-design.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\trace-matrix.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\invariants.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\evaluation-table.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\evaluation-logbook.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\permission-model.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\option-ledger.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\risk-list.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\runtime-policy-catalog.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\code-governance\verification-constraints.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\code-governance\structural-constraints.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\code-governance\mcp-tool-manifest.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\005-termination-discipline.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\004-hard-guardrail.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\003-evidence-traceability.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\002-structured-debate.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\001-context-budgeting.md
```

**Tool call — `glob`**

Input:
```json
{
  "pattern": "{architecture-blueprint.md,.agent/*,.opencode/*,docs/**/*.yaml,pytest.ini,pyproject.toml,setup.cfg,conftest.py}"
}
```

Result:
```text
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\architecture-blueprint.md
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\pytest.ini
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\ai-use-log.yaml
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\req\requirements.yaml
```

### Coding Agent

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\docs\\architecture\\adr\\003-evidence-traceability.md"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\003-evidence-traceability.md, lines 1-30

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\docs\\code-governance\\structural-constraints.md"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\code-governance\structural-constraints.md, lines 1-24

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\pytest.ini"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\pytest.ini, lines 1-8

### Coding Agent

**Tool call — `grep`**

Input:
```json
{
  "pattern": "TRACE",
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\docs"
}
```

Result:
```text
Found 7 matches
C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\invariants.md:
  Line 10: | INV-TRACE-COMPLETENESS | Every critical assertion is linked to a recorded evidence snapshot | REQ-TRACEABILITY | `TraceRecorder` | offline test: auditor resolves every link | Log gap + surface in review memo |


C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\code-governance\structural-constraints.md:
  Line 13: | Trace recorder | `src/trace_recorder.py` | ADR-003 / REQ-TRACEABILITY | INV-TRACE-COMPLETENESS |


C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\req\requirements.yaml:
  Line 107:   # 3. REQ-TRACEABILITY — evidence-chain traceability (functional)

  Line 109:   - id: REQ-TRACEABILITY

  Line 217:   traceability_requirement: REQ-TRACEABILITY


C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\adr\003-evidence-traceability.md:
  Line 22: - Supports REQ-TRACEABILITY; auditability and renderable trace table.


C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\trace-matrix.md:
  Line 9: | REQ-TRACEABILITY | `TraceRecorder` | offline test: link auditor resolves all | trace-link completeness check |

```

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\docs\\architecture\\invariants.md"
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\architecture\invariants.md, lines 1-13

### Coding Agent

**Tool call — `read`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\docs\\req\\requirements.yaml",
  "offset": 100,
  "limit": 30
}
```

Result: Read file C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\docs\req\requirements.yaml, lines 100-129

**Tool call — `shell`**

Input:
```json
{
  "command": "cat .agent/rules.md 2>/dev/null | head -60; cat .opencode/rules.md 2>/dev/null | head -40"
}
```

Result:
```text
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

(TODO: expand as the project's rules crystallise.)# .opencode/rules.md — Always-On Behavioral Rules (D3)

> Project-level, always-on behavioral rules for the coding agent. **Human-only
> file** — the agent does not edit this.

## Always-on rules
1. Read `AGENTS.md` first; follow the architecture artifact reading order.
2. **Stop for approval before generating code.** Produce an execution plan
   first (traceability, interface contract, scope, testing strategy, steps).
3. **Extend the baseline, never replace it**, unless an ADR authorises.
4. **No non-agentic modification** — all code is produced by the coding agent.
5. **Every change updates `docs/ai-use-log.yaml`** before a PR can merge.
6. Respect authority boundaries: architecture blueprint and covenant
   (`docs/architecture/*`, `.agent/rules.md`) are authoritative; agent
   suggestions are advisory.
7. Run the deterministic offline tests and the full prior suite (zero
   regressions) before declaring work done.
8. Keep module ↔ architectural-element mapping consistent.

(TODO: expand with project-specific rules as they emerge.)
```

### Coding Agent

Now I have the full picture. Let me confirm the current baseline failure state before writing code.

**Tool call — `shell`**

Input:
```json
{
  "command": "python -m pytest test/offline/test_traceability.py -m offline -q 2>&1 | tail -15",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
    from src.trace_recorder import (
E   ImportError: cannot import name 'AuditFinding' from 'src.trace_recorder' (C:\Users\jiu\Desktop\cityu\course\cs5351-SE\project\team-app\src\trace_recorder.py)
============================== warnings summary ===============================
D:\Python\3.14\Lib\site-packages\anyio\pytest_plugin.py:14
  D:\Python\3.14\Lib\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR test/offline/test_traceability.py
!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
1 warning, 1 error in 0.34s

```

### Coding Agent

Baseline confirmed: collection error at the stub. Let me record the pre-existing full-suite failures for a clean comparison later.

**Tool call — `shell`**

Input:
```json
{
  "command": "python -m pytest -q --continue-on-collection-errors 2>&1 | tail -12",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app",
  "timeout": 600000
}
```

Result:
```text
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
ERROR test/offline/test_traceability.py
FAILED test/live/test_live_prose.py::test_faithfulness_relevancy - NotImpleme...
FAILED test/offline/test_context_budget.py::test_context_within_budget - NotI...
FAILED test/offline/test_termination.py::test_terminates_on_repeat - NotImple...
3 failed, 86 passed, 1 warning, 1 error in 0.35s

```

### Coding Agent

Baseline: 86 passed, 3 pre-existing failures + 1 collection error (the stub). Now writing the implementation.

**Tool call — `write`**

Input:
```json
{
  "path": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app\\src\\trace_recorder.py",
  "content": "\"\"\"Evidence-chain trace recorder (REQ-TRACEABILITY, ADR-003).\n\nADR-003 / REQ-TRACEABILITY / INV-TRACE-COMPLETENESS\n\nRecords the evidence chain assertion_id -> referenced_data_snapshot_id ->\ndata_source + fetch_timestamp, and audits a final decision against it. Pure\nand in-memory only: no clock, no uuid, no network, no LLM. Every timestamp is\nsupplied by the caller, and every identity is content-derived, so the same\nrecorded content always produces byte-identical records and reports.\n\nPinned semantics (requirements session + architecture session)\n--------------------------------------------------------------\ncritical    ``record_assertion`` takes ``critical`` as keyword-only with no\n            default. The producing agent must state explicitly whether an\n            assertion is critical; omitting the flag is a ``TypeError``, never\n            a guess.\nlink_id     content-derived from (assertion_id, referenced_data_snapshot_id).\n            Re-recording the same pair is a collision -> ``TraceError``; a\n            recorded link is never overwritten. Likewise a repeated\n            ``snapshot_id`` is rejected, and a second\n            ``record_final_decision`` is rejected.\nTimestamp   ``fetch_timestamp`` must be UTC ISO-8601, timezone-aware, with a\n            zero UTC offset, and parseable by ``datetime.fromisoformat``.\n            Anything else raises ``TraceError`` and is NOT stored, so a later\n            decision citing it stays an unresolved reference.\nDangling    ``record_assertion`` never drops a link. A reference to a snapshot\n            that was never recorded is stored as-is and surfaces as the\n            ``DANGLING_SNAPSHOT`` finding when ``audit()`` runs.\nAudit       ``checked_links`` counts recorded critical links (N);\n            ``resolved_links`` counts those whose snapshot was recorded (M).\n            ``traceable`` requires every critical link resolved, at least one\n            final-decision reference that resolves, and no findings.\nTable       ``render_table()`` returns one row per recorded link, in insertion\n            order, with no empty cells.\n\nFinding reasons (frozen vocabulary)\n-----------------------------------\n``DANGLING_SNAPSHOT``        a recorded assertion cites a snapshot never recorded.\n``UNKNOWN_FINAL_REFERENCE``  the final decision cites a snapshot never recorded.\n``NO_FINAL_DECISION``        no final decision was recorded.\n``NO_EVIDENCE``              the final decision references no snapshot at all.\n``NO_CRITICAL_LINKS``        nothing critical was asserted, so completeness is\n                             unmeasurable; the audit refuses to bless it.\n``EMPTY_FIELD``              an identifier or source/decision field was blank.\n\nAudit boundary -- recorded assertions only (pinned by the reviewer)\n-------------------------------------------------------------------\n``audit()`` audits recorded assertions only. It measures whether each assertion\nthat was given to ``record_assertion`` is resolvable. It can never detect a\ncritical assertion that was never passed to the recorder at all -- nothing in\nthe recorder's memory can testify to a call that did not happen. A critical\nassertion silently omitted by a producing agent therefore leaves NO trace and\nNO finding. Closing that never-called gap needs an interface change (the\nproducing agents must declare their critical assertions up-front) and is\ndeferred to the next ADR.\n\nOne-snapshot-per-assertion workaround\n-------------------------------------\n``link_id`` is derived from (assertion_id, referenced_data_snapshot_id), so one\nassertion id carries exactly one evidence snapshot. An assertion resting on\nseveral pieces of evidence is therefore recorded under distinct assertion ids\n(e.g. ``assert-revenue-growth#1``, ``assert-revenue-growth#2``), one snapshot\neach, and every one of those links is audited separately.\n\"\"\"\n\nfrom __future__ import annotations\n\nimport hashlib\nfrom dataclasses import dataclass\nfrom datetime import datetime\nfrom enum import Enum\nfrom typing import Final\n\n\nclass TraceError(ValueError):\n    \"\"\"A recorder *protocol* fault: a collision, a bad timestamp, bad input.\"\"\"\n\n\nclass FindingReason(str, Enum):\n    \"\"\"Frozen finding vocabulary. Every audit finding names exactly one.\"\"\"\n\n    DANGLING_SNAPSHOT = \"DANGLING_SNAPSHOT\"\n    UNKNOWN_FINAL_REFERENCE = \"UNKNOWN_FINAL_REFERENCE\"\n    NO_FINAL_DECISION = \"NO_FINAL_DECISION\"\n    NO_EVIDENCE = \"NO_EVIDENCE\"\n    NO_CRITICAL_LINKS = \"NO_CRITICAL_LINKS\"\n    EMPTY_FIELD = \"EMPTY_FIELD\"\n\n\n# Pinned reporting order, so a report with several findings is deterministic.\nFINDING_PRECEDENCE: Final[tuple[FindingReason, ...]] = (\n    FindingReason.EMPTY_FIELD,\n    FindingReason.DANGLING_SNAPSHOT,\n    FindingReason.NO_FINAL_DECISION,\n    FindingReason.NO_EVIDENCE,\n    FindingReason.UNKNOWN_FINAL_REFERENCE,\n    FindingReason.NO_CRITICAL_LINKS,\n)\n\n\n# ---------------------------------------------------------------------------\n# Frozen records\n# ---------------------------------------------------------------------------\n\n@dataclass(frozen=True, slots=True)\nclass DataSnapshot:\n    \"\"\"One fetched evidence snapshot: what was read, from where, and when.\"\"\"\n\n    snapshot_id: str\n    data_source: str\n    fetch_timestamp: str\n\n    def to_dict(self) -> dict[str, object]:\n        return {\n            \"snapshot_id\": self.snapshot_id,\n            \"data_source\": self.data_source,\n            \"fetch_timestamp\": self.fetch_timestamp,\n        }\n\n\n@dataclass(frozen=True, slots=True)\nclass TraceLink:\n    \"\"\"One assertion -> evidence edge. ``critical`` is the agent's own flag.\"\"\"\n\n    link_id: str\n    assertion_id: str\n    referenced_data_snapshot_id: str\n    critical: bool\n\n    def to_dict(self) -> dict[str, object]:\n        return {\n            \"link_id\": self.link_id,\n            \"assertion_id\": self.assertion_id,\n            \"referenced_data_snapshot_id\": self.referenced_data_snapshot_id,\n            \"critical\": self.critical,\n        }\n\n\n@dataclass(frozen=True, slots=True)\nclass AuditFinding:\n    \"\"\"One reason the audit failed. A failure, never a warning.\"\"\"\n\n    assertion_id: str\n    reason: str\n    referenced_data_snapshot_id: str\n\n    def to_dict(self) -> dict[str, object]:\n        return {\n            \"assertion_id\": self.assertion_id,\n            \"reason\": self.reason,\n            \"referenced_data_snapshot_id\": self.referenced_data_snapshot_id,\n        }\n\n\n@dataclass(frozen=True, slots=True)\nclass AuditReport:\n    \"\"\"The audit verdict: ``checked_links`` is N, ``resolved_links`` is M.\"\"\"\n\n    traceable: bool\n    checked_links: int\n    resolved_links: int\n    findings: tuple[AuditFinding, ...] = ()\n\n    def to_dict(self) -> dict[str, object]:\n        return {\n            \"traceable\": self.traceable,\n            \"checked_links\": self.checked_links,\n            \"resolved_links\": self.resolved_links,\n            \"findings\": [finding.to_dict() for finding in self.findings],\n        }\n\n\n# ---------------------------------------------------------------------------\n# Internal state: the final decision (not part of the frozen public records)\n# ---------------------------------------------------------------------------\n\n@dataclass(frozen=True, slots=True)\nclass _FinalDecision:\n    decision_id: str\n    referenced_snapshot_ids: tuple[str, ...]\n\n\n# ---------------------------------------------------------------------------\n# Content-derived identity and validation\n# ---------------------------------------------------------------------------\n\ndef _link_id(assertion_id: str, referenced_data_snapshot_id: str) -> str:\n    \"\"\"``link_id`` is a pure function of (assertion_id, snapshot_id).\n\n    No counter, no uuid, no clock -- so the same pair always yields the same\n    id, and a differing pair cannot collide.\n    \"\"\"\n    payload = f\"{assertion_id}\\x00{referenced_data_snapshot_id}\"\n    digest = hashlib.sha256(payload.encode(\"utf-8\")).hexdigest()\n    return f\"tl-{digest[:16]}\"\n\n\ndef _require_text(value: object, field: str) -> str:\n    if not isinstance(value, str) or not value.strip():\n        raise TraceError(f\"{field} must be a non-empty string, got {value!r}\")\n    return value\n\n\ndef _require_utc_iso8601(value: object) -> str:\n    \"\"\"Accept only a tz-aware ISO-8601 timestamp whose UTC offset is zero.\"\"\"\n    text = _require_text(value, \"fetch_timestamp\")\n    try:\n        parsed = datetime.fromisoformat(text)\n    except ValueError as exc:\n        raise TraceError(f\"fetch_timestamp is not ISO-8601: {text!r}\") from exc\n    if parsed.tzinfo is None or parsed.utcoffset() is None:\n        raise TraceError(f\"fetch_timestamp must be timezone-aware: {text!r}\")\n    if parsed.utcoffset().total_seconds() != 0:\n        raise TraceError(f\"fetch_timestamp must be UTC (zero offset): {text!r}\")\n    return text\n\n\n# ---------------------------------------------------------------------------\n# The recorder\n# ---------------------------------------------------------------------------\n\nclass TraceRecorder:\n    \"\"\"Append-only, in-memory evidence-chain recorder.\n\n    Every ``record_*`` call either stores its record or raises ``TraceError``;\n    nothing is silently dropped and nothing is overwritten. Inspection goes\n    through ``render_table()`` and ``audit()`` only.\n    \"\"\"\n\n    def __init__(self) -> None:\n        self._snapshots: dict[str, DataSnapshot] = {}\n        self._links: list[TraceLink] = []\n        self._link_ids: set[str] = set()\n        self._final_decision: _FinalDecision | None = None\n\n    # -- recording ---------------------------------------------------------\n\n    def record_snapshot(\n        self, *, snapshot_id: str, data_source: str, fetch_timestamp: str\n    ) -> DataSnapshot:\n        \"\"\"Record one evidence snapshot; a repeated id is rejected.\n\n        REQ-TRACEABILITY: the validator runs BEFORE anything is stored, so a\n        rejected timestamp leaves the recorder exactly as it was.\n        \"\"\"\n        snapshot_id = _require_text(snapshot_id, \"snapshot_id\")\n        data_source = _require_text(data_source, \"data_source\")\n        fetch_timestamp = _require_utc_iso8601(fetch_timestamp)\n\n        if snapshot_id in self._snapshots:\n            raise TraceError(\n                f\"duplicate snapshot_id: {snapshot_id!r} (already recorded; \"\n                \"evidence is never overwritten)\"\n            )\n\n        snapshot = DataSnapshot(\n            snapshot_id=snapshot_id,\n            data_source=data_source,\n            fetch_timestamp=fetch_timestamp,\n        )\n        self._snapshots[snapshot_id] = snapshot\n        return snapshot\n\n    def record_assertion(\n        self, *, assertion_id: str, referenced_data_snapshot_id: str, critical: bool\n    ) -> TraceLink:\n        \"\"\"Record one assertion -> snapshot link; never drops, never overwrites.\n\n        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. A dangling reference is\n        stored as-is -- it is a failure the audit must surface, not a record\n        the recorder may discard. ``critical`` has no default: the producing\n        agent states it explicitly.\n        \"\"\"\n        assertion_id = _require_text(assertion_id, \"assertion_id\")\n        referenced_data_snapshot_id = _require_text(\n            referenced_data_snapshot_id, \"referenced_data_snapshot_id\"\n        )\n        if not isinstance(critical, bool):\n            raise TraceError(f\"critical must be a bool, got {type(critical).__name__}\")\n\n        link_id = _link_id(assertion_id, referenced_data_snapshot_id)\n        if link_id in self._link_ids:\n            raise TraceError(\n                f\"duplicate link: {link_id} for ({assertion_id!r}, \"\n                f\"{referenced_data_snapshot_id!r}) (already recorded; \"\n                \"links are never overwritten)\"\n            )\n\n        link = TraceLink(\n            link_id=link_id,\n            assertion_id=assertion_id,\n            referenced_data_snapshot_id=referenced_data_snapshot_id,\n            critical=critical,\n        )\n        self._links.append(link)\n        self._link_ids.add(link_id)\n        return link\n\n    def record_final_decision(\n        self, *, decision_id: str, referenced_snapshot_ids: tuple[str, ...] | list[str]\n    ) -> _FinalDecision:\n        \"\"\"Record the one final decision and the snapshots it cites.\n\n        Exactly one final decision per recorder: a second call is a\n        ``TraceError``. References are stored verbatim (deduplicated, order\n        preserved) so an unknown one can be reported by the audit.\n        \"\"\"\n        decision_id = _require_text(decision_id, \"decision_id\")\n        if self._final_decision is not None:\n            raise TraceError(\n                f\"duplicate final decision: {decision_id!r} \"\n                f\"(already recorded {self._final_decision.decision_id!r})\"\n            )\n        if isinstance(referenced_snapshot_ids, str):\n            raise TraceError(\"referenced_snapshot_ids must be a sequence, not a string\")\n\n        refs: list[str] = []\n        for reference in referenced_snapshot_ids:\n            reference = _require_text(reference, \"referenced_snapshot_ids entry\")\n            if reference not in refs:\n                refs.append(reference)\n\n        decision = _FinalDecision(\n            decision_id=decision_id,\n            referenced_snapshot_ids=tuple(refs),\n        )\n        self._final_decision = decision\n        return decision\n\n    # -- inspection --------------------------------------------------------\n\n    def audit(self) -> AuditReport:\n        \"\"\"Walk the recorded chain and report whether it is traceable.\n\n        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. Audits recorded assertions\n        only -- see the module docstring's audit boundary. N (``checked_links``)\n        counts recorded critical links; M (``resolved_links``) counts those\n        whose snapshot was recorded. ``traceable`` requires M == N with N > 0,\n        at least one resolving final-decision reference, and no findings.\n        \"\"\"\n        findings: list[AuditFinding] = []\n\n        # A snapshot with a blank source or timestamp would defeat the chain.\n        for snapshot in self._snapshots.values():\n            if not snapshot.data_source.strip() or not snapshot.fetch_timestamp.strip():\n                findings.append(\n                    AuditFinding(\n                        assertion_id=\"\",\n                        reason=FindingReason.EMPTY_FIELD.value,\n                        referenced_data_snapshot_id=snapshot.snapshot_id,\n                    )\n                )\n\n        checked_links = 0\n        resolved_links = 0\n        for link in self._links:\n            if not link.critical:\n                continue  # non-critical links are optional (storage bound)\n            checked_links += 1\n            if link.referenced_data_snapshot_id in self._snapshots:\n                resolved_links += 1\n            else:\n                findings.append(\n                    AuditFinding(\n                        assertion_id=link.assertion_id,\n                        reason=FindingReason.DANGLING_SNAPSHOT.value,\n                        referenced_data_snapshot_id=link.referenced_data_snapshot_id,\n                    )\n                )\n\n        decision = self._final_decision\n        decision_id = decision.decision_id if decision is not None else \"\"\n        final_references = decision.referenced_snapshot_ids if decision is not None else ()\n\n        if decision is None:\n            findings.append(\n                AuditFinding(\n                    assertion_id=\"\",\n                    reason=FindingReason.NO_FINAL_DECISION.value,\n                    referenced_data_snapshot_id=\"\",\n                )\n            )\n        elif not final_references:\n            findings.append(\n                AuditFinding(\n                    assertion_id=decision_id,\n                    reason=FindingReason.NO_EVIDENCE.value,\n                    referenced_data_snapshot_id=\"\",\n                )\n            )\n\n        for reference in final_references:\n            if reference not in self._snapshots:\n                findings.append(\n                    AuditFinding(\n                        assertion_id=decision_id,\n                        reason=FindingReason.UNKNOWN_FINAL_REFERENCE.value,\n                        referenced_data_snapshot_id=reference,\n                    )\n                )\n\n        if checked_links == 0:\n            # Nothing critical was asserted: completeness is unmeasurable, so\n            # the audit must not bless the run as traceable (fail closed).\n            findings.append(\n                AuditFinding(\n                    assertion_id=decision_id,\n                    reason=FindingReason.NO_CRITICAL_LINKS.value,\n                    referenced_data_snapshot_id=\"\",\n                )\n            )\n\n        traceable = (\n            not findings\n            and checked_links > 0\n            and resolved_links == checked_links\n            and any(reference in self._snapshots for reference in final_references)\n        )\n\n        order = {reason.value: index for index, reason in enumerate(FINDING_PRECEDENCE)}\n        findings.sort(\n            key=lambda finding: (\n                order[finding.reason],\n                finding.assertion_id,\n                finding.referenced_data_snapshot_id,\n            )\n        )\n\n        return AuditReport(\n            traceable=traceable,\n            checked_links=checked_links,\n            resolved_links=resolved_links,\n            findings=tuple(findings),\n        )\n\n    def render_table(self) -> list[dict[str, object]]:\n        \"\"\"One row per recorded link, in insertion order, with no empty cells.\n\n        The row joins the link to its snapshot, so the reviewer sees the\n        citation and its source on the same line. A dangling link prints an\n        explicit placeholder instead of a blank cell.\n        \"\"\"\n        rows: list[dict[str, object]] = []\n        for link in self._links:\n            snapshot = self._snapshots.get(link.referenced_data_snapshot_id)\n            rows.append(\n                {\n                    \"assertion_id\": link.assertion_id,\n                    \"link_id\": link.link_id,\n                    \"critical\": str(link.critical),\n                    \"referenced_data_snapshot_id\": link.referenced_data_snapshot_id,\n                    \"data_source\": snapshot.data_source if snapshot is not None else \"(unresolved)\",\n                    \"fetch_timestamp\": (\n                        snapshot.fetch_timestamp if snapshot is not None else \"(unresolved)\"\n                    ),\n                }\n            )\n        return rows\n"
}
```

Result:
```text
Wrote file successfully: src/trace_recorder.py
```

### Coding Agent

Now Step 1 — the traceability suite:

**Tool call — `shell`**

Input:
```json
{
  "command": "python -m pytest test/offline/test_traceability.py -m offline -q 2>&1 | tail -8",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
  D:\Python\3.14\Lib\site-packages\anyio\pytest_plugin.py:14: PytestRemovedIn10Warning: _pytest.python.CallSpec2 has been renamed to CallSpec.
  The CallSpec2 alias will be removed in pytest 10.
  Update imports to use CallSpec instead.
  See https://docs.pytest.org/en/stable/deprecations.html#callspec2-renamed
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
29 passed, 1 warning in 0.09s

```

### Coding Agent

All 29 pass. Step 2 — traceability + guardrail together:

**Tool call — `shell`**

Input:
```json
{
  "command": "python -m pytest test/offline/test_guardrail.py test/offline/test_traceability.py -m offline -q 2>&1 | tail -4",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
115 passed, 1 warning in 0.22s

```

### Coding Agent

Step 3 — full suite, checking for regressions against the baseline:

**Tool call — `shell`**

Input:
```json
{
  "command": "python -m pytest -q --continue-on-collection-errors 2>&1 | tail -8",
  "timeout": 600000,
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
    from _pytest.python import CallSpec2

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
=========================== short test summary info ===========================
FAILED test/live/test_live_prose.py::test_faithfulness_relevancy - NotImpleme...
FAILED test/offline/test_context_budget.py::test_context_within_budget - NotI...
FAILED test/offline/test_termination.py::test_terminates_on_repeat - NotImple...
3 failed, 115 passed, 1 warning in 0.38s

```

### Coding Agent

Exactly the 3 pre-existing failures, and the baseline collection error is gone (86 → 115 passed). Let me confirm no other file was touched.

**Tool call — `shell`**

Input:
```json
{
  "command": "find . -name \"*.py\" -newer src/guardrail.py -not -path \"*/__pycache__/*\" -print; ls -la src/trace_recorder.py",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
./src/trace_recorder.py
./test/offline/test_guardrail.py
-rw-r--r-- 1 jiu 197609 18488 Nov 24 23:23 src/trace_recorder.py

```

### Coding Agent

**Tool call — `shell`**

Input:
```json
{
  "command": "ls -la --time-style=full-iso test/offline/test_guardrail.py test/offline/test_traceability.py src/guardrail.py src/trace_recorder.py",
  "workdir": "C:\\Users\\jiu\\Desktop\\cityu\\course\\cs5351-SE\\project\\team-app"
}
```

Result:
```text
-rw-r--r-- 1 jiu 197609 15310 2026-11-24 23:21:48.406151800 +0800 src/guardrail.py
-rw-r--r-- 1 jiu 197609 18488 2026-11-24 23:23:43.742241500 +0800 src/trace_recorder.py
-rw-r--r-- 1 jiu 197609 28540 2026-11-24 23:21:51.383472100 +0800 test/offline/test_guardrail.py
-rw-r--r-- 1 jiu 197609 27387 2026-11-24 23:18:48.304934700 +0800 test/offline/test_traceability.py

```

### Coding Agent

STOP 3 reached. Only `src/trace_recorder.py` was written (the `test_guardrail.py` mtime predates my first command; I never wrote to it). No tests, docs, or other files were modified.

## Verbatim output

**1.** `python -m pytest test/offline/test_traceability.py -m offline -q`
```
29 passed, 1 warning in 0.09s
```

**2.** `python -m pytest test/offline/test_guardrail.py test/offline/test_traceability.py -m offline -q`
```
115 passed, 1 warning in 0.22s
```

**3.** `python -m pytest -q --continue-on-collection-errors`
```
=========================== short test summary info ===========================
FAILED test/live/test_live_prose.py::test_faithfulness_relevancy - NotImpleme...
FAILED test/offline/test_context_budget.py::test_context_within_budget - NotI...
FAILED test/offline/test_termination.py::test_terminates_on_repeat - NotImple...
3 failed, 115 passed, 1 warning in 0.38s
```

Baseline before the change was `3 failed, 86 passed, 1 error` — the same 3 failures, plus the collection error from the `TODO implement` stub. That error is gone and 29 tests were added; zero regressions.

## Full `src/trace_recorder.py`

```python
"""Evidence-chain trace recorder (REQ-TRACEABILITY, ADR-003).

ADR-003 / REQ-TRACEABILITY / INV-TRACE-COMPLETENESS

Records the evidence chain assertion_id -> referenced_data_snapshot_id ->
data_source + fetch_timestamp, and audits a final decision against it. Pure
and in-memory only: no clock, no uuid, no network, no LLM. Every timestamp is
supplied by the caller, and every identity is content-derived, so the same
recorded content always produces byte-identical records and reports.

Pinned semantics (requirements session + architecture session)
--------------------------------------------------------------
critical    ``record_assertion`` takes ``critical`` as keyword-only with no
            default. The producing agent must state explicitly whether an
            assertion is critical; omitting the flag is a ``TypeError``, never
            a guess.
link_id     content-derived from (assertion_id, referenced_data_snapshot_id).
            Re-recording the same pair is a collision -> ``TraceError``; a
            recorded link is never overwritten. Likewise a repeated
            ``snapshot_id`` is rejected, and a second
            ``record_final_decision`` is rejected.
Timestamp   ``fetch_timestamp`` must be UTC ISO-8601, timezone-aware, with a
            zero UTC offset, and parseable by ``datetime.fromisoformat``.
            Anything else raises ``TraceError`` and is NOT stored, so a later
            decision citing it stays an unresolved reference.
Dangling    ``record_assertion`` never drops a link. A reference to a snapshot
            that was never recorded is stored as-is and surfaces as the
            ``DANGLING_SNAPSHOT`` finding when ``audit()`` runs.
Audit       ``checked_links`` counts recorded critical links (N);
            ``resolved_links`` counts those whose snapshot was recorded (M).
            ``traceable`` requires every critical link resolved, at least one
            final-decision reference that resolves, and no findings.
Table       ``render_table()`` returns one row per recorded link, in insertion
            order, with no empty cells.

Finding reasons (frozen vocabulary)
-----------------------------------
``DANGLING_SNAPSHOT``        a recorded assertion cites a snapshot never recorded.
``UNKNOWN_FINAL_REFERENCE``  the final decision cites a snapshot never recorded.
``NO_FINAL_DECISION``        no final decision was recorded.
``NO_EVIDENCE``              the final decision references no snapshot at all.
``NO_CRITICAL_LINKS``        nothing critical was asserted, so completeness is
                             unmeasurable; the audit refuses to bless it.
``EMPTY_FIELD``              an identifier or source/decision field was blank.

Audit boundary -- recorded assertions only (pinned by the reviewer)
-------------------------------------------------------------------
``audit()`` audits recorded assertions only. It measures whether each assertion
that was given to ``record_assertion`` is resolvable. It can never detect a
critical assertion that was never passed to the recorder at all -- nothing in
the recorder's memory can testify to a call that did not happen. A critical
assertion silently omitted by a producing agent therefore leaves NO trace and
NO finding. Closing that never-called gap needs an interface change (the
producing agents must declare their critical assertions up-front) and is
deferred to the next ADR.

One-snapshot-per-assertion workaround
-------------------------------------
``link_id`` is derived from (assertion_id, referenced_data_snapshot_id), so one
assertion id carries exactly one evidence snapshot. An assertion resting on
several pieces of evidence is therefore recorded under distinct assertion ids
(e.g. ``assert-revenue-growth#1``, ``assert-revenue-growth#2``), one snapshot
each, and every one of those links is audited separately.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final

class TraceError(ValueError):
    """A recorder *protocol* fault: a collision, a bad timestamp, bad input."""

class FindingReason(str, Enum):
    """Frozen finding vocabulary. Every audit finding names exactly one."""

    DANGLING_SNAPSHOT = "DANGLING_SNAPSHOT"
    UNKNOWN_FINAL_REFERENCE = "UNKNOWN_FINAL_REFERENCE"
    NO_FINAL_DECISION = "NO_FINAL_DECISION"
    NO_EVIDENCE = "NO_EVIDENCE"
    NO_CRITICAL_LINKS = "NO_CRITICAL_LINKS"
    EMPTY_FIELD = "EMPTY_FIELD"

# Pinned reporting order, so a report with several findings is deterministic.
FINDING_PRECEDENCE: Final[tuple[FindingReason, ...]] = (
    FindingReason.EMPTY_FIELD,
    FindingReason.DANGLING_SNAPSHOT,
    FindingReason.NO_FINAL_DECISION,
    FindingReason.NO_EVIDENCE,
    FindingReason.UNKNOWN_FINAL_REFERENCE,
    FindingReason.NO_CRITICAL_LINKS,
)

# ---------------------------------------------------------------------------
# Frozen records
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class DataSnapshot:
    """One fetched evidence snapshot: what was read, from where, and when."""

    snapshot_id: str
    data_source: str
    fetch_timestamp: str

    def to_dict(self) -> dict[str, object]:
        return {
            "snapshot_id": self.snapshot_id,
            "data_source": self.data_source,
            "fetch_timestamp": self.fetch_timestamp,
        }

@dataclass(frozen=True, slots=True)
class TraceLink:
    """One assertion -> evidence edge. ``critical`` is the agent's own flag."""

    link_id: str
    assertion_id: str
    referenced_data_snapshot_id: str
    critical: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "link_id": self.link_id,
            "assertion_id": self.assertion_id,
            "referenced_data_snapshot_id": self.referenced_data_snapshot_id,
            "critical": self.critical,
        }

@dataclass(frozen=True, slots=True)
class AuditFinding:
    """One reason the audit failed. A failure, never a warning."""

    assertion_id: str
    reason: str
    referenced_data_snapshot_id: str

    def to_dict(self) -> dict[str, object]:
        return {
            "assertion_id": self.assertion_id,
            "reason": self.reason,
            "referenced_data_snapshot_id": self.referenced_data_snapshot_id,
        }

@dataclass(frozen=True, slots=True)
class AuditReport:
    """The audit verdict: ``checked_links`` is N, ``resolved_links`` is M."""

    traceable: bool
    checked_links: int
    resolved_links: int
    findings: tuple[AuditFinding, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "traceable": self.traceable,
            "checked_links": self.checked_links,
            "resolved_links": self.resolved_links,
            "findings": [finding.to_dict() for finding in self.findings],
        }

# ---------------------------------------------------------------------------
# Internal state: the final decision (not part of the frozen public records)
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class _FinalDecision:
    decision_id: str
    referenced_snapshot_ids: tuple[str, ...]

# ---------------------------------------------------------------------------
# Content-derived identity and validation
# ---------------------------------------------------------------------------

def _link_id(assertion_id: str, referenced_data_snapshot_id: str) -> str:
    """``link_id`` is a pure function of (assertion_id, snapshot_id).

    No counter, no uuid, no clock -- so the same pair always yields the same
    id, and a differing pair cannot collide.
    """
    payload = f"{assertion_id}\x00{referenced_data_snapshot_id}"
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"tl-{digest[:16]}"

def _require_text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TraceError(f"{field} must be a non-empty string, got {value!r}")
    return value

def _require_utc_iso8601(value: object) -> str:
    """Accept only a tz-aware ISO-8601 timestamp whose UTC offset is zero."""
    text = _require_text(value, "fetch_timestamp")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TraceError(f"fetch_timestamp is not ISO-8601: {text!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise TraceError(f"fetch_timestamp must be timezone-aware: {text!r}")
    if parsed.utcoffset().total_seconds() != 0:
        raise TraceError(f"fetch_timestamp must be UTC (zero offset): {text!r}")
    return text

# ---------------------------------------------------------------------------
# The recorder
# ---------------------------------------------------------------------------

class TraceRecorder:
    """Append-only, in-memory evidence-chain recorder.

    Every ``record_*`` call either stores its record or raises ``TraceError``;
    nothing is silently dropped and nothing is overwritten. Inspection goes
    through ``render_table()`` and ``audit()`` only.
    """

    def __init__(self) -> None:
        self._snapshots: dict[str, DataSnapshot] = {}
        self._links: list[TraceLink] = []
        self._link_ids: set[str] = set()
        self._final_decision: _FinalDecision | None = None

    # -- recording ---------------------------------------------------------

    def record_snapshot(
        self, *, snapshot_id: str, data_source: str, fetch_timestamp: str
    ) -> DataSnapshot:
        """Record one evidence snapshot; a repeated id is rejected.

        REQ-TRACEABILITY: the validator runs BEFORE anything is stored, so a
        rejected timestamp leaves the recorder exactly as it was.
        """
        snapshot_id = _require_text(snapshot_id, "snapshot_id")
        data_source = _require_text(data_source, "data_source")
        fetch_timestamp = _require_utc_iso8601(fetch_timestamp)

        if snapshot_id in self._snapshots:
            raise TraceError(
                f"duplicate snapshot_id: {snapshot_id!r} (already recorded; "
                "evidence is never overwritten)"
            )

        snapshot = DataSnapshot(
            snapshot_id=snapshot_id,
            data_source=data_source,
            fetch_timestamp=fetch_timestamp,
        )
        self._snapshots[snapshot_id] = snapshot
        return snapshot

    def record_assertion(
        self, *, assertion_id: str, referenced_data_snapshot_id: str, critical: bool
    ) -> TraceLink:
        """Record one assertion -> snapshot link; never drops, never overwrites.

        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. A dangling reference is
        stored as-is -- it is a failure the audit must surface, not a record
        the recorder may discard. ``critical`` has no default: the producing
        agent states it explicitly.
        """
        assertion_id = _require_text(assertion_id, "assertion_id")
        referenced_data_snapshot_id = _require_text(
            referenced_data_snapshot_id, "referenced_data_snapshot_id"
        )
        if not isinstance(critical, bool):
            raise TraceError(f"critical must be a bool, got {type(critical).__name__}")

        link_id = _link_id(assertion_id, referenced_data_snapshot_id)
        if link_id in self._link_ids:
            raise TraceError(
                f"duplicate link: {link_id} for ({assertion_id!r}, "
                f"{referenced_data_snapshot_id!r}) (already recorded; "
                "links are never overwritten)"
            )

        link = TraceLink(
            link_id=link_id,
            assertion_id=assertion_id,
            referenced_data_snapshot_id=referenced_data_snapshot_id,
            critical=critical,
        )
        self._links.append(link)
        self._link_ids.add(link_id)
        return link

    def record_final_decision(
        self, *, decision_id: str, referenced_snapshot_ids: tuple[str, ...] | list[str]
    ) -> _FinalDecision:
        """Record the one final decision and the snapshots it cites.

        Exactly one final decision per recorder: a second call is a
        ``TraceError``. References are stored verbatim (deduplicated, order
        preserved) so an unknown one can be reported by the audit.
        """
        decision_id = _require_text(decision_id, "decision_id")
        if self._final_decision is not None:
            raise TraceError(
                f"duplicate final decision: {decision_id!r} "
                f"(already recorded {self._final_decision.decision_id!r})"
            )
        if isinstance(referenced_snapshot_ids, str):
            raise TraceError("referenced_snapshot_ids must be a sequence, not a string")

        refs: list[str] = []
        for reference in referenced_snapshot_ids:
            reference = _require_text(reference, "referenced_snapshot_ids entry")
            if reference not in refs:
                refs.append(reference)

        decision = _FinalDecision(
            decision_id=decision_id,
            referenced_snapshot_ids=tuple(refs),
        )
        self._final_decision = decision
        return decision

    # -- inspection --------------------------------------------------------

    def audit(self) -> AuditReport:
        """Walk the recorded chain and report whether it is traceable.

        REQ-TRACEABILITY / INV-TRACE-COMPLETENESS. Audits recorded assertions
        only -- see the module docstring's audit boundary. N (``checked_links``)
        counts recorded critical links; M (``resolved_links``) counts those
        whose snapshot was recorded. ``traceable`` requires M == N with N > 0,
        at least one resolving final-decision reference, and no findings.
        """
        findings: list[AuditFinding] = []

        # A snapshot with a blank source or timestamp would defeat the chain.
        for snapshot in self._snapshots.values():
            if not snapshot.data_source.strip() or not snapshot.fetch_timestamp.strip():
                findings.append(
                    AuditFinding(
                        assertion_id="",
                        reason=FindingReason.EMPTY_FIELD.value,
                        referenced_data_snapshot_id=snapshot.snapshot_id,
                    )
                )

        checked_links = 0
        resolved_links = 0
        for link in self._links:
            if not link.critical:
                continue  # non-critical links are optional (storage bound)
            checked_links += 1
            if link.referenced_data_snapshot_id in self._snapshots:
                resolved_links += 1
            else:
                findings.append(
                    AuditFinding(
                        assertion_id=link.assertion_id,
                        reason=FindingReason.DANGLING_SNAPSHOT.value,
                        referenced_data_snapshot_id=link.referenced_data_snapshot_id,
                    )
                )

        decision = self._final_decision
        decision_id = decision.decision_id if decision is not None else ""
        final_references = decision.referenced_snapshot_ids if decision is not None else ()

        if decision is None:
            findings.append(
                AuditFinding(
                    assertion_id="",
                    reason=FindingReason.NO_FINAL_DECISION.value,
                    referenced_data_snapshot_id="",
                )
            )
        elif not final_references:
            findings.append(
                AuditFinding(
                    assertion_id=decision_id,
                    reason=FindingReason.NO_EVIDENCE.value,
                    referenced_data_snapshot_id="",
                )
            )

        for reference in final_references:
            if reference not in self._snapshots:
                findings.append(
                    AuditFinding(
                        assertion_id=decision_id,
                        reason=FindingReason.UNKNOWN_FINAL_REFERENCE.value,
                        referenced_data_snapshot_id=reference,
                    )
                )

        if checked_links == 0:
            # Nothing critical was asserted: completeness is unmeasurable, so
            # the audit must not bless the run as traceable (fail closed).
            findings.append(
                AuditFinding(
                    assertion_id=decision_id,
                    reason=FindingReason.NO_CRITICAL_LINKS.value,
                    referenced_data_snapshot_id="",
                )
            )

        traceable = (
            not findings
            and checked_links > 0
            and resolved_links == checked_links
            and any(reference in self._snapshots for reference in final_references)
        )

        order = {reason.value: index for index, reason in enumerate(FINDING_PRECEDENCE)}
        findings.sort(
            key=lambda finding: (
                order[finding.reason],
                finding.assertion_id,
                finding.referenced_data_snapshot_id,
            )
        )

        return AuditReport(
            traceable=traceable,
            checked_links=checked_links,
            resolved_links=resolved_links,
            findings=tuple(findings),
        )

    def render_table(self) -> list[dict[str, object]]:
        """One row per recorded link, in insertion order, with no empty cells.

        The row joins the link to its snapshot, so the reviewer sees the
        citation and its source on the same line. A dangling link prints an
        explicit placeholder instead of a blank cell.
        """
        rows: list[dict[str, object]] = []
        for link in self._links:
            snapshot = self._snapshots.get(link.referenced_data_snapshot_id)
            rows.append(
                {
                    "assertion_id": link.assertion_id,
                    "link_id": link.link_id,
                    "critical": str(link.critical),
                    "referenced_data_snapshot_id": link.referenced_data_snapshot_id,
                    "data_source": snapshot.data_source if snapshot is not None else "(unresolved)",
                    "fetch_timestamp": (
                        snapshot.fetch_timestamp if snapshot is not None else "(unresolved)"
                    ),
                }
            )
        return rows
```

## Implementation notes

- **Allowed imports only** — `hashlib`, `dataclasses`, `datetime`, `enum`, `typing`, `__future__`. Confirmed by the AST hygiene test.
- **Validate-then-store** — in both `record_snapshot` and `record_assertion`, every check runs before mutation, so a rejected call leaves state byte-identical (T7, duplicate tests).
- **`critical` passthrough** — `render_table` emits `str(link.critical)`, which is exactly what the test helper parses back (`row["critical"] == "True"`).
- **Two additions beyond the brief, both fail-closed:**
  - `NO_CRITICAL_LINKS` — a recorder with zero critical links would otherwise report `traceable=True` on a vacuous 0 == 0. The audit refuses that. No test requires the opposite.
  - `EMPTY_FIELD` — guarded defensively; unreachable via the public API since `_require_text` already rejects blanks.
- **`link_id`** is `tl-` + first 16 hex chars of SHA-256 over `assertion_id \x00 snapshot_id` — stable, non-numeric, 19 chars, collision-safe by construction.
- **Determinism** — findings are sorted by a frozen `FINDING_PRECEDENCE` then by identifiers, so `to_dict()` comparison across instances (T8) holds regardless of insertion quirks.
- **Scope** — `record_final_decision` returns a private `_FinalDecision` rather than a new public frozen record, keeping the public surface exactly as specified. No `links()`/`snapshots()` accessors exist; inspection goes through `render_table()` and `audit()`.

One governance note for you, not something I changed: `.opencode/rules.md` rule 5 requires every change to update `docs/ai-use-log.yaml` before a PR can merge. That file is outside my write scope, so it needs a human edit before merge.

---

> **[POST-SESSION REVIEWER NOTE — gate result and interface drift]** The reviewer independently reran the acceptance commands: `test_traceability.py -m offline` → **29 passed**; both new suites → **115 passed**; `pytest -q --continue-on-collection-errors` → **3 failed** (the pre-existing live/context-budget/termination stubs), no new failures. No test was edited. Two follow-ups are carried into session 05: (a) `record_final_decision` returns the private `_FinalDecision` although the frozen interface says `-> None` — an interface drift to correct or explicitly record; (b) `docs/ai-use-log.yaml` needs the human entry required by `.opencode/rules.md` rule 5.
