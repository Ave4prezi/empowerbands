# EmpowerBands

Flask application using PostgreSQL for Safety ID activation and member profiles.

## Core data stores

- PostgreSQL `members` — customer profile information.
- PostgreSQL `activation_codes` — activation credentials, claim status, and inventory assignment.
- `customers.csv` — legacy data used by remaining dashboard routes during the PostgreSQL migration.

## Activation flow

1. Visit `/activate` or `/activate/<band_id>`.
2. Enter the Safety ID and its activation code.
3. `/api/activate` validates and locks the matching PostgreSQL activation record.
4. If the ID is unclaimed and no populated profile exists, the member profile is saved and the code is marked claimed in one transaction.

Administrators generate and manage inventory at `/admin/activation-codes`. Activation codes remain separate from customer profile fields and must never be committed to the repository.

## Run

Install `requirements.txt`, set the required environment variables, and run `python app.py` locally or use the included `procfile` on the hosting platform.

## Support and resources page

`/resources` displays the groups and links in `resources.json`. To add a song or a short talk, edit that file in GitHub, add an object to the appropriate group's `links` list, and commit the change. Each object needs a `title`, `description`, and direct `url`; the optional `call` and `text` fields create phone or text buttons. Use links that open one recording directly if you want to avoid an autoplay queue. Check the JSON syntax before committing. GitHub edits to this file deploy with the rest of the site.

The crisis links are curated separately from the music and encouragement groups. Check that hotline details still match the linked organizations when updating them. Do not add visitor names or health information to this file.

## Support group hub draft

`/support-hub` is a public preview of planned invitation-only groups. It deliberately has no posting, sign-in, or member data collection yet. Do not open live chat until member invitations, moderator appointments, message reports, access controls, persistent storage, and privacy review are implemented and tested. April and Avery are the intended initial moderators.
