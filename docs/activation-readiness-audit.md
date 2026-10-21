# Activation readiness audit — 2026-10-21

**Release decision: HOLD for review and live/hardware verification.** The fixes below
are on `audit/activation-readiness`, not deployed. Local software checks pass; that
does not establish production readiness.

## Scope and evidence

- Baseline: main commit `e52cf0a`. Existing suite: 54 executed, 49 passed,
  3 failed, 2 errored. Five additional targeted regressions reproduced five real
  defects against a separate copy of that baseline.
- Fixed branch: **78 tests passed, zero failures/errors/skips**, using Python 3.12
  and PostgreSQL 16. Includes concurrent claims/verification and real database
  transactions, not just mocks.
- Chromium staging: **390×900 and 1440×900**, real forms and local PostgreSQL,
  synthetic inventory only. Notification sinks replace external delivery.
- Key Finder email API: a loopback HTTP test service receives the application's
  Resend-shaped requests using a fake test key. Tests cover success, provider
  rejection, cooldown, expiration, wrong-address use and single-use codes.
- No production database, actual customer data, real device activations, external
  email/SMS recipients, payments, merge or deployment were used.

Local evidence, browser scripts and screenshots are in
`/workspace/activation-audit/` in the audit environment. The browser driver and
safe local staging harness are also committed in `scripts/`. The automated regression
coverage is committed under `tests/`; CI now runs the complete suite against its
own disposable PostgreSQL service.

## Safety ID customer steps

PASS means verified on this development branch with synthetic data. PENDING means
it has not been established on physical inventory or the deployed service.

| Customer step | Result | Evidence / qualification |
| --- | --- | --- |
| Generate inventory and print activation card | PASS | Actual PostgreSQL generator, stored ID/code, printed code and `/activate/<id>` URL agree. Generated codes are 8 characters; table constraints enforce uniqueness. |
| Match printed card to physical unit | PENDING | No physical units inspected. Match each device's NFC/QR destination to its database ID and the packaged card before shipping. |
| Enter valid ID and activation code | PASS | Browser review/confirmation and API create one profile and mark the same inventory row claimed with a timestamp. |
| Wrong code / unknown ID / malformed input | PASS | Rejected without profile creation; malformed non-text JSON returns a controlled 400. |
| Expired inventory activation code | N/A | Inventory codes have no time-based expiry. Unclaimed-code rotation/revocation is supported and tested; old code fails and replacement succeeds. |
| Previously claimed code | PASS | Reuse fails; populated profiles cannot be overwritten. Rotation/reassignment of claimed inventory is rejected. |
| Two simultaneous claims | PASS | PostgreSQL row locks yield exactly one success and one rejection. |
| Correct profile and emergency contacts | PASS | Name, hashed PIN, phone/email contacts and claimed timestamp verified in PostgreSQL. No plaintext PIN stored. |
| Verify phone to edit profile | PASS locally / PENDING live | Mocked SMS targets the synthetic owner's phone. Wrong/expired codes fail. Five attempts, a 60-second resend cooldown, concurrent verification and replay of an old cookie are tested. Production Twilio delivery is not verified. |
| Update profile and PIN | PASS | Real update/readback and browser editor; invalid PIN or emergency contacts do not partially save. Phone verification expires after 30 minutes. |
| Save emergency contact names/relationships | FAIL (existing limitation) | The editor displays these fields but does not persist them. Phone/email contacts do persist; see the remaining data-model issue below. |
| PIN-protected private notes | PASS | Absent in public/wrong-PIN responses; correct POST unlocks. PIN is not accepted through URL query parameters. Five attempts per ID/IP in 15 minutes; privacy responses use `no-store` and `no-referrer`. |
| Public NFC/QR profile | PASS software / PENDING hardware | Short and full profile routes load the correct synthetic profile. QR endpoint returns a PNG. Generated URL/route alignment is verified; physical NFC encoding and optical QR scanning are not. |
| Emergency alert with/without location; “I'm safe” | PASS locally / PENDING live | Current PostgreSQL-only profiles reach the current synthetic contacts through mocked notification functions. Delivery failure is not reported as success. Live SMS/email and handset location permission still require testing. |
| Other Key Finder user accesses protected Safety ID data | PASS (denied) | Key Finder-only session cannot read/update `/api/profile/me` or use admin editing. Public Safety ID fields remain intentionally public. |
| Script-like profile content | PASS (escaped) | Synthetic hostile text is escaped in public/private profile HTML, admin editing and dashboard views. |

