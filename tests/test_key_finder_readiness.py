"""Real-PostgreSQL Key Finder flows with a loopback-only fake email API."""
import concurrent.futures
import json
import os
import re
import secrets
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse
from unittest.mock import patch

import psycopg
from flask import Flask

import key_finder_backend as backend
from key_finder_admin import FIELDS, RECOVERY_BASE, generate_inventory, parse_batch
from test_safety_id_database import disposable_database


class TestMailbox(BaseHTTPRequestHandler):
    __test__ = False
    def do_POST(self):
        self.server.messages.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
        self.send_response(self.server.response_status)
        self.end_headers()
        self.wfile.write(b'{"id":"synthetic-email"}')

    def log_message(self, *_args):
        pass


class KeyFinderReadinessTests(unittest.TestCase):
    case_number = 0
    @classmethod
    def setUpClass(cls):
        cls.url = disposable_database()
        backend.initialize_key_finders()
        cls.mailbox = ThreadingHTTPServer(('127.0.0.1', 0), TestMailbox)
        cls.mailbox.messages = []
        cls.mailbox.response_status = 200
        cls.thread = threading.Thread(target=cls.mailbox.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.mailbox.shutdown(); cls.mailbox.server_close(); cls.thread.join()

    def setUp(self):
        type(self).case_number += 1
        self.ip = f'198.18.0.{self.case_number}'
        self.email = 'audit-' + secrets.token_hex(8) + '@example.test'
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only-mailbox-session'
        self.app.register_blueprint(backend.key_finder_api)
        self.client = self.app.test_client()
        self.client.get('/key-finder/account')
        self.mailbox.messages.clear(); self.mailbox.response_status = 200
        opener = urllib.request.urlopen

        def local_delivery(request, **kwargs):
            self.assertEqual(request.full_url, 'https://api.resend.com/emails')
            self.assertEqual(request.get_header('Authorization'), 'Bearer test-only-mailbox-key')
            local = urllib.request.Request(f'http://127.0.0.1:{self.mailbox.server_port}/emails',
                                           data=request.data, headers={'Content-Type':'application/json'}, method='POST')
            return opener(local, **kwargs)

        patches = [patch.dict(os.environ, {'RESEND_API_KEY':'test-only-mailbox-key',
                    'KEY_FINDER_EMAIL_FROM':'EmpowerBands <audit@example.test>'}),
                   patch('urllib.request.urlopen', side_effect=local_delivery)]
        for item in patches:
            item.start(); self.addCleanup(item.stop)
        with psycopg.connect(self.url) as conn:
            self.rows = generate_inventory(conn, 2)
        self.serial, self.token, self.recovery_url, self.code = [self.rows[0][key] for key in FIELDS]

    def post(self, path, client=None, **data):
        client = client or self.client
        with client.session_transaction() as sess: data['csrf'] = sess['kf_csrf']
        return client.post('/key-finder/'+path, data=data, headers={'Origin':'http://localhost'}, environ_overrides={'REMOTE_ADDR':self.ip})

    def send(self):
        response = self.post('send-code', email=self.email)
        self.assertEqual(response.status_code, 303)
        message = self.mailbox.messages[-1]
        self.assertEqual(message['to'], [self.email])
        self.assertIn('10 minutes', message['text'])
        return re.search(r'code is (\d{6})', message['text']).group(1)

    def login(self, client=None, email=None):
        client = client or self.client
        with client.session_transaction() as sess:
            sess['kf_email'] = email or self.email
            sess['kf_csrf'] = secrets.token_hex(16)

    def test_email_delivered_to_test_service_and_code_is_single_use(self):
        code = self.send()
        with psycopg.connect(self.url) as conn:
            hashed = conn.execute('SELECT code_hash FROM key_finder_email_challenges WHERE email=%s', (self.email,)).fetchone()[0]
            self.assertNotEqual(hashed, code)
        self.assertEqual(self.post('verify-code', email=self.email, code=code).status_code, 303)
        self.assertEqual(self.post('verify-code', email=self.email, code=code).status_code, 400)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['kf_email'], self.email)
            self.assertNotIn('profile_edit_band_id', sess)
        with psycopg.connect(self.url) as conn:
            self.assertIsNone(conn.execute('SELECT 1 FROM key_finder_email_challenges WHERE email=%s', (self.email,)).fetchone())

    def test_email_cooldown_expiry_and_attempt_limit(self):
        code = self.send()
        self.assertEqual(self.post('send-code', email=self.email).status_code, 429)
        self.assertEqual(len(self.mailbox.messages), 1)
        wrong = '000000' if code != '000000' else '111111'
        for _ in range(5): self.assertEqual(self.post('verify-code', email=self.email, code=wrong).status_code, 400)
        self.assertEqual(self.post('verify-code', email=self.email, code=code).status_code, 400)
        with psycopg.connect(self.url) as conn:
            conn.execute("UPDATE key_finder_email_challenges SET attempts=0, expires_at=NOW()-INTERVAL '1 minute' WHERE email=%s", (self.email,))
        self.assertEqual(self.post('verify-code', email=self.email, code=code).status_code, 400)

    def test_concurrent_email_verification_has_one_winner(self):
        code = self.send()
        cookie = self.client.get_cookie('session').value
        def verify(_):
            client = self.app.test_client(); client.set_cookie('session', cookie)
            return self.post('verify-code', client=client, email=self.email, code=code).status_code
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(verify, range(2))), [303,400])

    def test_email_service_rejection_has_safe_recovery_instructions(self):
        self.mailbox.response_status = 503
        response = self.post('send-code', email=self.email)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '60')
        self.assertIn(b'Return to sign-in', response.data)
        self.assertIn(b'support@empowerbands.org', response.data)
        self.assertNotIn(b'test-only-mailbox-key', response.data)

    def test_generated_cards_match_claims_and_nfc_recovery(self):
        import csv, io
        out = io.StringIO(); writer=csv.DictWriter(out, fieldnames=FIELDS); writer.writeheader(); writer.writerows(self.rows)
        self.assertEqual(parse_batch(out.getvalue().encode()), self.rows)
        self.assertEqual(self.recovery_url, RECOVERY_BASE+self.token)
        self.assertIn(b'not been activated', self.client.get('/k/'+self.token).data)
        self.login()
        self.assertEqual(self.post('claim', serial=self.serial, activation_code=self.rows[1][FIELDS[3]]).status_code,400)
        self.assertEqual(self.post('claim', serial=self.serial, activation_code=self.code).status_code,303)
        self.assertEqual(self.post('claim', serial=self.serial, activation_code=self.code).status_code,400)
        response = self.client.get('/k/'+self.token)
        self.assertEqual(response.status_code,200)
        self.assertNotIn(self.email.encode(),response.data)
        self.assertEqual(self.post('update',serial=self.serial,label='Synthetic keys',contact_email=self.email,visible='on',lost='on').status_code,303)
        page=self.client.get('/k/'+self.token)
        self.assertIn(b'reported lost',page.data); self.assertIn(self.email.encode(),page.data)
        self.assertNotIn(self.email.encode(),self.client.get('/k/'+self.rows[1][FIELDS[1]]).data)
        api=self.client.get('/api/key-finder/public/'+self.serial).get_json()
        self.assertEqual(api,{'lost':True,'product_type':'key_finder','contact_email':self.email,'message':'Contact the owner only using the information they chose to share.'})
        self.assertEqual(self.post('update',serial=self.serial,label='Synthetic keys',contact_email=self.email).status_code,303)
        self.assertNotIn(self.email.encode(),self.client.get('/k/'+self.token).data)
        with psycopg.connect(self.url) as conn:
            record=conn.execute('SELECT owner_email, activation_secret_hash FROM key_finder_devices WHERE serial=%s',(self.serial,)).fetchone()
            self.assertEqual(record[0],self.email)
            self.assertNotEqual(record[1], backend._claim_digest('activation:'+self.serial+':'+self.code))

    def test_foreign_owner_cannot_edit_or_claim_device(self):
        self.login()
        self.assertEqual(self.post('claim',serial=self.serial,activation_code=self.code).status_code,303)
        intruder=self.app.test_client(); self.login(intruder,'intruder@example.test')
        self.assertEqual(self.post('claim',client=intruder,serial=self.serial,activation_code=self.code).status_code,400)
        self.assertEqual(self.post('update',client=intruder,serial=self.serial,label='Stolen',contact_email='intruder@example.test',visible='on').status_code,404)
        self.assertNotIn(self.serial.encode(),intruder.get('/key-finder/account').data)
        self.assertNotIn(self.email.encode(),intruder.get('/k/'+self.token).data)

    def test_email_code_cannot_verify_another_address(self):
        code = self.send()
        self.assertEqual(self.post('verify-code', email='other@example.test', code=code).status_code,400)
        self.assertEqual(self.post('verify-code', email=self.email, code=code).status_code,303)
