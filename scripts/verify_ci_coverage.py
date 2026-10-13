"""Fail closed unless isolated CI workers complete all discovered tests exactly once."""
import json
from pathlib import Path


def verify_coverage(records, *, count, revision, native=False):
    if len(records) != count or {record['index'] for record in records} != set(range(count)):
        raise ValueError('Require exactly one completed record for every shard.')
    discovered = records[0]['discovered']
    if not discovered or len(discovered) != len(set(discovered)):
        raise ValueError('Invalid full discovery identities.')
    selected = []
    for record in records:
        if (record['schema'] != 1 or record['count'] != count or record['revision'] != revision
                or record['discovered'] != discovered or record['successful'] is not True
                or record['executed'] != len(record['selected'])):
            raise ValueError('Incomplete, failed or inconsistent shard evidence.')
        if native and record['skipped']:
            raise ValueError('Native regression must execute without skips.')
        if not set(record['skipped']) <= set(record['selected']):
            raise ValueError('Skip evidence is outside the selected tests.')
        selected.extend(record['selected'])
    if len(selected) != len(set(selected)) or set(selected) != set(discovered):
        raise ValueError('Shards must cover complete discovery exactly once.')
    owners = {}
    for record in records:
        for identity in record['selected']:
            name = identity.rsplit('.', 1)[0]
            if name in owners and owners[name] != record['index']:
                raise ValueError('A test class was split across workers.')
            owners[name] = record['index']
    return len(discovered)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Verify complete successful CI shard coverage.')
    parser.add_argument('directory', type=Path)
    parser.add_argument('--count', type=int, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--native', action='store_true')
    args = parser.parse_args()
    records = [json.loads(path.read_text(encoding='utf-8')) for path in sorted(args.directory.rglob('coverage.json'))]
    total = verify_coverage(records, count=args.count, revision=args.revision, native=args.native)
    print(f'PASS: {total} discovered tests covered exactly once across {args.count} successful shards.')