## NFC Key Finder customer steps

| Customer step | Result | Evidence / qualification |
| --- | --- | --- |
| Inventory generator / private CSV / printed data | PASS | Generated serial, recovery token, URL and 24-character activation code validate through the same import format; claim hash matches generator. Existing admin tests check cards/private CSV. |
| Receive email verification code | PASS test service / PENDING live | Real request serialization and local HTTP delivery tested. No claim that Resend accepted or delivered a real email. |
| Wrong / expired / reused email code | PASS | Address-bound hash, 10-minute expiry and five attempts; replay and two simultaneous verifications yield only one accepted login. |
| Missing provider / provider rejection / cooldown | PASS | Existing mocks plus HTTP rejection test verify safe error text, retry timing and return-to-sign-in/support instructions. |
| Match serial and hidden activation code | PASS | Another generated unit's code is rejected. Matching pair claims only the intended record. |
| Single-use activation and concurrent claims | PASS | Consumed hash is replaced; reuse/foreign claim fails. Existing real-DB concurrent-claim test has one winner. |
| Tag opens its own recovery page | PASS software / PENDING hardware | Each generated `/k/<20-character-token>` resolves its own record; the other unit does not expose the first owner's contact. Physical tag programming remains unverified. |
| Owner contact visibility | PASS | Hidden by default and when disabled; visible email appears only with owner opt-in. Browser and API checked. |
| Mark lost and change recovery details | PASS | Signed-in owner can update; recovery page reflects lost state. |
| Another account edits claimed unit | PASS (denied) | Real DB owner predicate rejects modification, excludes the device from the other account's dashboard and prevents reclaiming. |
| Separation from Safety ID profiles | PASS | Key Finder routes use their own tables/session keys. Protected Safety ID routes deny a Key Finder-only login; no medical fields appear in recovery API. |
| Mobile sign-in, claim and owner settings | PASS local staging | Chromium runs both mobile and desktop forms, then opens the exact generated recovery URL. Real iOS/Android NFC and native email links remain pending. |

## Defects found and addressed in this branch

1. **Partial update on rejected PIN:** the old handler wrote profile changes before
   validating the new PIN. Returning 400 still committed the transaction. All
   validation now occurs before writes; invalid contact updates also fail safely.
2. **Stored HTML/script injection:** customer fields were directly interpolated
   into profile and admin HTML. Those render paths now escape stored text.
3. **Replayable Safety ID SMS verification:** hashes and attempt counters lived in
   signed, readable browser cookies. An old cookie could reset attempts and reuse
   a verification challenge. Opaque challenge IDs now refer to server-side,
   expiring, single-use PostgreSQL records, consumed transactionally.
4. **PINs in URLs with unlimited guesses:** unlocking now uses POST with a
   persistent ID/IP attempt limit and private-response cache/referrer headers.
   Old `?pin=` links intentionally no longer unlock a profile.
5. **CSV-only notification routes:** location alerts and safe notifications could
   miss newly activated PostgreSQL-only customers. Both now use current database
   contacts, validate IDs/location, and return failure when nothing was delivered.
6. **Contact number corruption in the editor:** the phone formatter truncated
   the leading country code incorrectly. It now strips a single US `+1` before
   formatting; the browser test checks both the displayed number and the stored
   number after saving.
7. **Five stale test failures:** activation fixtures lacked the required PIN and
   the in-memory print repository lacked `band_ids`. Fixtures now match the real
   contract, with no disabled tests or removed assertions.

## Database and environment review

The runtime uses `members` and `activation_codes` for Safety IDs; Key Finder uses
`key_finder_*` tables. `schema_postgres.sql` defines a separate legacy bulk
`bands.activation_token` model. Do not assume a bulk activation token is a valid
Safety ID activation code. Match the shipment to the actual application's
inventory; that physical reconciliation is still outstanding.

Both existing SQL migrations and `schema_postgres.sql` were applied twice to the
local disposable database without changing the synthetic activation record. The
new additive migration is
`migrations/20261021_profile_verification_challenges.sql`. It creates
`profile_verification_challenges` and `safety_pin_attempts`, touching no customer
rows or inventory. Runtime initialization also creates these tables for a fresh
database. Before any approved release, apply the migration under the normal
migration role; verify the application role can read/write the tables. Existing
startup still needs its documented schema-management permissions.

