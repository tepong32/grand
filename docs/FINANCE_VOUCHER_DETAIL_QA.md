# Voucher detail source parity and browser QA

2026-09-09, v0.7.55 verified. This is synthetic implemented-control evidence, not an official-form or LGU acceptance record.

The isolated default/Finance database pair and browser fixture are described in [My Work browser QA](FINANCE_MY_WORK_BROWSER_QA.md). Both preparer and independent reviewer sessions use that disposable local fixture; no operational voucher was changed.

## Reproduced findings

- The unapproved preparer saw a validation form and next-task banner even though the real validation queue excluded self-review. One regression test produced two failed assertions in 3.190 seconds. The page now consumes the existing Accounting validation selector for both displays; the service remains authoritative.
- Browser styles rendered the compatibility notice as white on almost white and the reviewer banner as white on pale blue. Scoped notice colors now use dark text. The pinned workbook shows its title/version instead of a raw model-object label.
- At 320px, uncontained Accounting/signature tables and fixed-width reason textareas expanded the document beyond the viewport. Evidence tables now have named keyboard-focusable scrolling regions, and source form controls fit the card.

## Browser results

- PASS: the preparer sees routing and its separately permitted amendment/correction controls, without an invitation to validate its own DV. The independent Accounting reviewer sees the validation form and main-step banner.
- PASS: the preparer and reviewer pages each measured 305px document width within a 320px viewport after repair. Wide evidence remains available inside its scrolling region rather than expanding the page.
- PASS: ArrowRight scrolled the focused Accounting compatibility table by 40px; the named region had visible keyboard focus with a 3px outline.
- PASS: checked notice colors are rgb(52,58,64) on rgb(248,249,250), and reviewer-banner rgb(8,66,152) on rgb(207,226,255). Desktop screenshots were inspected after the repair. No new console errors appeared on the checked fixture navigations.
- The first two focused runs were intentionally stopped while successive browser checks found table and textarea overflow. They are not counted as passing runs. Final executable source was fixed before the final focused/dependency runs.
- OPEN: the return form offers stage-incompatible targets; FIN-GAP-028 tracks the next source-page repair.

## Screenshots

- [Preparer desktop](../output/playwright/finance-voucher-detail/preparer-desktop.png)
- [Reviewer desktop](../output/playwright/finance-voucher-detail/reviewer-desktop.png)
- [Preparer at 320px](../output/playwright/finance-voucher-detail/preparer-320.png)
- [Reviewer at 320px](../output/playwright/finance-voucher-detail/reviewer-320.png)
- [Keyboard evidence scrolling](../output/playwright/finance-voucher-detail/evidence-keyboard-scroll.png)

All 77 focused voucher tests passed in 46.346 seconds. All 84 My Work/operations/signature dependency tests passed in 56.615 seconds. System, migration-drift, compilation and diff checks passed. Full regression is not planned for this isolated source-page selector reuse and scoped template presentation change; existing mutation services, permissions, models and source selectors are unchanged. The preceding complete project gate passed 674 tests in v0.7.53. Wider workflow, browser-engine and actual device/accessibility acceptance remains separate.
