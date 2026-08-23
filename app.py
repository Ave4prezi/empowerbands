@app.route('/health')
def health():
    return jsonify({"ok": True, "tracking_enabled": TRACKING_ENABLED})


@app.route('/tracking_status')
def tracking_status():
    exists = os.path.exists(location_pings_file)
    rows = 0
    try:
        if exists:
            with open(location_pings_file, 'r', encoding='utf-8') as _pf:
                rows = sum(1 for _ in _pf) - 1
                if rows < 0:
                    rows = 0
    except Exception as e:
        print('tracking_status read error', e)
    return jsonify({
        "ok": True,
        "tracking_enabled": TRACKING_ENABLED,
        "location_pings_exists": exists,
        "location_pings_rows": rows,
        "base_url": BASE_URL
    })
