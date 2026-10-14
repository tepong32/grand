"""Regression checks for complete coverage and fail-closed CI aggregation."""
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from scripts.ci_test_runner import partition, ShardedDiscoverRunner
from scripts.verify_ci_coverage import verify_coverage


class Case:
    def __init__(self, identity):
        self.identity = identity

    def id(self):
        return self.identity


class ShardCoverageTests(unittest.TestCase):
    def setUp(self):
        self.tests = [Case(name) for name in ('app.Z.test_b', 'app.A.test_b', 'app.A.test_a', 'app.B.test_a')]
        self.records = [dict(schema=1, index=index, count=2, revision='candidate',
            discovered=[test.id() for test in self.tests],
            selected=[test.id() for test in partition(self.tests, index, 2)],
            successful=True, skipped=[]) for index in range(2)]
        for record in self.records:
            record['executed'] = len(record['selected'])

    def test_complete_ordered_classes_and_successful_coverage(self):
        self.assertEqual(verify_coverage(self.records, count=2, revision='candidate', native=True), 4)
        self.assertEqual(self.records[0]['selected'], ['app.Z.test_b', 'app.A.test_b', 'app.A.test_a'])

    def test_missing_duplicate_failed_short_or_wrong_revision_record_rejected(self):
        variants = [self.records[:1], [self.records[0], self.records[0]]]
        for key, value in [('successful', False), ('executed', 0), ('revision', 'other'), ('count', 3), ('schema', 2)]:
            records = deepcopy(self.records)
            records[0][key] = value
            variants.append(records)
        for records in variants:
            with self.subTest(records=records), self.assertRaises(ValueError):
                verify_coverage(records, count=2, revision='candidate')

    def test_omitted_repeated_or_split_class_tests_rejected(self):
        for selected in [[], ['app.A.test_b'], ['app.A.test_b', 'app.B.test_a']]:
            records = deepcopy(self.records)
            records[1]['selected'] = selected
            records[1]['executed'] = len(selected)
            with self.subTest(selected=selected), self.assertRaises(ValueError):
                verify_coverage(records, count=2, revision='candidate')
        records = deepcopy(self.records)
        records[0]['selected'].remove('app.A.test_a')
        records[1]['selected'].append('app.A.test_a')
        for record in records:
            record['executed'] = len(record['selected'])
        with self.assertRaises(ValueError):
            verify_coverage(records, count=2, revision='candidate')

    def test_native_skip_and_invalid_partition_rejected(self):
        records = deepcopy(self.records)
        records[0]['skipped'] = ['app.A.test_a']
        self.assertEqual(verify_coverage(records, count=2, revision='candidate'), 4)
        with self.assertRaises(ValueError):
            verify_coverage(records, count=2, revision='candidate', native=True)
        for index, count, tests in [(-1,2,self.tests), (2,2,self.tests), (0,0,self.tests), (0,4,self.tests), (0,1,[]), (0,1,self.tests+self.tests)]:
            with self.subTest(index=index, count=count), self.assertRaises(ValueError):
                partition(tests, index, count)

    def test_runner_accepts_sequential_defaults_and_rejects_filtered_or_retained_execution(self):
        with patch.dict(os.environ, GRAND_CI_SHARD_INDEX='0', GRAND_CI_SHARD_COUNT='2'):
            runner = ShardedDiscoverRunner(verbosity=0)
            self.assertEqual((runner.shard_index, runner.shard_count), (0, 2))
            with self.assertRaises(ValueError):
                runner.build_suite(['app.tests'])
            for options in [dict(parallel=2), dict(failfast=True), dict(keepdb=True),
                    dict(tags={'limited'}), dict(exclude_tags={'excluded'}),
                    dict(test_name_patterns=['test_one']), dict(pattern='test_one.py')]:
                with self.subTest(options=options), self.assertRaises(ValueError):
                    ShardedDiscoverRunner(verbosity=0, **options)

    def test_actual_django_command_defaults_allow_complete_discovery(self):
        from django.core.management.commands.test import Command
        command = Command()
        command.test_runner = 'scripts.ci_test_runner.ShardedDiscoverRunner'
        defaults = vars(command.create_parser('manage.py', 'test').parse_args([]))
        with patch.dict(os.environ, GRAND_CI_SHARD_INDEX='0', GRAND_CI_SHARD_COUNT='2'):
            runner = ShardedDiscoverRunner(**defaults)
            self.assertEqual(runner.pattern, 'test*.py')

    def intake_partition_tests(self):
        classes = ['app.A', 'app.B', 'app.C',
            'budget.test_form1_package_intake.Form1PackageIntakeTests',
            *['other.Class' + str(index).zfill(2) for index in range(12)]]
        # Interleave class members and reverse class discovery order: assignment
        # must be deterministic without sorting the selected test sequence.
        return [Case(name + method) for method in ('.test_b', '.test_a')
                for name in reversed(classes)]

    def test_only_intake_class_moves_from_index_three_to_six(self):
        tests = self.intake_partition_tests()
        identities = [test.id() for test in tests]
        classes = sorted({name.rsplit('.', 1)[0] for name in identities})
        original = {name: position % 8 for position, name in enumerate(classes)}
        intake = 'budget.test_form1_package_intake.Form1PackageIntakeTests'
        self.assertEqual(original[intake], 3)
        records = []
        for index in range(8):
            selected = [test.id() for test in partition(tests, index, 8)]
            expected = [name for name in identities
                        if (6 if name.rsplit('.', 1)[0] == intake
                            else original[name.rsplit('.', 1)[0]]) == index]
            self.assertEqual(selected, expected)
            reversed_selected = [test.id() for test in partition(list(reversed(tests)), index, 8)]
            self.assertEqual(reversed_selected, list(reversed(selected)))
            records.append(dict(schema=1, index=index, count=8, revision='candidate',
                discovered=identities, selected=selected, executed=len(selected),
                successful=True, skipped=[]))
        self.assertEqual(verify_coverage(records, count=8, revision='candidate', native=True), len(tests))

    def test_intake_reassignment_rejects_changed_shard_count(self):
        for count in (1, 2, 3, 6, 7, 9, 16):
            for index in range(count):
                with self.subTest(count=count, index=index), self.assertRaisesRegex(ValueError, 'reassignment'):
                    partition(self.intake_partition_tests(), index, count)

    def test_intake_reassignment_rejects_changed_original_owner(self):
        tests = [Case('app.Added.test_new'), *self.intake_partition_tests()]
        for index in range(8):
            with self.subTest(index=index), self.assertRaisesRegex(ValueError, 'original owner 3'):
                partition(tests, index, 8)
