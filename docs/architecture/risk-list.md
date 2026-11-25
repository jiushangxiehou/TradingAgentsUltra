# Risk List (optional)

> Assumptions that could become defects, with review triggers.

| Assumption / risk | Why it might break | Review trigger |
|-------------------|--------------------|----------------|
| Guardrail limits (10% / cash) are safe for all asset types | Crypto / leverage books differ | Any measured false-rejection; new asset type test |
| Compaction preserves constraints | Hard to prove in general | Faithfulness < bound on a probe set |
| Structured debate converges within cap | Some tickers need more rounds | Divergence still high at cap |
| Trace link storage stays bounded | Many critical assertions | Storage growth precedent; adjust critical classification |