| Configuration | Purpose / verification |
| --- | --- |
| `DATABASE_URL` | Required PostgreSQL binding. Only disposable localhost test URLs were used. |
| `SECRET_KEY` | Stable, strong shared secret for sessions and challenge HMACs. Must match across workers/restarts. Not inspected or printed. |
| `ADMIN_PASSWORD` | Needed for real inventory administration; tests use synthetic authenticated sessions. |
| `BASE_URL` | Public Safety ID profile/QR origin. Confirm deployed canonical hostname and redirects. |
| `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER` | Required for real SMS verification and SMS notifications. Mocked locally. Verify sender permissions, messaging registration and handset delivery. |
| `KEY_FINDER_ACTIVATION_PEPPER` | Required, stable, 32+ characters. Must match the value used when inventory was generated/imported. Changing it without the documented unclaimed-inventory rehash process breaks existing codes. Never restore a consumed code. |
| `RESEND_API_KEY`, `KEY_FINDER_EMAIL_FROM` | Required for real Key Finder email. Confirm verified sending domain, provider permissions and inbox/spam delivery. Default sender is support@empowerbands.org. |
| `ALERT_EMAILS`, `ALERT_EMAIL_PASSWORD` | Optional SMTP notification channel. Verify SMTP authentication and delivery independently if used. |
| `RENDER` | Hosting mode enables secure cookies and the Key Finder HTTPS form-origin expectation. Verify against the actual public host/proxy. |

The cloud environment's saved requirements contain no provider bindings. At audit
start, these application variable names were absent in the base shell; local test
configuration supplied only synthetic values. This does **not** establish that
production variables are missing: production configuration was not accessed.

## Remaining launch checks and limitations

- Review and approve these fixes before any merge/deployment. Run the full suite
  in CI and repeat the browser flows on the approved hosted staging release.
- Verify each packaged Safety ID/card pair and Key Finder NFC token/card pair on
  representative iOS and Android phones. Check the final apex/`www` host redirects
  and that printed codes were generated with the deployed pepper.
- Follow the existing legacy-inventory exposure procedure in
  `docs/activation-code-operations.md`: an authorized administrator must review
  previously exposed **unclaimed** inventory before sale. No real record was
  inspected, rotated or activated in this audit.
- Confirm real Resend inbox delivery and real Twilio SMS using designated test
  recipients and provider sandbox/test arrangements, not customer devices.
- **Known remaining UI issue:** the Safety ID editor displays contact name and
  relationship fields, but its existing storage contract only persists phone
  numbers and emails. Those labels will not survive reload. Notifications and
  phone/email persistence are tested; saving contact names/relationships needs a
  separate data-model change before promising that feature.
- Rate limits use the app-visible remote address. Verify real reverse-proxy
  behavior and upstream anti-abuse controls. These tests are not a penetration
  test or a guarantee against distributed guessing/notification abuse.
- Clearing browser cookies requires requesting a new verification challenge.
  Pre-release browser SMS challenges will be invalid after this change; users
  can request a new code. Activation inventory is not expired or reset.

## Reproduce the local staging audit

Use a **new disposable local database**, Python dependencies from requirements.txt,
Node with Playwright available, and a Chromium browser. The harness refuses a
non-local database or a database name outside `activation_audit_test*`, replaces
provider credentials with test values, creates only synthetic inventory, and
listens only on loopback. Its fixture/mailbox endpoints must never be deployed.

```sh
# Create a fresh test DB using your local PostgreSQL administrator role first.
export ACTIVATION_AUDIT_DATABASE_URL=postgresql://LOCAL_TEST_ROLE@127.0.0.1:LOCAL_TEST_PORT/activation_audit_test_browser
python scripts/audit_activation_staging.py
# In another terminal, from the repository:
node scripts/check_activation_browser.cjs
# If using a system Chromium rather than Playwright's downloaded browser:
CHROMIUM_PATH=/usr/bin/chromium node scripts/check_activation_browser.cjs
```

Run the browser driver **once per fresh fixture set**: it consumes synthetic
activation codes. Stop the harness, create a new disposable DB, and restart to
repeat it. The two driver commands above are alternatives. Screenshots default
to `/tmp/empowerbands-activation-audit`; `ACTIVATION_AUDIT_ARTIFACTS` can override
that directory. Run automated tests separately with `DATABASE_URL` set to a
fresh disposable localhost DB whose name contains `test`, a test `SECRET_KEY`,
and a test `KEY_FINDER_ACTIVATION_PEPPER` of at least 32 characters:
`python -m unittest discover -s tests -v`. The CI workflow supplies these settings.
