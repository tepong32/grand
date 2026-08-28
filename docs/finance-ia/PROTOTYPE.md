# F1.1 synthetic prototype review

Open the [clickable prototype](prototype/index.html) in a browser. It is a static, no-network artifact with synthetic data; switching roles demonstrates information shaping, not authenticated security enforcement.

Reviewed captures: [desktop Budget overview](../../output/playwright/finance-f1-ia/overview-desktop.png) and [320-pixel shared case](../../output/playwright/finance-f1-ia/case-mobile.png). Both contain synthetic values only.

## What it demonstrates

- one Finance landing page with stable navigation;
- role-shaped Overview and My Work content;
- a shared case header, authority chain, responsible office, next gate, and complete-cycle timeline;
- permission-aware action visibility in the synthetic scenario;
- authorized-search concepts, filters, result labels, and empty state;
- explicit case phase, task state, artifact status, exception, and shadow/UAT labels;
- responsive desktop/mobile navigation and keyboard-operable controls.

It deliberately does not implement models, permissions, balances, posting, numbering, notification delivery, or official output. Buttons marked `Prototype` update only the demonstration state.

## Review script

1. Start as `Budget approver`; confirm the Overview names fiscal year/mode and the primary queue is Budget work.
2. Open `My Work`, switch between Ready and Waiting, and inspect the visible action/gate on each task.
3. Open case `GF-2026-00418`; verify one stable reference exposes separate appropriation, allotment, obligation, payable, accounting, and cash concepts.
4. Move through the timeline filter and confirm corrections/custody would remain append-only events.
5. Switch to `Accounting maker`, then `Treasury releaser`; verify the same case remains but actions and queue copy change.
6. Switch to `Auditor / UAT viewer`; verify action buttons disappear and the read-only context is stated in text.
7. Search for `GF-2026-00418` and filter by phase; confirm results identify object type, status object, office, fund, fiscal year, and safe summary.
8. Review at wide and 320 CSS-pixel viewports using keyboard navigation and 200% zoom.

## Capture findings

Record unclear labels, missing role distinctions, unsafe search fields, route assumptions, responsive failures, and status disagreements as `DEC-###` entries in the [decision log](../finance-discovery/DECISION_LOG.md). Acceptance must name the role/office, scenario, viewport/assistive method, result, conditions, prototype commit, and evidence ID.
