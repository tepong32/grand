from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import BytesIO
import json
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from django.utils import timezone

from accounting.cash_classifications import checksum
from . import form1_signed_copies as signed


class Form1SignedValidationTests(SimpleTestCase):
    """Input/provenance checks without substituting for two-store integration."""

    def setUp(self):
        self.today = timezone.localtime().date()
        package = SimpleNamespace(proposal_id=1, fund_id=2, department_id=3,
            payload={'assembly': {'payload': {'members': [{'entity_key':'entity-A'}, {'entity_key':'entity-B'}]}}})
        preparation = SimpleNamespace(package=package, payload={'signatories': {
            role: {'valid_from':'2000-01-01','valid_to':None} for role in signed.signing.ROLES}})
        self.copy = SimpleNamespace(preparation=preparation,released_at=timezone.now()-timedelta(days=3))
        self.dates = {entity: {role:self.today-timedelta(days=1) for role in signed.signing.ROLES}
                      for entity in ('entity-A','entity-B')}

    def facts(self, dates):
        return signed._facts(self.copy,dates,self.today,'Synthetic recipient','TEST handover','TEST location',self.today)

    def test_each_entity_requires_its_own_complete_signing_functions(self):
        result = self.facts(self.dates)
        self.assertEqual(set(result['signed_dates']),{'entity-A','entity-B'})
        missing_entity = deepcopy(self.dates); missing_entity.pop('entity-B')
        with self.assertRaises(ValidationError): self.facts(missing_entity)
        missing_role = deepcopy(self.dates); missing_role['entity-B'].pop('chief_executive')
        with self.assertRaises(ValidationError): self.facts(missing_role)

    def test_approval_and_designation_dates_are_checked_for_each_entity(self):
        dates = deepcopy(self.dates)
        dates['entity-A']['chief_executive'] = self.today
        self.assertEqual(self.facts(dates)['signed_dates']['entity-A']['chief_executive'],self.today.isoformat())
        dates['entity-B']['accountant'] = self.today
        with self.assertRaises(ValidationError): self.facts(dates)
        self.copy.preparation.payload['signatories']['treasurer']['valid_to'] = (self.today-timedelta(days=2)).isoformat()
        with self.assertRaises(ValidationError): self.facts(self.dates)

    def test_missing_date_is_an_explicit_unverified_declaration_not_a_completed_signature(self):
        dates = deepcopy(self.dates); dates['entity-B']['treasurer'] = None
        facts = self.facts(dates)
        self.assertIs(facts['signed_dates']['entity-B']['treasurer'],None)
        self.assertFalse(signed._complete_dates(facts))
        self.assertTrue(signed._complete_dates(self.facts(self.dates)))

    def test_predecessor_link_requires_actual_original_archive_bytes(self):
        head = self.predecessor()
        data = head.archive
        self.assertEqual(signed._previous(head,self.copy)['archive_sha256'],sha256(data).hexdigest())
        head.archive = b'changed predecessor bytes'
        with self.assertRaises(ValidationError): signed._previous(head,self.copy)

    def predecessor(self):
        public_id = uuid4()
        payload = dict(schema=1,kind='form1_final_issue',identity=dict(
            public_id=str(public_id),proposal_id=1,fund_id=2,department_id=3,version=1),
            reference='Synthetic independently issued original')
        envelope = dict(payload=payload,payload_checksum=checksum(payload))
        buffer = BytesIO()
        with ZipFile(buffer,'w') as archive:
            archive.writestr('issuance.json',json.dumps(envelope,ensure_ascii=False,sort_keys=True,
                separators=(',',':')).encode('utf-8'))
        data = buffer.getvalue()
        return SimpleNamespace(proposal_id=1,fund_id=2,department_id=3,payload=payload,
            payload_checksum=envelope['payload_checksum'],archive=data,archive_checksum=sha256(data).hexdigest(),
            public_id=public_id,version=1)

    def test_predecessor_row_identity_and_version_must_match_original_issue(self):
        for field,value in [('version',2),('public_id',uuid4())]:
            with self.subTest(field=field):
                head = self.predecessor()
                setattr(head,field,value)
                with self.assertRaises(ValidationError): signed._previous(head,self.copy)

    def test_rehashed_predecessor_payload_must_match_archived_issuance(self):
        head = self.predecessor()
        head.payload['reference'] = head.payload['reference'].replace('original','modified')
        head.payload_checksum = checksum(head.payload)
        with self.assertRaises(ValidationError): signed._previous(head,self.copy)
