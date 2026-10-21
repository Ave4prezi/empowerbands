"""Local-only synthetic staging harness. Never deploy this file."""

def main():
    import os, secrets, sys, re
    from pathlib import Path
    from types import SimpleNamespace
    from urllib.parse import urlparse
    url = os.environ.get('ACTIVATION_AUDIT_DATABASE_URL', '')
    parsed = urlparse(url)
    if parsed.hostname not in {'127.0.0.1', 'localhost'} or not parsed.path.startswith('/activation_audit_test'):
        raise SystemExit('Set ACTIVATION_AUDIT_DATABASE_URL to a disposable localhost activation_audit_test* database.')
    os.environ['DATABASE_URL'] = url
    artifacts = Path(os.environ.get('ACTIVATION_AUDIT_ARTIFACTS', '/tmp/empowerbands-activation-audit'))
    artifacts.mkdir(parents=True, exist_ok=True)
    os.environ['SECRET_KEY']=secrets.token_hex(32)
    os.environ['KEY_FINDER_ACTIVATION_PEPPER']=secrets.token_hex(32)
    os.environ['BASE_URL']='http://127.0.0.1:5051'
    for key in ('RESEND_API_KEY','TWILIO_AUTH_TOKEN','ALERT_EMAIL_PASSWORD','TWILIO_ACCOUNT_SID','TWILIO_PHONE_NUMBER','RENDER'):
        os.environ.pop(key,None)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    import app as application
    import key_finder_backend as backend
    import psycopg
    from activation_manager import PostgresActivationRepository
    from key_finder_admin import generate_inventory
    from flask import jsonify
    application.file_name=str(artifacts/'synthetic-customers.csv')
    Path(application.file_name).write_text('band_id,name,email,phone\n')
    application.scan_log_file=str(artifacts/'synthetic-scan-log.csv')
    mailbox={}
    backend._email_code=lambda email,code:mailbox.update({email:code})
    application.TWILIO_ACCOUNT_SID='test-only'
    application.TWILIO_AUTH_TOKEN='test-only'
    application.TWILIO_PHONE_NUMBER='+12025550199'
    application.Client=lambda *a:SimpleNamespace(messages=SimpleNamespace(create=lambda **kw:mailbox.update({'sms':re.search(r'code is (\d{6})',kw['body']).group(1)})))
    application.send_full_alert=lambda *a,**k: True
    application.send_safe_notification=lambda *a,**k: True
    repository=PostgresActivationRepository(os.environ['DATABASE_URL'])
    repository.ensure_schema()
    fixtures=[]
    for width in (390,1440):
        safety=repository.generate(1).records[0]
        with psycopg.connect(os.environ['DATABASE_URL']) as conn:key=generate_inventory(conn,1)[0]
        fixtures.append({'width':width,'safety':safety,'key':key})
    @application.app.get('/__audit__/fixtures')
    def audit_fixtures():return jsonify(fixtures)
    @application.app.get('/__audit__/mailbox')
    def audit_mailbox():return jsonify(mailbox)
    application.app.run(host='127.0.0.1',port=5051,use_reloader=False)


if __name__ == "__main__":
    main()
