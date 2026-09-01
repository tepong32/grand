# GRAND production Docker and Render preparation

Status: the reproducible container, production settings, static-file build, process health endpoint, and environment contract are implemented. No Render service, production database, domain, disk, scheduler, or secret has been created by this repository change.

## Deployment shape

GRAND runs as one Django web application with two external MySQL databases:

- `default` stores platform identity, department, reporting, custody, voucher, and shared workflow data;
- `finance` stores the separately routed Accounting and Budget authority data.

The checked-in `Dockerfile` uses Python 3.11, installs the pinned Python dependencies and a native MySQL client, builds collected static assets, runs as the non-root `grand` user, and starts Gunicorn on Render's `PORT`. Application and access logs go to stdout/stderr. The image does not contain `.env`, SQLite databases, uploaded media, generated exports, backups, local logs, or showcase output.

WhiteNoise serves release-built static assets. GRAND uses compression-only storage because the installed AdminLTE distribution contains legacy CSS references to optional sourcemaps it does not ship; enabling manifest URL rewriting currently makes `collectstatic` fail and must not be forced by inventing those package files.

Current platform behavior should be rechecked before deployment against Render's [Docker](https://render.com/docs/docker), [health check](https://render.com/docs/health-checks), [persistent disk](https://render.com/docs/disks), and [cron job](https://render.com/docs/cronjobs) documentation.

## Required decisions before creating the service

The LGU/deployment owner must confirm:

1. the exact Render workspace, service name, plan, region, branch, custom domain, and deploy approval route;
2. the production-compatible MySQL hosts and independently provisioned `default` and `finance` databases;
3. whether filesystem media/exports remain on one Render persistent disk or move to approved object storage;
4. how restricted database backups reach durable off-host storage and how TraceSync or another custody process retrieves them;
5. approved secret ownership/rotation, email and Google OAuth production configuration;
6. monitoring, alert recipients, maintenance window, rollback owner, and accepted downtime implications;
7. approved backup retention, RPO/RTO, restore witnesses, and recovery-rehearsal schedule.

Do not commit `render.yaml` with guessed plan, disk size, database, region, or schedule values. Create that blueprint only after these choices are approved.

## Build and local container check

Build the same Linux image Render will use:

```text
docker build --tag grand:production .
```

Copy `.env.example` to a non-repository secret file, replace every placeholder, and run the container with a disposable MySQL environment. Do not point an unreviewed local container at production.

```text
docker run --rm --env-file <approved-secret-file> --publish 10000:10000 grand:production
```

Then request `http://127.0.0.1:10000/healthz/`. The endpoint is deliberately minimal and does not expose database names or credentials. It proves that the web process can answer; database migrations, login, role access, Finance cross-store flows, and report generation remain separate release checks.

## Render web-service configuration

Create a Docker web service from the approved repository and branch. Use the checked-in Dockerfile and its default startup command. Configure:

- health check path: `/healthz/`;
- environment variables: all applicable values from `.env.example` using Render's secret/environment controls;
- `GRAND_ALLOWED_HOSTS`: the exact custom and Render hostnames;
- `GRAND_CSRF_TRUSTED_ORIGINS`: only additional trusted HTTPS origins, if required;
- `RENDER_EXTERNAL_HOSTNAME`: supplied by Render and automatically admitted by production settings;
- the main database through `DEFAULT_DB_*` and Finance through `FINANCE_DB_*`;
- runtime roots below `/app/runtime` only when an approved disk is mounted there.

Legacy `TEST_DB_NAME`, `TEST_DB_UN`, and `TEST_DB_PW` main-store variables and `FINANCE_DB_UN`/`FINANCE_DB_PW` remain temporary compatibility fallbacks, but new deployments should use the explicit names in `.env.example`.

Production settings fail fast when the secret key or either database identity is absent. Connections use configurable connect/read/write timeouts, connection health checks, and a finite connection age. HTTPS redirect, secure cookies, proxy SSL recognition, and an initial one-hour HSTS window are enabled. Increase HSTS and enable subdomains/preload only after every affected hostname is verified; those settings can make mistakes difficult to reverse.

## Persistent runtime files

By default, Render filesystems are ephemeral. GRAND currently writes three materially different runtime trees:

- `/app/runtime/media` — uploaded or generated application files;
- `/app/runtime/exports` — user-requested TraceSync-ready report/transaction artifacts;
- `/app/runtime/backups` — restricted database recovery sets.

If filesystem storage is retained, mount an approved persistent disk at `/app/runtime` and set the three environment roots accordingly. Keep permissions and off-host handling different even though the directories share a mount. A disk is attached to one service instance, prevents horizontal scaling, and disables zero-downtime deploys; the deployment owner must accept that tradeoff or implement approved shared object storage before cutover.

Never mount runtime storage over `/app`, `/app/staticfiles`, or the image source. Static files belong to the release image. Never expose the backup directory through Django media/static URLs.

## Migrations and initial setup

Migrate both stores before routing a new release to users. On a paid Render service, use an approved pre-deploy command because it runs against the external databases and does not require the runtime disk:

```text
python manage.py migrate --noinput --settings=src.settings.prod && python manage.py migrate --database=finance --noinput --settings=src.settings.prod
```

The exact command and rollback window must be reviewed for each release. Back up both stores first, confirm backward compatibility when zero-downtime deployment is expected, and never assume a successful schema command proves the application workflow.

Run idempotent role/report/how-to seed commands only during an authorized initial deployment or versioned operational change. Record who ran them and review their output.

## Scheduled work boundary

Do not install or start a cron daemon inside the web container. Invoke idempotent Django management commands as explicit platform jobs.

Render cron jobs cannot access a persistent disk. This has important consequences:

- database-only work such as approved leave-credit accrual can use a discrete job after its timezone and idempotency behavior are accepted;
- scheduled report generation must not run on an ephemeral cron instance while report outputs depend on filesystem storage;
- `backup_databases` must not publish to an ephemeral cron filesystem and report success.

Before scheduling reports or backups, choose and implement either an approved shared/object-storage backend or a dedicated worker/off-host publication design. The web service must not expose a public backup trigger or download endpoint. See [database backup and recovery](DATABASE_BACKUP.md).

## Release verification

For every candidate image:

1. run `python -m pip check`;
2. run Django checks and migration-drift detection under development settings;
3. run `collectstatic --noinput` under production settings with non-secret validation placeholders;
4. run `python manage.py check --deploy --settings=src.settings.prod` and review the intentionally staged HSTS warnings/settings;
5. build the Docker image from a clean context;
6. run the container as its configured non-root user and confirm `/healthz/`;
7. run the full automated test suite against both test stores;
8. inspect the image/context to confirm local databases, `.env`, media, exports, and backups are absent;
9. on an isolated release environment, migrate both stores and exercise login, department boundaries, one complete Finance lineage, static/media delivery, an export, and backup command failure/success handling;
10. complete the witnessed restore and field-acceptance gates already recorded in the Finance roadmap.

## Truthful readiness boundary

Repository and container validation mean **deployable preparation**, not production acceptance. GRAND is not production-ready on Render until real infrastructure choices are approved, secrets and databases are provisioned, persistent/off-host storage is proven, both stores are migrated and restored in rehearsal, LGU controls reconcile, and named owners approve cutover and rollback.
