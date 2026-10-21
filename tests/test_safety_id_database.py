"""Synthetic Safety ID readiness checks. Only run against a disposable local test DB."""
import concurrent.futures
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

import psycopg
from werkzeug.security import check_password_hash

import app as application
from activation_manager import PostgresActivationRepository


def disposable_database():
    url = os.environ.get('DATABASE_URL', '')
    parsed = urlparse(url)
    name = parsed.path.lstrip('/')
    if parsed.hostname not in {'localhost', '127.0.0.1'} or 'test' not in name:
        raise unittest.SkipTest('A disposable localhost test database is required')
    return url


class SafetyIdDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = disposable_database()
        with patch.object(application, 'DATABASE_URL', cls.url):
            application.init_db()
        cls.repository = PostgresActivationRepository(cls.url)
        cls.repository.ensure_schema()

    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(application, 'DATABASE_URL', self.url).start()
        patch.object(application, 'log_scan').start()
        patch.object(application, 'send_full_alert', return_value=True).start()
        patch.object(application, 'TWILIO_ACCOUNT_SID', 'test-only-sid').start()
        patch.object(application, 'TWILIO_AUTH_TOKEN', 'test-only-token').start()
        patch.object(application, 'TWILIO_PHONE_NUMBER', '+12025550199').start()
        self.sms = patch.object(application, 'Client').start()
        self.client = application.app.test_client()
        self.record = self.repository.generate(1).records[0]
        self.band = self.record['band_id']
        self.code = self.record['activation_code']

    def payload(self, **overrides):
        return dict(bandId=self.band, activationCode=self.code, firstName='Synthetic',
                    lastName='Owner', email='owner@example.test', phone='202-555-0100',
                    profileType='Adult', pin='7391', emergencyContacts='202-555-0101',
                    emergencyEmails='helper@example.test', **overrides)

    def activate(self):
        response = self.client.post('/api/activate', json=self.payload())
        self.assertEqual(response.status_code, 200, response.get_json())

    def row(self):
        with psycopg.connect(self.url) as conn:
            return conn.execute('SELECT full_name, pin_hash, emergency_contacts, emergency_emails FROM members WHERE band_id=%s', (self.band,)).fetchone()

    def authorize(self):
        with self.client.session_transaction() as sess:
            sess['profile_edit_band_id'] = self.band
            sess['profile_edit_expires'] = 4102444800

    def request_sms(self):
        response = self.client.post('/api/profile/request-code', json={'bandId': self.band})
        self.assertEqual(response.status_code, 200, response.get_json())
        message = self.sms.return_value.messages.create.call_args.kwargs
        self.assertEqual(message['to'], '+12025550100')
        return re.search(r'code is (\d{6})', message['body']).group(1)

    def verify(self, code):
        return self.client.post('/api/profile/verify-code', json={'bandId': self.band, 'code': code})

    def test_inventory_card_matches_database_and_claim_creates_profile(self):
        self.assertEqual(self.repository.records_for_print(band_id=self.band)[0]['activation_code'], self.code)
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
        card = self.client.get('/admin/activation-codes/print', query_string={'band_id': self.band})
        self.assertEqual(card.status_code, 200)
        self.assertIn(self.code.encode(), card.data)
        self.assertIn(f'/activate/{self.band}'.encode(), card.data)
        self.activate()
        name, hashed, phones, emails = self.row()
        self.assertEqual(name, 'Synthetic Owner')
        self.assertNotEqual(hashed, '7391')
        self.assertTrue(check_password_hash(hashed, '7391'))
        self.assertEqual((phones, emails), ('+12025550101', 'helper@example.test'))
        with psycopg.connect(self.url) as conn:
            self.assertTrue(conn.execute('SELECT claimed AND claimed_at IS NOT NULL FROM activation_codes WHERE band_id=%s', (self.band,)).fetchone()[0])

    def test_wrong_unknown_rotated_and_claimed_codes(self):
        payload = self.payload(); payload['activationCode'] = 'WRONGCODE'
        self.assertEqual(self.client.post('/api/activate', json=payload).status_code, 403)
        payload['bandId'] = 'EB999999999'; self.assertEqual(self.client.post('/api/activate', json=payload).status_code, 404)
        self.repository.rotate_unclaimed(self.band)
        self.assertEqual(self.client.post('/api/activate', json=self.payload()).status_code, 403)
        self.code = self.repository.records_for_print(band_id=self.band)[0]['activation_code']
        self.activate()
        self.assertEqual(self.client.post('/api/activate', json=self.payload()).status_code, 409)
        self.assertFalse(self.repository.assign(self.band, 'Another store', ''))
        with self.assertRaises(ValueError): self.repository.rotate_unclaimed(self.band)

    def test_populated_profile_is_not_overwritten(self):
        with psycopg.connect(self.url) as conn:
            conn.execute('INSERT INTO members(band_id,full_name) VALUES (%s,%s)', (self.band, 'Existing synthetic owner'))
        self.assertEqual(self.client.post('/api/activate', json=self.payload()).status_code, 409)
        self.assertEqual(self.row()[0], 'Existing synthetic owner')

    def test_concurrent_claims_have_one_winner(self):
        def claim(first):
            payload = self.payload(); payload['firstName'] = first
            return application.app.test_client().post('/api/activate', json=payload).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(claim, ['First', 'Second'])), [200, 409])
        self.assertIn(self.row()[0], ['First Owner', 'Second Owner'])

    def test_profile_updates_public_scan_and_pin_privacy(self):
        self.activate(); self.authorize()
        update = dict(fullName='Updated Synthetic Owner', phone='2025550100', medicalNotes='PRIVATE-SYNTHETIC-NOTE',
                      condition='Public synthetic condition', instructions='Call caregiver', pin='8462',
                      emergencyContacts='2025550102', emergencyEmails='updated@example.test')
        self.assertEqual(self.client.put('/api/profile/me', json=update).status_code, 200)
        self.assertTrue(check_password_hash(self.row()[1], '8462'))
        for path in (f'/{self.band}', f'/customer/{self.band}'):
            public = self.client.get(path)
            self.assertEqual(public.status_code, 200)
            self.assertIn(b'Updated Synthetic Owner', public.data)
            self.assertIn(b'Public synthetic condition', public.data)
            self.assertNotIn(b'PRIVATE-SYNTHETIC-NOTE', public.data)
            self.assertEqual(public.headers['Cache-Control'], 'no-store')
            self.assertNotIn(b'PRIVATE-SYNTHETIC-NOTE', self.client.get(path+'?pin=0000').data)
            self.assertIn(b'PRIVATE-SYNTHETIC-NOTE', self.client.post(path, data={'pin':'8462'}).data)
        qr = self.client.get(f'/qr/{self.band}')
        self.assertEqual(qr.status_code, 200); self.assertEqual(qr.mimetype, 'image/png')
        with patch.object(application, 'send_full_alert', return_value=True) as notify:
            self.assertEqual(self.client.get(f'/{self.band}?alert=yes').status_code, 200)
            self.assertEqual(notify.call_args.args[1:3], ('+12025550102', 'updated@example.test'))

    def test_invalid_pin_update_is_atomic(self):
        self.activate(); self.authorize()
        before = self.row()
        response = self.client.put('/api/profile/me', json={'fullName':'MUST NOT SAVE','phone':'2025550100','pin':'bad'})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.row(), before)

    def test_profile_content_is_escaped(self):
        self.activate(); self.authorize()
        payload = dict(fullName='<script>window.auditXss=1</script>', phone='2025550100',
                       condition='<img src=x onerror=alert(1)>', medicalNotes='<script>private()</script>',
                       photoUrl='https://example.test/"><script>photo()</script>')
        self.assertEqual(self.client.put('/api/profile/me', json=payload).status_code, 200)
        for response in (self.client.get(f'/{self.band}'), self.client.post(f'/{self.band}', data={'pin':'7391'})):
            html = response.get_data(as_text=True)
            self.assertNotIn('<script>window.auditXss', html)
            self.assertNotIn('<img src=x', html)
            self.assertNotIn('<script>private()', html)
            self.assertNotIn('<script>photo()', html)
            self.assertIn('&lt;script&gt;', html)
        with self.client.session_transaction() as sess:
            sess['logged_in'] = True
        self.assertNotIn(b'<script>window.auditXss', self.client.get(f'/edit/{self.band}').data)
        with patch('urllib.request.urlopen', side_effect=OSError('No external requests during audit')):
            self.assertNotIn(b'<script>window.auditXss', self.client.get('/dashboard').data)

    def test_sms_verification_is_single_use_and_cookie_has_no_code_hash(self):
        self.activate(); code = self.request_sms()
        cookie = self.client.get_cookie('session').value
        decoded = application.app.session_interface.get_signing_serializer(application.app).loads(cookie)
        self.assertEqual(self.verify(code).status_code, 200)
        self.assertEqual(self.client.get('/api/profile/me').status_code, 200)
        replay = application.app.test_client(); replay.set_cookie('session', cookie)
        self.assertEqual(replay.post('/api/profile/verify-code', json={'bandId':self.band,'code':code}).status_code, 403)
        self.assertEqual(replay.get('/api/profile/me').status_code, 401)
        self.assertIsInstance(decoded['profile_verify'], str)

    def test_sms_expiry_cooldown_attempt_limits_and_cookie_replay(self):
        self.activate(); code = self.request_sms()
        cookie = self.client.get_cookie('session').value
        self.assertEqual(self.client.post('/api/profile/request-code', json={'bandId':self.band}).status_code, 429)
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5):
            self.client.set_cookie('session', cookie)
            self.assertEqual(self.verify(wrong).status_code, 403)
        self.client.set_cookie('session', cookie)
        self.assertEqual(self.verify(code).status_code, 403)
        with psycopg.connect(self.url) as conn:
            conn.execute("UPDATE profile_verification_challenges SET sent_at=NOW()-INTERVAL '2 minutes' WHERE band_id=%s", (self.band,))
        self.request_sms()
        with psycopg.connect(self.url) as conn:
            conn.execute("UPDATE profile_verification_challenges SET expires_at=NOW()-INTERVAL '1 minute' WHERE band_id=%s", (self.band,))
        self.assertEqual(self.verify(code).status_code, 403)

    def test_sms_failure_and_missing_provider_have_recovery_messages(self):
        self.activate()
        with patch.object(application, 'TWILIO_AUTH_TOKEN', None):
            response = self.client.post('/api/profile/request-code', json={'bandId':self.band})
            self.assertEqual(response.status_code, 503); self.assertIn('support', response.get_json()['error'])
        self.sms.return_value.messages.create.side_effect = RuntimeError('synthetic provider failure')
        response = self.client.post('/api/profile/request-code', json={'bandId':self.band})
        self.assertEqual(response.status_code, 502)
        self.assertNotIn('synthetic provider failure', response.get_json()['error'])
        with psycopg.connect(self.url) as conn:
            self.assertIsNone(conn.execute('SELECT 1 FROM profile_verification_challenges WHERE band_id=%s', (self.band,)).fetchone())

    def test_key_finder_session_cannot_edit_safety_profile(self):
        self.activate()
        with self.client.session_transaction() as sess:
            sess['kf_email']='owner@example.test'; sess['kf_csrf']='test-only'
        self.assertEqual(self.client.get('/api/profile/me').status_code, 401)
        self.assertEqual(self.client.put('/api/profile/me',json={'fullName':'Intruder'}).status_code, 401)
        self.assertEqual(self.client.get(f'/edit/{self.band}').status_code, 302)

    def test_malformed_json_and_database_failure_are_actionable(self):
        for endpoint in ('/api/activate','/api/profile/request-code','/api/profile/verify-code'):
            for payload in ([], {'bandId':123}, {'bandId':self.band,'code':[]}):
                response = self.client.post(endpoint, json=payload)
                self.assertEqual(response.status_code, 400, endpoint)
        self.activate(); self.authorize()
        self.assertEqual(self.client.put('/api/profile/me', json=[]).status_code, 400)
        with patch.object(application.psycopg, 'connect', side_effect=psycopg.OperationalError('synthetic')):
            response = self.client.get('/api/profile/me')
            self.assertEqual(response.status_code, 503)
            self.assertIn('support',response.get_json()['error'])

    def test_migration_repeats_without_changing_inventory(self):
        with psycopg.connect(self.url) as conn:
            for _ in range(2):
                for path in sorted(Path('migrations').glob('*.sql')):
                    conn.execute(path.read_text())
                conn.execute(Path('schema_postgres.sql').read_text())
        self.assertEqual(self.repository.records_for_print(band_id=self.band)[0]['activation_code'], self.code)

    def test_pin_is_post_only_throttled_and_cannot_leak_in_url(self):
        self.activate(); self.authorize()
        self.assertEqual(self.client.put('/api/profile/me', json={'fullName':'Synthetic Owner', 'phone':'2025550100', 'medicalNotes':'PRIVATE-PIN-TEST'}).status_code, 200)
        self.assertNotIn(b'PRIVATE-PIN-TEST', self.client.get(f'/{self.band}?pin=7391').data)
        for _ in range(5):
            wrong = self.client.post(f'/{self.band}', data={'pin':'0000'})
            self.assertEqual(wrong.status_code, 200)
            self.assertIn(b'Incorrect PIN', wrong.data)
            self.assertNotIn(b'PRIVATE-PIN-TEST', wrong.data)
        self.assertEqual(self.client.post(f'/{self.band}', data={'pin':'7391'}).status_code, 429)
        with psycopg.connect(self.url) as conn:
            conn.execute("UPDATE safety_pin_attempts SET window_start=NOW()-INTERVAL '16 minutes'")
        unlocked = self.client.post(f'/{self.band}', data={'pin':'7391'})
        self.assertIn(b'PRIVATE-PIN-TEST', unlocked.data)
        self.assertEqual(unlocked.headers['Referrer-Policy'], 'no-referrer')

    def test_database_only_member_can_send_location_and_safe_notifications(self):
        self.activate()
        with patch.object(application, 'file_name', '/nonexistent-do-not-read-customer-csv'), patch.object(application, 'send_full_alert', return_value=True) as alert, patch.object(application, 'send_safe_notification', return_value=True) as safe:
            response=self.client.get('/alert_with_location',query_string={'band_id':self.band,'lat':'34.5','lon':'-86.9'})
            self.assertEqual(response.status_code,200)
            self.assertIn(b'Alert Sent',response.data)
            self.assertEqual(alert.call_args.args,('Synthetic Owner','+12025550101','helper@example.test',self.band,'https://maps.google.com/?q=34.5,-86.9'))
            self.assertEqual(self.client.get('/im_safe/'+self.band).status_code,200)
            self.assertEqual(safe.call_args.args,('Synthetic Owner','+12025550101','helper@example.test',self.band))
            alert.return_value=False; safe.return_value=False
            self.assertEqual(self.client.get('/alert_with_location',query_string={'band_id':self.band,'lat':'34.5','lon':'-86.9'}).status_code,502)
            self.assertEqual(self.client.get('/im_safe/'+self.band).status_code,502)
        self.assertEqual(self.client.get('/alert_with_location',query_string={'band_id':self.band,'lat':'nan','lon':'-86.9'}).status_code,400)

    def test_profile_rejects_invalid_emergency_contacts_without_saving(self):
        self.activate(); self.authorize()
        before = self.row()
        for fields in ({'emergencyContacts':'not-a-phone'}, {'emergencyEmails':'not-an-email'}, {'emergencyContacts':', '.join(['2025550100']*6)}):
            data={'fullName':'Must not save','phone':'2025550100',**fields}
            self.assertEqual(self.client.put('/api/profile/me',json=data).status_code,400)
            self.assertEqual(self.row(),before)

    def test_concurrent_sms_verification_has_one_winner(self):
        self.activate(); code=self.request_sms()
        cookie=self.client.get_cookie('session').value
        def verify(_):
            client=application.app.test_client();client.set_cookie('session',cookie)
            return client.post('/api/profile/verify-code',json={'bandId':self.band,'code':code}).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(verify,range(2))),[200,403])
