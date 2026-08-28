# Department Internal How-Tos

GRAND's Internal How-To layer gives employees contextual operating guidance without assigning tutorials to named users or freezing instructions to a predecessor. Any authenticated employee with at least one published guide visible for the current department and permissions sees a floating `?` button on normal GRAND pages.

## In-page behavior

Clicking `?` opens a non-modal help window above the current page. There is no backdrop or focus trap, so the employee can continue using the underlying form, register, or transaction while reading the steps. The panel is keyboard accessible, closes with Escape, adapts to a mobile bottom sheet, respects reduced-motion preferences, and remembers its open/closed state and selected guide locally for that department/user/browser.

Guides whose named-route pattern matches the current page appear first and carry a **Relevant here** label. Other published guides available to the same department/role remain browsable in the panel. A step can link to a named GRAND workspace when no route arguments are needed.

## Visibility and succession rule

Visibility is evaluated on every request from:

1. the employee profile's **current** assigned department;
2. the guide's `Published` state;
3. the guide's optional `app_label.codename` permission; and
4. its optional named-route patterns for contextual priority.

The guide has no user assignment field. Reassigning an employee immediately removes the old department's guides and exposes only the new department's eligible guides. Removing a role permission immediately removes the role-specific guide. A successor with the same department and permission sees the appropriate guide automatically.

Step completion is a private record keyed to the actual user, guide step, and department snapshot. It is not copied to a successor and does not grant access to the guide. Old completion remains retained as historical personal progress but is inaccessible when the guide is no longer visible under the employee's current department/role.

## Publishing governance

Authorized content managers use **Departments → Internal How-Tos** in Django Admin. Non-superusers are limited to their currently assigned department and require `departments.manage_internal_how_tos`.

1. Create version 1 as `Draft` and define its summary, optional required permission, optional page patterns, order, and steps.
2. Add ordered steps with the instruction, expected result, caution, and optional named action route.
3. Review the guide with the department process owner, then change it to `Published`.
4. Published content and steps are immutable. To update instructions, retire the old guide and publish a new version under the same department/slug.
5. Guides and completions are retained rather than deleted.

Route patterns use named Django routes and shell-style wildcards—for example `accounting:opening_*`, `vouchers:*`, or `department_dashboard`. They do not authorize the linked action; the destination view still enforces its own permission and department boundary.

## Finance starter guides

`python manage.py seed_internal_howtos` idempotently creates Finance guides for departments whose name/slug identifies Accounting/Finance, Budget, or Treasury. `configure_finance_roles` also invokes the seed, and the post-migration hook seeds existing matching departments. A definition at the same or an older version preserves the published guide. A reviewed newer definition retires the old published guide and publishes its successor without changing old steps or moving private progress.

The initial set covers:

- governed Finance configuration;
- opening-balance staging/correction, independent approval, posting/reconciliation, and portable export;
- manual JEV preparation and independent posting/correction;
- Accounting DV preparation and wet-signature/custody routing;
- requesting-office transaction-specific payable preparation and independent Accounting readiness review;
- Budget case initiation/certification; and
- Treasury check preparation, cancellation/replacement, advice, and release.

These steps describe GRAND-implemented controls and explicitly retain the shadow/UAT and local-acceptance limits. Later F3–F11 slices should add or version department/role guides alongside each accepted workflow, template, exception, and export.

## Acceptance checks

Tests must prove published-state filtering, current-department isolation, permission filtering, page relevance, immediate reassignment behavior, private per-user completion, successor non-inheritance, protected completion endpoints, immutable published versions, responsive non-modal markup, and repeatable seeding.
