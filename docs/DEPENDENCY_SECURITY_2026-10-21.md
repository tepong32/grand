# Local checkpoint dependency audit — 2026-10-21

The combined office-output checkpoint stopped before commit when the required
`python -m pip_audit -r requirements.txt` returned1: nine advisories in two pinned
packages. `pip check` passed; that does not replace a vulnerability audit.

- certifi2024.8.30: PYSEC-2026-4320; audit reports2026.10.19 as fixed.
- Pillow12.3.0: CVE-2026-112895,112400,112397,112896,112897,112395,112404,112899;
  audit reports13.0.0 as fixed. These identifiers are the audit receipt, not a
  claim that every ID was independently reconciled with an upstream advisory.

The original failure is retained privately in `batch-dependency-audit.log`.
Requirements now pin the reported fixed versions for validation. This is the
bounded security-gate follow-up, not a broad dependency refresh or gate exception.
No Python/runtime-policy upgrade is required: upstream's
[Python support matrix](https://pillow.readthedocs.io/en/stable/installation/python-support.html)
includes Python3.11 for Pillow13, and
[certifi release metadata](https://pypi.org/project/certifi/2026.10.19/)
supports Python>=3.7. The
[Pillow13 release notes](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html)
describe security fixes and API removals. Repository search found no direct uses
of the removed `get_child_images`, `_show`, ImageCms product fields or Makernote
APIs; framework/third-party compatibility still requires actual regression.

Use a new isolated Python3.11 environment; preserve the earlier environment and
all its retained test evidence. Repeat dependency audit, framework/migration and
CI-coverage checks, then the full applicable regression. Until those actual
receipts pass, this is an unvalidated dependency candidate and checkpoint remains
uncommitted. Do not ignore advisories or infer image/evidence security from
package version alone. Hosted CI, publication, operations and formal acceptance
remain separate; Finance NO-GO and no deployment.

CONTINUE.md owns current command results and the active process handle.

October21 candidate preflight: a fresh Python3.11.5 environment installed the pinned
requirements/dev requirements successfully. `pip check`, `pip_audit` (no known
vulnerabilities), isolated Django/migration checks and CI-coverage unit tests pass.
The original failure remains retained. That full3,161-case SQLite attempt was
interrupted without a terminal receipt/summary; it is not a passing full run.
No checkpoint, CI or publication pass is claimed.

## October22 fresh audit failure and bounded PDF follow-up

The resumed preflight passed `pip check` but failed `pip_audit`: five advisories
in pypdf6.19.0. The original log is retained at
`.tmp/checkpoint209-shards/prechecks-nbhvfoom/dependency-audit.log`.
CVE-2026-113792/113793 report6.20.1 as fixed;113795/113794 report6.20.0;
113786 reports6.21.1. These are audit-reported IDs/fix versions, not an assertion
that every advisory was individually reconciled upstream.

The candidate now pins pypdf6.21.2. Its
[official release metadata](https://pypi.org/project/pypdf/6.21.2/)
confirms October21 release and Python>=3.9, including3.11. The
[upstream changelog](https://pypdf.readthedocs.io/en/stable/meta/CHANGELOG.html)
records additional limits on repeated file loads and standard xref tables in
6.21.2, following stream/tree parsing limits and JPEG-plugin restriction in
6.20–6.21.1. The
[maintainer's JPEG advisory](https://github.com/py-pdf/pypdf/security/advisories/GHSA-5hx5-vpf9-5wcv)
independently confirms113786 and the6.21.1 fix. Use6.21.2 to include the newly
published security fixes as well as the audit-reported minimums.

Source inspection covers Reporting PDF template inspection/overlays and Budget
package, unsigned-copy and returned signed-copy parsing. They use PdfReader,
PdfWriter, pages, append/add_page, merge_page and write. Existing files/history
are not regenerated. No financial rule is changed. This
three-pin security follow-up still requires fresh audit and full SQLite/native
regression in a new isolated environment. Earlier environments and failed logs
stay intact; no ignored advisories, weakened parsing or gate exception.

The6.21.2 xref-size guard raises `LimitReachedError`, which is outside
`PdfReadError`. Inspection found the Budget returned-copy parser did not catch
that exception. An authenticated regression using a tiny PDF with an impossible
xref count reproduced HTTP500 instead of the existing409 validation response
(`.tmp/batch-pdf-limit-red.log`: one failure,50.759s). The bounded compatibility
fix maps this exact known exception to the existing readable-PDF ValidationError;
it does not raise/disable parser limits or change ownership, approvals or posting.
The regression also requires unchanged prior bytes/audit/journals and a permitted
valid retry with no automatic review or issuance. Green PASS:1/1 in61.088s,
exit0 with both-store cleanup; exact red/green hashes are recorded privately in
`.tmp/batch-pdf-limit-regression.json`. Fresh five-check preflight also passes,
including no known dependency advisories. Final local full validation now
passes:SQLite2,923 passed/239 native-only skips;MySQL3,162 passed/zero skips,
with exact complete coverage, both-store cleanup and owned-server shutdown.
The separate mocked Telegram gate passes5/5. CONTINUE.md owns command/receipt
paths and local checkpoint state; hosted CI/publication and acceptance remain
unperformed. Failed/interrupted attempts and earlier environments are retained.
