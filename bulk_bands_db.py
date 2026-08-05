# --- BEGIN: Bulk pre-program admin pages (paste into bulk_bands_db.py) ---

from markupsafe import escape  # already installed with Flask; used to avoid HTML injection

@app.route("/admin/preprogram")
def admin_preprogram():
    if not session.get("logged_in"):
        return redirect("/admin")

    # show unassigned bands (limit for UI)
    bands = list_bands(status="unassigned", limit=1000)

    rows = ""
    for b in bands:
        bid = b.get("band_id", "")
        partner = b.get("partner_org", "")
        batch = b.get("batch_number", "")
        rows += f"""
        <tr>
            <td style="padding:10px;border-bottom:1px solid rgba(255,255,255,0.06);">{escape(bid)}</td>
            <td style="padding:10px;border-bottom:1px solid rgba(255,255,255,0.06);">{escape(partner)}</td>
            <td style="padding:10px;border-bottom:1px solid rgba(255,255,255,0.06);">{escape(batch)}</td>
            <td style="padding:10px;border-bottom:1px solid rgba(255,255,255,0.06);">
                <a style="display:inline-block;padding:8px 12px;background:#2563eb;color:white;border-radius:8px;text-decoration:none;margin-right:6px;" href="/admin/preprogram/edit/{escape(bid)}">Pre‑program</a>

                <form style="display:inline-block;margin:0;" method="POST" action="/admin/preprogram/activate" onsubmit="return confirm('Activate and open profile for {escape(bid)}?')">
                    <input type="hidden" name="band_id" value="{escape(bid)}">
                    <button style="padding:8px 12px;background:#16a34a;color:white;border-radius:8px;border:none;cursor:pointer;" type="submit">Activate & Open</button>
                </form>
            </td>
        </tr>
        """

    if not rows:
        rows = '<tr><td colspan="4" style="padding:20px;color:#94a3b8;">No unassigned bands found.</td></tr>'

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Pre‑program Bulk Bands — Admin</title>
      <style>
        body{{font-family:Arial,helvetica,sans-serif;background:#07111f;color:white;padding:20px;}}
        .wrap{{max-width:980px;margin:0 auto;}}
        table{{width:100%;border-collapse:collapse;background:rgba(255,255,255,0.02);border-radius:8px;overflow:hidden;}}
        th{{text-align:left;padding:12px;background:rgba(255,255,255,0.03);color:#7dd3fc;font-weight:700}}
        td{{color:#e5e7eb}}
        .toplinks{{display:flex;gap:12px;margin-bottom:14px;flex-wrap:wrap}}
        .btn{{display:inline-block;padding:10px 14px;border-radius:10px;text-decoration:none;color:white;background:#2563eb}}
        .back{{background:rgba(255,255,255,0.08);color:#94a3b8}}
      </style>
    </head>
    <body>
      <div class="wrap">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
          <h1 style="margin:0">Pre‑program Bulk Bands</h1>
          <div>
            <a class="btn back" href="/dashboard">← Dashboard</a>
            <a class="btn" href="/admin/preprogram">Refresh</a>
          </div>
        </div>

        <p style="color:#94a3b8">Assign customer/profile details to bulk-provisioned bands, or activate them directly. Activating redirects to the public band profile URL.</p>

        <table>
          <thead>
            <tr><th>Band ID</th><th>Partner</th><th>Batch</th><th>Actions</th></tr>
          </thead>
          <tbody>
            {rows}
          </tbody>
        </table>
      </div>
    </body>
    </html>
    """

@app.route("/admin/preprogram/edit/<band_id>", methods=["GET", "POST"])
def admin_preprogram_edit(band_id):
    if not session.get("logged_in"):
        return redirect("/admin")

    band_id = band_id.strip().upper()

    # Load existing CSV rows
    rows = []
    try:
        with open(file_name, "r", newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
    except FileNotFoundError:
        # create header if missing
        rows = [header]

    header_row = rows[0] if rows else header
    data_rows = rows[1:] if len(rows) > 1 else []

    current = None
    for r in data_rows:
        if r and r[0].strip().upper() == band_id:
            # ensure length
            while len(r) < len(header_row):
                r.append("")
            current = r
            break

    if request.method == "POST":
        # build row in same column order as header
        new_row = [
            request.form.get("band_id", band_id).strip().upper(),
            request.form.get("name", "").strip(),
            request.form.get("email", "").strip(),
            request.form.get("phone", "").strip(),
            request.form.get("emergency_phones", "").strip(),
            request.form.get("emergency_emails", "").strip(),
            request.form.get("age_group", "").strip(),
            request.form.get("condition", "").strip(),
            request.form.get("instructions", "").strip(),
            request.form.get("medical_notes", "").strip(),
            request.form.get("pin", "").strip() or "1234",
            request.form.get("address", "").strip(),
            request.form.get("race", "").strip(),
            request.form.get("gender", "").strip(),
            request.form.get("photo_url", "").strip(),
        ]

        # replace or append
        updated_rows = [header_row]
        replaced = False
        for r in data_rows:
            if r and r[0].strip().upper() == band_id:
                updated_rows.append(new_row)
                replaced = True
            else:
                updated_rows.append(r)
        if not replaced:
            updated_rows.append(new_row)

        with open(file_name, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows(updated_rows)

        return redirect("/admin/preprogram")

    # GET: render form with current values (or blanks)
    values = current or [""] * len(header_row)
    # ensure length
    while len(values) < len(header_row):
        values.append("")

    return f"""
    <!doctype html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Pre‑program {escape(band_id)}</title>
      <style>
        body{{font-family:Arial,Helvetica,sans-serif;background:#07111f;color:white;padding:20px}}
        .card{{max-width:720px;margin:0 auto;background:rgba(255,255,255,0.03);padding:20px;border-radius:12px}}
        input,textarea{{width:100%;padding:10px;border-radius:8px;border:none;margin-top:8px;margin-bottom:12px;background:rgba(255,255,255,0.04);color:white}}
        label{{font-weight:700;color:#7dd3fc}}
        .row{display:flex;gap:12px}
        .row > div{flex:1}
        .btn{padding:10px 14px;border-radius:10px;border:none;background:#22c55e;color:white;font-weight:700;cursor:pointer}
        .back{background:rgba(255,255,255,0.06);color:#94a3b8;text-decoration:none;padding:8px 12px;border-radius:8px}
      </style>
    </head>
    <body>
      <div class="card">
        <a class="back" href="/admin/preprogram">← Back</a>
        <h2>Pre‑program Band {escape(band_id)}</h2>

        <form method="POST">
          <label>Band ID</label>
          <input name="band_id" value="{escape(values[0] or band_id)}" required>

          <label>Full name (public)</label>
          <input name="name" value="{escape(values[1])}">

          <label>Email (optional)</label>
          <input name="email" value="{escape(values[2])}">

          <label>Primary phone</label>
          <input name="phone" value="{escape(values[3])}">

          <label>Emergency phones (comma separated)</label>
          <input name="emergency_phones" value="{escape(values[4])}">

          <label>Emergency emails (comma separated)</label>
          <input name="emergency_emails" value="{escape(values[5])}">

          <label>Age group</label>
          <input name="age_group" value="{escape(values[6])}">

          <label>Condition</label>
          <input name="condition" value="{escape(values[7])}">

          <label>Public instructions</label>
          <textarea name="instructions">{escape(values[8])}</textarea>

          <label>Private medical notes</label>
          <textarea name="medical_notes">{escape(values[9])}</textarea>

          <label>PIN (required to unlock full info)</label>
          <input name="pin" value="{escape(values[10] or '1234')}">

          <label>Address</label>
          <input name="address" value="{escape(values[11])}">

          <label>Race</label>
          <input name="race" value="{escape(values[12])}">

          <label>Gender</label>
          <input name="gender" value="{escape(values[13])}">

          <label>Photo URL</label>
          <input name="photo_url" value="{escape(values[14])}">

          <div style="display:flex;gap:8px;margin-top:12px;">
            <button class="btn" type="submit">Save profile</button>
            <a class="back" href="/admin/preprogram">Cancel</a>
          </div>
        </form>
      </div>
    </body>
    </html>
    """

@app.route("/admin/preprogram/activate", methods=["POST"])
def admin_preprogram_activate():
    if not session.get("logged_in"):
        return redirect("/admin")

    band_id = (request.form.get("band_id") or "").strip().upper()
    if not band_id:
        return redirect("/admin/preprogram")

    # Attempt to activate in the bulk DB
    try:
        activated = activate_band(band_id, actor="admin", ip_address=request.remote_addr)
    except Exception as e:
        # activation failed silently — still redirect to the public profile so admin can inspect
        print("Activation error:", e)
        activated = False

    # Redirect straight to public profile (app's /<band_id> handler)
    return redirect(f"/{band_id}")

# --- END: Bulk pre-program admin pages ---
