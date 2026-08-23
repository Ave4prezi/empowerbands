# Tracking page JS

async function postLocation(bandId, lat, lon, name, contact) {
  try {
    const res = await fetch('/report_location', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ band_id: bandId, lat, lon, reporter_name: name, reporter_contact: contact })
    });
    return res.ok;
  } catch (e) {
    console.error('Report failed', e);
    return false;
  }
}

async function fetchPings(bandId) {
  try {
    const res = await fetch(`/pings/${encodeURIComponent(bandId)}`);
    if (!res.ok) return null;
    return await res.json();
  } catch (e) {
    console.error('Fetch pings failed', e);
    return null;
  }
}

function fmtTime(ts) {
  try {
    const d = new Date(ts);
    return d.toLocaleString();
  } catch (e) { return ts; }
}

window.Tracking = { postLocation, fetchPings, fmtTime };