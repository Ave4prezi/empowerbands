# Activation Update — Unassigned Bands

This update adds support for managing unassigned bands and activating full user profiles in the empowerbands application.

## Features

- **`/add` endpoint** — Add unassigned bands to a user profile
- **`/activate` endpoint** — Activate the full user profile with assigned bands
- **Register template updates** — UI components for band activation

## Installation

Run the activation update installer:

```bash
python3 apply_activation_update.py
```

This script will:
1. Update `app.py` with activation and band route blueprints
2. Update `templates/register.html` with activation UI components

## Verification

After installation, verify the Python syntax:

```bash
python3 -m py_compile app.py
```

## API Endpoints

### POST `/add`
Add unassigned bands to a user profile.

**Request:**
```json
{
  "user_id": "user123",
  "band_ids": ["band1", "band2", "band3"]
}
```

**Response:**
```json
{
  "message": "Bands added successfully",
  "result": {
    "user_id": "user123",
    "bands_added": ["band1", "band2", "band3"],
    "added_at": "2026-07-16T14:30:00",
    "status": "success"
  }
}
```

### POST `/activate`
Activate the full user profile.

**Request:**
```json
{
  "user_id": "user123",
  "bands": ["band1", "band2", "band3"]
}
```

**Response:**
```json
{
  "message": "Profile activated successfully",
  "activation": {
    "user_id": "user123",
    "bands": ["band1", "band2", "band3"],
    "activated_at": "2026-07-16T14:30:00",
    "status": "active"
  }
}
```

## Files Modified

- `app.py` — Added blueprint registrations
- `templates/register.html` — Added activation UI section

## Files Added

- `activation_routes.py.txt` — Activation endpoint definition
- `add_band_routes.py.txt` — Band management endpoint definition
- `apply_activation_update.py` — Installer script
- `README.md` — This documentation