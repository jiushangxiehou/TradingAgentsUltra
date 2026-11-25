# Bug Diary (D4)

> One entry per significant bug found during the supervised build. The entries
> below are from the guardrail/trace integration and the CI work; they are the
> defects that changed a test or an invariant story. Owners are noted where the
> work was mine (CUI Haoyu).

## Bug-001: Guardrail adapter raised on a non-dict final state

- **Class:** correctness / robustness
- **Symptom:** A final state that was not a mapping could raise in the decision
  adapter instead of producing a gate verdict.
- **Reproduction:** Call `build_decision(final_state=<non-dict>, ...)`; the
  adapter attempted dictionary access and failed.
- **Root cause:** The adapter assumed the graph always returns a `dict`.
- **Fix:** Normalize a non-dict state to `{}`; the rating, intent and cash still
  reach the frozen guardrail, so the verdict remains fail-closed.
- **Invariant gap exposed:** A gate that can raise is a gate that can be
  skipped. Added the negative test in `test/offline/test_integration_decision.py`.
- **Note:** Found in the supervised integration session; fixed by OpenCode,
  reviewed by CUI Haoyu.

## Bug-002: Trace capture double-installed its patches

- **Class:** correctness / evidence integrity
- **Symptom:** Under a `with` block, data-capture patches could be installed
  twice; restore order inverted and the second capture wrapped the first.
- **Reproduction:** Enter the capture twice (or leave one open across a second
  run) and inspect the patched functions after the block.
- **Root cause:** `begin_capture` was not idempotent across nested/with usage.
- **Fix:** Make capture enter/finish idempotent and finish any previous capture
  before opening a new one; regression test in the trace suite.
- **Invariant gap exposed:** `INV-TRACE-COMPLETENESS` — evidence must survive a
  re-run without silently stacking wrappers.
- **Note:** Found during the trace-recorder review; fixed by OpenCode, reviewed
  by CUI Haoyu.

## Bug-003: Capture faults were silently dropped

- **Class:** observability / evidence integrity
- **Symptom:** A fault inside a data-capture observer disappeared; the run
  looked clean but the evidence set was incomplete.
- **Reproduction:** Inject a failing observer; the trace completed with no
  record of the failure.
- **Root cause:** Exceptions were swallowed instead of journaled.
- **Fix:** Add a `capture_errors` journal and surface it in the sidecar/trace;
  a capture failure no longer looks like a successful capture.
- **Invariant gap exposed:** `INV-TRACE-COMPLETENESS`; absence of evidence must
  be distinguishable from evidence of absence.
- **Note:** Found in the human review of the trace adapter; fixed and tested.

## Bug-004: No-data marker matched unrelated prose

- **Class:** correctness / evidence integrity
- **Symptom:** A data-unavailable placeholder could be detected anywhere in a
  text, including a sentence that merely mentioned “unavailable”.
- **Reproduction:** Feed a tool result containing the word away from the
  placeholder position; the recorder misclassified it as no-data evidence.
- **Root cause:** The check used an unanchored substring match.
- **Fix:** Anchor the placeholder at the start of the rendered block and add a
  negative test.
- **Invariant gap exposed:** `INV-TRACE-COMPLETENESS`; evidence labels must
  describe the actual data path.
- **Note:** Found while testing the G1 run-level evidence set.

## Bug-005: Trace construction only caught `TraceError`

- **Class:** correctness / resilience
- **Symptom:** An unexpected exception while building the trace could fail the
  run after the decision had been made.
- **Reproduction:** Force a non-`TraceError` exception in `build_trace`; the
  guarded graph propagated it.
- **Root cause:** The attest path caught only the project’s own `TraceError`.
- **Fix:** Catch `Exception`, record `trace_error`, and leave the rating
  untouched. Evidence is not allowed to change a decision.
- **Invariant gap exposed:** rating integrity under trace failure; covered by
  the graph tests.
- **Note:** Fixed in `src/integration/governed_graph.py`; reviewed by
  CUI Haoyu.

## Bug-006: Bad guardrail configuration raised instead of failing closed

- **Class:** security / correctness
- **Symptom:** An invalid limits configuration could raise out of the gate.
- **Reproduction:** Pass a non-finite limit to the evaluator; a
  `GuardrailError` escaped the integration path.
- **Root cause:** The integration did not translate configuration errors into a
  rejection.
- **Fix:** `config_error_result` produces the Hold/REVIEW-HOLD result and a
  note; the gate never passes by accident.
- **Invariant gap exposed:** `INV-GUARDRAIL-ZERO-ESCAPE`.
- **Note:** Added to the gate tests; owned by CUI Haoyu.

## Bug-007: CI could not import `src` from the pytest console script

- **Class:** CI / regression
- **Symptom:** `ModuleNotFoundError: No module named 'src'` on GitHub Actions
  while the same tests passed locally.
- **Reproduction:** Run the `pytest` console script from the repository root in
  CI; the root was not on `sys.path`.
- **Root cause:** `python -m pytest` and the console script differ in path
  setup; the workflow used the console script.
- **Fix:** Add `pythonpath = .` to `pytest.ini`; CI passed.
- **Invariant gap exposed:** none; process/CI reliability.
- **Note:** Found in the feature-c CI run and fixed by CUI Haoyu.

## Bug-008: AI-use-log gate blocked a style-only source change

- **Class:** process / CI
- **Symptom:** The `ai-use-log` gate failed after ruff-style changes in `src/`
  without a new log entry.
- **Reproduction:** Push a `src/` style change with no `docs/ai-use-log.yaml`
  change; the gate exits 1.
- **Root cause:** The gate correctly enforces the rule, but the change was not
  logged.
- **Fix:** Add entry 008 (root-layout/CI/style changes); CI passed.
- **Invariant gap exposed:** none; the gate is working as designed. The log is
  now part of the co-evolution loop.
- **Note:** Fixed by CUI Haoyu; this is evidence that the gate is not merely
  decorative.

<!-- Append new bugs below. Every bug that weakens an invariant must update
docs/architecture/invariants.md and add a regression test. -->
