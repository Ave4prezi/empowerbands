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
