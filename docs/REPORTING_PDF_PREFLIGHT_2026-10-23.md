# Reporting PDF preflight input handling

Status: local development after checkpoint209. CONTINUE.md owns actual command
results and checkpoint/publication status. Finance remains **NO-GO**; no deployment,
production operations, template acceptance or formal Accounting/LGU approval.

## Demonstrated defect

An8,329-byte synthetic PDF has a readable cross-reference table and opens with
the pinned pypdf6.21.2 reader. Accessing its pages traverses an excessively deep
page tree and raises the real `LimitReachedError` at depth101 beyond the default100.
A self-referencing page tree likewise opens, then raises `PdfReadError` on traversal.
Neither fixture changes parser configuration or requires a large workload.

`reporting.mappers.inspect_pdf_template` handled construction errors but inspected
pages, mappings and geometry afterward. The authenticated preflight view catches
`TemplateMappingError`; these lazy parser exceptions escaped as HTTP500. The
regression reproduced500 instead of the existing302 redirect/error-message flow.
The separate signed Form1 return parser already handles its complete page-count
inspection after the checkpoint209 dependency follow-up; it is unchanged here.

The [upstream error documentation](https://pypdf.readthedocs.io/en/stable/modules/errors.html)
identifies both errors under `PyPdfError`, and notes that damaged PDFs can also
raise other exceptions. Installed6.21.2 `_doc_common.py` / `_configuration.py` and
the real fixtures establish the exact lazy traversal/default-depth behavior above.
No assertion is made that every malformed file or exception is covered.

## Bounded repair

Preserve the existing reader-construction handler. Wrap the subsequent inspection
of encryption/page presence, mapped page selection, rotation and geometry in a
known-`PyPdfError` handler, translating it to the existing safe diagnostic:
“The uploaded PDF could not be opened safely.” The existing atomic preflight
service still records a checksum and validation only after inspection succeeds.

Existing `TemplateMappingError` diagnostics are not swallowed: absent mappings,
encrypted/rotated pages, out-of-range page numbers and out-of-bounds coordinates
retain their actionable messages. No parser limit is relaxed, no catch-all is
added around mapper or database logic, and no automatic retry/approval is created.

Authorization and owning-office checks still run before reading the reference.
Preflight remains distinct from independent preview approval, fidelity acceptance,
promotion and activation. Prior templates, issued report bytes and source history
are retained. No model, migration, routing, permission, accounting recipe, financial
calculation, reference-file relocation or source rewrite is introduced.

## Regression scope and evidence

Three methods extend the existing Reporting test class without changing inherited
test identities, bases, decorators or original bodies:

- A real lazy depth-limit failure through authenticated POST/redirect/GET, unchanged
  candidate mappings/validation/approval, retained original report/template/bytes,
  and a separate valid replacement that passes preflight without approval/activation.
- A real cyclic-page failure, anonymous/operator/foreign-office denial, direct
  service authority checks and retained unvalidated candidate state.
- A normal out-of-range coordinate diagnostic followed by a permitted correction.

Initial red: two tests,2.814s,exit1; the new HTTP regression fails500 vs302, while
the unchanged recognized-advance starter check passes. Both disposable aliases
are cleaned. `.tmp/pdf-preflight-red.log` and the red test source are preserved.
Redirect assertions read the existing message only once rather than consuming it
through a preliminary automatic follow; the HTTP expectation is unchanged.

Affected/dependent Reporting, template promotion, Finance-report and signed-Form1
tests PASS:95/95,zero skips,587.451s,exit0 and both disposable aliases destroyed.
The raw log/verified95 unique identities and exact runtime/environment are retained.
Static review preserves all34 original test bodies and confirms only the known-error
boundary/import/comment alter the mapper. No database or validation gate is weakened.
Raw commands/results and subsequent checkpoint gates belong to CONTINUE.md.
CONTINUE.md records the owner's later deferral of remaining full runs for a
feature-branch checkpoint and pause. Required primary-publication CI remains
pending; the checkpoint does not establish a complete native-suite pass.
This is input-error handling evidence, not official form or production readiness.
