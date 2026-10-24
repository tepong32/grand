"""Partition complete Django discovery by test class on isolated CI workers."""
import json
import os
from pathlib import Path

from django.test.runner import DiscoverRunner, iter_test_cases


# Reviewed 2026-10-24 after the accepted security classes changed complete discovery.
# Keep Form1 intake on worker 6; a later inventory change must be reviewed again.
FORM1_INTAKE_ORIGINAL_OWNER = 0


def partition(tests, index, count):
    if not 0 <= index < count or count < 1:
        raise ValueError('Require 0 <= shard index < shard count.')
    identities = [test.id() for test in tests]
    if not identities or len(identities) != len(set(identities)):
        raise ValueError('Complete discovery must contain distinct test identities.')
    classes = sorted({identity.rsplit('.', 1)[0] for identity in identities})
    if count > len(classes):
        raise ValueError('Shard count exceeds discovered test classes.')
    owners = {name: position % count for position, name in enumerate(classes)}
    # Measured v172 load: keep this whole class off the other heavy Budget
    # classes. Indices are zero-based and shared by SQLite and native MySQL.
    intake_class = 'budget.test_form1_package_intake.Form1PackageIntakeTests'
    if intake_class in owners:
        if count != 8 or owners[intake_class] != FORM1_INTAKE_ORIGINAL_OWNER:
            raise ValueError(
                "Review the Form1 intake reassignment: require eight shards and "
                f"original owner {FORM1_INTAKE_ORIGINAL_OWNER}."
            )
        owners[intake_class] = 6
    return [test for test in tests if owners[test.id().rsplit('.', 1)[0]] == index]


class ShardedDiscoverRunner(DiscoverRunner):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.shard_index = int(os.environ['GRAND_CI_SHARD_INDEX'])
        self.shard_count = int(os.environ['GRAND_CI_SHARD_COUNT'])
        if (self.parallel not in (0, 1) or self.failfast or self.keepdb or self.tags
                or self.exclude_tags or self.test_name_patterns
                or self.pattern not in (None, 'test*.py') or self.top_level):
            raise ValueError('CI coverage requires complete sequential discovery within each shard.')

    def build_suite(self, test_labels=None, **kwargs):
        if test_labels:
            raise ValueError('CI shards require full discovery, without test labels.')
        tests = list(iter_test_cases(super().build_suite(test_labels, **kwargs)))
        selected = partition(tests, self.shard_index, self.shard_count)
        self.coverage = dict(schema=1, index=self.shard_index, count=self.shard_count,
            revision=os.environ.get('GITHUB_SHA', ''),
            discovered=[test.id() for test in tests], selected=[test.id() for test in selected])
        self.log(f'Shard {self.shard_index + 1}/{self.shard_count}: {len(selected)} of {len(tests)} tests; whole classes retained.')
        return self.test_suite(selected)

    def run_suite(self, suite, **kwargs):
        result = super().run_suite(suite, **kwargs)
        self.coverage.update(executed=result.testsRun, successful=result.wasSuccessful(),
            skipped=[test.id() for test, reason in result.skipped])
        destination = Path(os.environ['GRAND_CI_COVERAGE_PATH'])
        destination.parent.mkdir(parents=True, exist_ok=True)
        # One worker owns one file. Refuse to replace previous run evidence.
        with destination.open('x', encoding='utf-8') as stream:
            json.dump(self.coverage, stream, indent=2)
        if result.testsRun != len(self.coverage['selected']):
            raise RuntimeError('Shard did not complete every selected test.')
        return result
