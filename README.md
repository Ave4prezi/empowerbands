# EmpowerBands

Flask application using CSV files as its data store.

## Core data files

- `customers.csv` — Safety ID/customer profiles (15 columns, beginning with `band_id,name,email,...`).
- `activation_codes.csv` — activation credentials and claimed status (`band_id,activation_code,claimed`).

## Activation flow

1. Visit `/activate` or `/activate/<band_id>`.
2. Enter the Safety ID and its activation code.
3. `/api/activate` validates the code against `activation_codes.csv`.
4. If the ID is unclaimed, the profile is created/updated in `customers.csv` and the code is marked `claimed=yes`.

Existing active customer rows remain in `customers.csv`. Activation codes are deliberately kept out of the customer profile columns so the rest of the legacy app retains its expected 15-column layout.

## Run

Install `requirements.txt`, set the required environment variables, and run `python app.py` locally or use the included `procfile` on the hosting platform.

## Support and resources page

`/resources` displays the groups and links in `resources.json`. To add a song or a short talk, edit that file in GitHub, add an object to the appropriate group's `links` list, and commit the change. Each object needs a `title`, `description`, and direct `url`; the optional `call` and `text` fields create phone or text buttons. Use links that open one recording directly if you want to avoid an autoplay queue. Check the JSON syntax before committing. GitHub edits to this file deploy with the rest of the site.

The crisis links are curated separately from the music and encouragement groups. Check that hotline details still match the linked organizations when updating them. Do not add visitor names or health information to this file.

## Support group hub draft

`/support-hub` is a public preview of planned invitation-only groups. It deliberately has no posting, sign-in, or member data collection yet. Do not open live chat until member invitations, moderator appointments, message reports, access controls, persistent storage, and privacy review are implemented and tested. April and Avery are the intended initial moderators.
