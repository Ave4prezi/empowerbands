"""Route regressions without network calls; PostgreSQL behavior is tested separately."""
import os
import io
import urllib.error
import urllib.request
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask
import psycopg
import key_finder_backend as k
from scripts.import_key_finder_batch import import_rows


class KeyFinderFlowTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            'DATABASE_URL': 'postgresql://unused',
            'KEY_FINDER_ACTIVATION_PEPPER': 'p' * 48,
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.app = Flask(__name__)
        self.app.secret_key = 'test-only'
        self.app.register_blueprint(k.key_finder_api)
        self.client = self.app.test_client()
        self.client.get('/key-finder/account')
        with self.client.session_transaction() as sess:
            self.csrf = sess['kf_csrf']

    def post(self, route, **data):
        return self.client.post('/key-finder/' + route,
            data=dict(data, csrf=self.csrf), headers={'Origin': 'http://localhost'})

    def db(self, rows):
        mock = MagicMock()
        cursor = mock.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value
        cursor.fetchone.side_effect = rows
        return mock, cursor

    def sign_in(self):
        with self.client.session_transaction() as sess:
            sess['kf_email'] = 'owner@example.com'

    def test_normal_email_sign_in_and_single_use_challenge(self):
        db, cur = self.db([(1,), (1,), (1,), ('owner@example.com',),
                            (k._code_digest('owner@example.com', '123456'),), None])
        with patch.object(k.psycopg, 'connect', db), patch.object(k, '_email_code') as send, patch.object(k.secrets, 'randbelow', return_value=123456):
            self.assertEqual(self.post('send-code', email='owner@example.com').status_code, 303)
            send.assert_called_once_with('owner@example.com', '123456')
            self.assertEqual(self.post('verify-code', email='owner@example.com', code='123456').status_code, 303)
            with self.client.session_transaction() as sess:
                self.assertEqual(sess['kf_email'], 'owner@example.com')
                self.csrf = sess['kf_csrf']
            self.assertEqual(self.post('verify-code', email='owner@example.com', code='123456').status_code, 400)
        self.assertTrue(any('DELETE FROM key_finder_email_challenges' in c.args[0] for c in cur.execute.call_args_list))

    def test_invalid_emails_never_reach_database(self):
        with patch.object(k.psycopg, 'connect') as db:
            for email in ['owner example.com', 'owner@example\\.com', 'a b@example.com', 'a@example.com\nBcc:x']:
                self.assertEqual(self.post('send-code', email=email).status_code, 400)
            db.assert_not_called()

    def test_send_budget_prevents_email_delivery(self):
        db, _ = self.db([(6,)])
        with patch.object(k.psycopg, 'connect', db), patch.object(k, '_email_code') as send:
            self.assertEqual(self.post('send-code', email='owner@example.com').status_code, 429)
            send.assert_not_called()

    def test_owner_settings_accept_email_and_hide_contact(self):
        self.sign_in()
        db, cur = self.db([('KF-12345678',)])
        with patch.object(k.psycopg, 'connect', db):
            self.assertEqual(self.post('update', serial='KF-12345678', contact_email='owner@example.com', lost='on').status_code, 303)
        sql, params = cur.execute.call_args.args
        self.assertIn('owner_email=%s AND activated_at IS NOT NULL', sql)
        self.assertEqual(params, ('', 'owner@example.com', False, True, 'KF-12345678', 'owner@example.com'))

    def test_other_owner_cannot_update(self):
        self.sign_in()
        db, _ = self.db([None])
        with patch.object(k.psycopg, 'connect', db):
            self.assertEqual(self.post('update', serial='KF-12345678', label='changed').status_code, 404)

    def test_public_privacy_matrix_for_nfc_and_serial(self):
        for active in (False, True):
            for visible in (False, True):
                for path in ['/k/ABCDEFGH123456789012', '/key-finder/found?serial=KF-12345678', '/api/key-finder/public/KF-12345678']:
                    with self.subTest(active=active, visible=visible, path=path):
                        db, _ = self.db([(active, True, visible, 'contact@example.com', 'KF-12345678')]
                            if path.startswith('/k/') else [(active, True, visible, 'contact@example.com')])
                        with patch.object(k.psycopg, 'connect', db):
                            response = self.client.get(path)
                        self.assertEqual('contact@example.com' in response.get_data(as_text=True), active and visible)
                        self.assertNotIn('KF-12345678', response.get_data(as_text=True))
                        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_csrf_requires_token_and_same_origin(self):
        self.sign_in()
        for headers, data in [({'Origin': 'https://other.example'}, {'csrf': self.csrf}), ({'Origin': 'http://localhost'}, {})]:
            self.assertEqual(self.client.post('/key-finder/logout', headers=headers, data=data).status_code, 403)
        fresh = self.app.test_client()
        self.assertEqual(fresh.post('/key-finder/logout', headers={'Origin': 'http://localhost'}).status_code, 403)


    def test_same_origin_policy_preserves_form_origin_without_external_referrers(self):
        response = self.client.get('/key-finder/account')
        self.assertEqual(response.headers['Referrer-Policy'], 'same-origin')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')

    def test_render_https_forms_work_behind_http_proxy(self):
        # Browser sees HTTPS, while Render's upstream connection can be HTTP.
        with patch.dict(os.environ, {'RENDER': 'true'}):
            client = self.app.test_client()
            client.get('/key-finder/account', base_url='http://www.empowerbands.org')
            with client.session_transaction(base_url='http://www.empowerbands.org') as sess:
                token = sess['kf_csrf']
            db, _ = self.db([(1,), (1,), (1,), ('owner@example.com',)])
            with patch.object(k.psycopg, 'connect', db), patch.object(k, '_email_code') as send:
                response = client.post('/key-finder/send-code',
                    base_url='http://www.empowerbands.org',
                    headers={'Origin': 'https://www.empowerbands.org'},
                    data={'csrf': token, 'email': 'owner@example.com'})
            self.assertEqual(response.status_code, 303)
            send.assert_called_once()

    def test_render_rejects_null_missing_foreign_and_insecure_origins(self):
        with patch.dict(os.environ, {'RENDER': 'true'}):
            client = self.app.test_client()
            client.get('/key-finder/account', base_url='http://www.empowerbands.org')
            with client.session_transaction(base_url='http://www.empowerbands.org') as sess:
                token = sess['kf_csrf']
            with patch.object(k.psycopg, 'connect') as db, patch.object(k, '_email_code') as send:
                for origin in [None, 'null', 'https://other.example', 'http://www.empowerbands.org',
                               'https://www.empowerbands.org.evil.example']:
                    with self.subTest(origin=origin):
                        response = client.post('/key-finder/send-code',
                            base_url='http://www.empowerbands.org',
                            headers={'Origin': origin} if origin else {},
                            data={'csrf': token, 'email': 'owner@example.com'})
                        self.assertEqual(response.status_code, 403)
                response = client.post('/key-finder/send-code',
                    base_url='http://www.empowerbands.org',
                    headers={'Origin': 'https://www.empowerbands.org'},
                    data={'csrf': 'wrong-token', 'email': 'owner@example.com'})
                self.assertEqual(response.status_code, 403)
                db.assert_not_called()
                send.assert_not_called()


    def test_email_api_identifies_application_and_keeps_secrets_out_of_errors(self):
        with patch.dict(os.environ, {'RESEND_API_KEY': 'test-only-api-key',
                                     'KEY_FINDER_EMAIL_FROM': 'EmpowerBands <support@example.com>'}):
            response = MagicMock()
            response.__enter__.return_value.status = 200
            with patch('urllib.request.urlopen', return_value=response) as send:
                k._email_code('owner@example.com', '123456')
            request = send.call_args.args[0]
            self.assertEqual(request.get_header('User-agent'), 'EmpowerBands/1.0')
            self.assertEqual(request.full_url, 'https://api.resend.com/emails')
            self.assertEqual(send.call_args.kwargs['timeout'], 10)

    def test_failed_email_has_safe_notice_and_return_link(self):
        db, _ = self.db([(1,), (1,), (1,), ('owner@example.com',)])
        error = urllib.error.HTTPError('https://api.resend.com/emails', 403,
                                      'secret-provider-detail', {}, io.BytesIO(b'private body'))
        with patch.object(k.psycopg, 'connect', db), patch.object(k, '_email_code', side_effect=error):
            with self.assertLogs(k.logger, level='ERROR') as logs:
                response = self.post('send-code', email='owner@example.com')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '60')
        html = response.get_data(as_text=True)
        self.assertIn('We could not send', html)
        self.assertIn('Return to sign-in', html)
        self.assertNotIn('secret-provider-detail', html)
        self.assertNotIn('owner@example.com', ' '.join(logs.output))
        self.assertNotIn('private body', ' '.join(logs.output))
        self.assertIn('http_status=403', ' '.join(logs.output))

    def test_cooldown_does_not_claim_delivery(self):
        db, _ = self.db([(1,), (1,), (1,), None])
        with patch.object(k.psycopg, 'connect', db), patch.object(k, '_email_code') as send:
            response = self.post('send-code', email='owner@example.com')
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['Retry-After'], '60')
        self.assertIn('does not confirm email delivery', response.get_data(as_text=True))
        self.assertIn('Return to sign-in', response.get_data(as_text=True))
        send.assert_not_called()

    def test_unavailable_services_return_503(self):
        self.sign_in()
        with patch.object(k.psycopg, 'connect', side_effect=psycopg.OperationalError('offline')):
            self.assertEqual(self.client.get('/key-finder/account').status_code, 503)
            self.assertEqual(self.post('verify-code', email='owner@example.com', code='123456').status_code, 503)
            self.assertEqual(self.post('update', serial='KF-12345678').status_code, 503)
        with patch.dict(os.environ, {'KEY_FINDER_ACTIVATION_PEPPER': ''}):
            self.assertEqual(self.post('claim', serial='KF-12345678', activation_code='A'*24).status_code, 503)

    def test_missing_recovery_link_cannot_activate(self):
        self.sign_in()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        db, cur = self.db([(0, now, None)]*3 + [(k._claim_digest('activation:KF-12345678:'+'A'*24), None, None, None)])
        with patch.object(k.psycopg, 'connect', db):
            self.assertEqual(self.post('claim', serial='KF-12345678', activation_code='A'*24).status_code, 400)
        self.assertFalse(any('SET owner_email' in c.args[0] for c in cur.execute.call_args_list))


class KeyFinderImportTests(unittest.TestCase):
    def test_import_rotation_and_consumed_secrets(self):
        import hashlib, hmac
        serial, token, code = 'KF-12345678', 'A'*20, 'B'*24
        old, new = 'o'*48, 'n'*48
        old_hash = hmac.new(old.encode(), f'activation:{serial}:{code}'.encode(), hashlib.sha256).hexdigest()
        cases = [((token, 'consumed', object()), None, False, False),
                 ((None, old_hash, None), old, True, False),
                 ((token, old_hash, None), None, False, True),
                 (('C'*20, old_hash, None), old, False, True)]
        for existing, previous, updates, rejects in cases:
            with self.subTest(existing=existing, previous=bool(previous)):
                conn = MagicMock(); cur = conn.cursor.return_value.__enter__.return_value
                cur.rowcount = 0; cur.fetchone.return_value = existing
                if rejects:
                    with self.assertRaises(ValueError): import_rows(conn, [(serial,token,code)], new, previous)
                else:
                    import_rows(conn, [(serial,token,code)], new, previous)
                self.assertEqual(any('UPDATE key_finder_devices' in c.args[0] for c in cur.execute.call_args_list), updates)


if __name__ == '__main__':
    unittest.main()
