# TR1 P1 chart audit

Audited after the independent exit replay and before freezing round 1. The deterministic manifest is
`chart_audit_p1.csv`; the full contact sheet is `charts_p1/audit_contact_sheet.svg` (with a local PNG rendering for
visual inspection).

Six positive and six negative SPLIT outcomes were selected evenly across each outcome distribution rather than by
hand. The winners span +0.029R to +16.424R and include both pre- and post-graduation exits. The losers span -1.265R
to approximately flat and include four full-position stops plus two paths that took the +1R partial before the
runner gave back profit.

Visual checks performed on all twelve panels:

- the black vertical entry marker follows the opening impulse and pullback rather than preceding confirmation;
- the initial stop is on the protected side of entry and no plotted structure candidate depends on an unclosed
  bar;
- the +1R partial line is on the executable profit side for buys and sells;
- trades marked `partial_taken=False` stop before reaching the partial line;
- trades marked `partial_taken=True` cross the partial line before their final exit;
- M5 structure candidates appear only after entry; M15 candidates do not replace the M5 trail before the +3R
  graduation condition;
- the six winning exits include genuine giveback as intended by a runner, while the losing cases are not relabelled
  or removed;
- every red exit marker matches the saved raw-tick exit time and is after the black entry marker.

No chart contradicted the written rule. The large +16.424R London winner is visibly exceptional and is the main
reason the concentration warning remains in `EXIT_FINDINGS_P1.md`; it is retained, not treated as representative.
