"""Inventory UI regression tests; integration cases use only disposable CI PostgreSQL."""
import hashlib
import hmac
import io
import os
from pathlib import Path
import secrets
import unittest
from unittest.mock import MagicMock, patch

from flask import Flask
import psycopg

from key_finder_backend import initialize_key_finders, key_finder_api
from key_finder_admin import (FIELDS, RECOVERY_BASE, generate_inventory,
    initialize_key_finder_admin, key_finder_admin, parse_batch)


class AdminRouteTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'DATABASE_URL':'unused', 'KEY_FINDER_ACTIVATION_PEPPER':'p'*48})
        self.env.start(); self.addCleanup(self.env.stop)
        self.app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[1] / 'templates'))
        self.app.secret_key = 'test-only'; self.app.register_blueprint(key_finder_admin)
        self.client = self.app.test_client()

    def login(self):
        with self.client.session_transaction() as sess:
            sess.update(logged_in=True, kf_admin_csrf='csrf-test', kf_admin_request='request-test')

    def test_admin_routes_require_login(self):
        with patch('key_finder_admin.psycopg.connect') as db:
            for method, path in [('get','/admin/key-finders'), ('post','/admin/key-finders/generate'), ('post','/admin/key-finders/import')]:
                self.assertEqual(getattr(self.client,method)(path).status_code,302)
            db.assert_not_called()

    def test_invalid_tokens_and_quantities_do_not_write(self):
        self.login()
        with patch('key_finder_admin.psycopg.connect') as db:
            self.assertEqual(self.client.post('/admin/key-finders/generate',data={'count':1}).status_code,403)
            for count in ['0','101','abc','1.5','-1']:
                self.assertEqual(self.client.post('/admin/key-finders/generate',data={'count':count,'csrf':'csrf-test','request_id':'request-test'}).status_code,400)
            db.assert_not_called()

    def test_pet_card_login_preserves_only_known_destination(self):
        response = self.client.get('/admin/key-finders?product=pet-finder')
        self.assertEqual(response.location, '/admin')
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['finder_cards_after_login'], 'pet-finder')
        self.client.get('/admin/key-finders?product=https://example.com')
        with self.client.session_transaction() as sess:
            self.assertEqual(sess['finder_cards_after_login'], 'key-finder')

    def test_generation_returns_matching_cards_and_private_csv_only_once(self):
        self.login(); db = MagicMock(); conn=db.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value=('request-test',)
        with patch('key_finder_admin.psycopg.connect',db):
            response=self.client.post('/admin/key-finders/generate',data={'count':'2','csrf':'csrf-test','request_id':'request-test'})
        self.assertEqual(response.status_code,200)
        self.assertIn(b'Download private CSV',response.data)
        self.assertEqual(response.data.count(b'class="card"'),2)
        self.assertIn('no-store',response.headers['Cache-Control'])
        with self.client.session_transaction() as sess:
            self.assertNotIn('kf_admin_request',sess)
            self.assertFalse(any('activation_code' in key for key in sess))
        self.assertEqual(self.client.post('/admin/key-finders/generate',data={'count':2,'csrf':'csrf-test','request_id':'request-test'}).status_code,403)

    def test_database_rejects_duplicate_submission(self):
        self.login(); db=MagicMock(); db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value=None
        with patch('key_finder_admin.psycopg.connect',db):
            self.assertEqual(self.client.post('/admin/key-finders/generate',data={'count':1,'csrf':'csrf-test','request_id':'request-test'}).status_code,409)
        self.assertFalse(any('INSERT INTO key_finder_devices' in c.args[0] for c in db.return_value.__enter__.return_value.execute.call_args_list))

    def test_pet_cards_use_shared_secure_inventory_and_reject_unknown_label(self):
        self.login()
        with patch('key_finder_admin.psycopg.connect') as db:
            invalid = self.client.post('/admin/key-finders/generate', data={
                'count': '1', 'csrf': 'csrf-test', 'request_id': 'request-test', 'product': 'other'})
            self.assertEqual(invalid.status_code, 400)
            db.assert_not_called()
            db.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = ('request-test',)
            response = self.client.post('/admin/key-finders/generate', data={
                'count': '1', 'csrf': 'csrf-test', 'request_id': 'request-test', 'product': 'pet-finder'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Activate your Pet Finder', response.data)
        self.assertIn(b'/key-finder/account', response.data)
        self.assertIn(b'no-store', response.headers['Cache-Control'].encode())

    def test_generation_stores_hashes_not_codes(self):
        conn=MagicMock(); rows=generate_inventory(conn,4)
        self.assertEqual(len({r[FIELDS[0]] for r in rows}),4)
        for row, call in zip(rows,conn.execute.call_args_list):
            serial,token,digest=call.args[1]
            code=row[FIELDS[3]]
            expected=hmac.new(b'p'*48,f'activation:{serial}:{code}'.encode(),hashlib.sha256).hexdigest()
            self.assertEqual(digest,expected); self.assertNotIn(code,repr(call))
            self.assertEqual(row[FIELDS[2]],RECOVERY_BASE+token)

    def test_upload_validation(self):
        import csv
        def csv_bytes(rows):
            out=io.StringIO(); writer=csv.writer(out); writer.writerow(FIELDS);writer.writerows(rows);return out.getvalue().encode()
        row=['KF-12345678','A'*20,RECOVERY_BASE+'A'*20,'B'*24]
        self.assertEqual(len(parse_batch(csv_bytes([row]))),1)
        for raw in [csv_bytes([row,row]),b'x,y\n1,2\n',b'x'*65537,csv_bytes([row[:2]+['https://evil.test','B'*24]])]:
            with self.assertRaises(ValueError):parse_batch(raw)

    def test_missing_activation_configuration_fails_before_database_write(self):
        self.login()
        raw=','.join(FIELDS)+'\nKF-12345678,'+'A'*20+','+RECOVERY_BASE+'A'*20+','+'B'*24+'\n'
        with patch.dict(os.environ, {'KEY_FINDER_ACTIVATION_PEPPER':''}), patch('key_finder_admin.psycopg.connect') as db:
            response=self.client.post('/admin/key-finders/import',data={'csrf':'csrf-test','request_id':'request-test','batch_csv':(io.BytesIO(raw.encode()),'private.csv')})
        self.assertEqual(response.status_code,503)
        db.assert_not_called()

    def test_refreshing_result_url_returns_to_inventory(self):
        self.login()
        for path in ['/admin/key-finders/import','/admin/key-finders/generate']:
            response=self.client.get(path)
            self.assertEqual(response.status_code,302)
            self.assertEqual(response.headers['Location'],'/admin/key-finders')

    def test_import_conflict_does_not_change_existing_records(self):
        self.login(); db=MagicMock(); conn=db.return_value.__enter__.return_value
        conn.execute.return_value.fetchone.return_value=('request-test',)
        raw=','.join(FIELDS)+'\nKF-12345678,'+'A'*20+','+RECOVERY_BASE+'A'*20+','+'B'*24+'\n'
        with patch('key_finder_admin.psycopg.connect',db),patch('key_finder_admin.import_rows',side_effect=ValueError('different hash')):
            response=self.client.post('/admin/key-finders/import',data={'csrf':'csrf-test','request_id':'request-test','batch_csv':(io.BytesIO(raw.encode()),'private.csv')})
        self.assertEqual(response.status_code,400)
        self.assertIs(db.return_value.__exit__.call_args.args[0],ValueError)


class AdminDatabaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.environ.get('DATABASE_URL'):raise unittest.SkipTest('Disposable test database unavailable')
        initialize_key_finders();initialize_key_finder_admin()

    def setUp(self):
        self.app=Flask(__name__,template_folder=str(Path(__file__).resolve().parents[1]/'templates'))
        self.app.secret_key='test-only';self.app.register_blueprint(key_finder_admin);self.app.register_blueprint(key_finder_api)
        self.client=self.app.test_client()
        with self.client.session_transaction() as sess:sess['logged_in']=True
        self.request_ids=[];self.serials=[]

    def tokens(self):
        response=self.client.get('/admin/key-finders');self.assertEqual(response.status_code,200)
        with self.client.session_transaction() as sess:
            self.request_ids.append(sess['kf_admin_request'])
            return {'csrf':sess['kf_admin_csrf'],'request_id':sess['kf_admin_request']}

    def tearDown(self):
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            conn.execute('DELETE FROM key_finder_devices WHERE serial=ANY(%s)',(self.serials,))
            conn.execute('DELETE FROM key_finder_admin_requests WHERE request_id=ANY(%s)',(self.request_ids,))

    def test_generated_inventory_can_be_claimed_and_replay_is_blocked(self):
        import json,re
        fields=self.tokens()
        response=self.client.post('/admin/key-finders/generate',data=dict(fields,count=2))
        self.assertEqual(response.status_code,200)
        raw=json.loads(re.search(r'const csvText=(.*);',response.get_data(as_text=True)).group(1))
        rows=parse_batch(raw.encode());self.serials=[r[FIELDS[0]] for r in rows]
        # Replay with the original signed admin session still cannot create extra records.
        with self.client.session_transaction() as sess:sess['kf_admin_request']=fields['request_id']
        self.assertEqual(self.client.post('/admin/key-finders/generate',data=dict(fields,count=2)).status_code,409)
        with self.client.session_transaction() as sess:sess.update(kf_email='owner@example.test',kf_csrf='customer-csrf')
        row=rows[0]
        result=self.client.post('/key-finder/claim',data={'serial':row[FIELDS[0]],'activation_code':row[FIELDS[3]],'csrf':'customer-csrf'},headers={'Origin':'http://localhost'})
        self.assertEqual(result.status_code,303)
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            self.assertIsNotNone(conn.execute('SELECT activated_at FROM key_finder_devices WHERE serial=%s',(row[FIELDS[0]],)).fetchone()[0])

    def test_private_csv_import_preserves_activated_devices_and_can_reprint_available(self):
        import csv
        serial='KF-'+secrets.token_hex(6).upper();token=secrets.token_hex(10).upper();code=secrets.token_hex(12).upper()
        self.serials=[serial]
        output=io.StringIO();writer=csv.writer(output);writer.writerow(FIELDS);writer.writerow([serial,token,RECOVERY_BASE+token,code]);raw=output.getvalue().encode()
        def upload():return self.client.post('/admin/key-finders/import',data=dict(self.tokens(),batch_csv=(io.BytesIO(raw),'private.csv')))
        self.assertEqual(upload().status_code,200);self.assertEqual(upload().status_code,200)
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            conn.execute("UPDATE key_finder_devices SET activated_at=NOW(),owner_email='existing@example.test',activation_secret_hash='consumed' WHERE serial=%s",(serial,))
        response=upload();self.assertEqual(response.status_code,200)
        self.assertIn(b'0 activation cards ready',response.data)
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:
            self.assertEqual(conn.execute('SELECT owner_email,activation_secret_hash FROM key_finder_devices WHERE serial=%s',(serial,)).fetchone(),('existing@example.test','consumed'))
