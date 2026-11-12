'use strict';
const $ = id => document.getElementById(id);
let limits = null, controller = null, lastReport = null, mediaKind = 'unknown';
const messages = {
  verified_claim: 'Signature and file binding validated', invalid: 'Invalid or conflicting evidence',
  expired_credential: 'Signing time could not be validated', not_found: 'Not found in this check',
  not_checked: 'Check incomplete or unavailable', recovered_claim: 'Watermark ID recovered',
  single_observation: 'One ID observation; not confirmed',
  multiple_ids: 'Several watermark IDs found'
};
async function getHealth() {
  try {
    const response = await fetch('/health', {cache: 'no-store'});
    if (!response.ok) throw Error('health');
    limits = await response.json();
    $('file-help').textContent = `JPEG, PNG or supported SDR MP4 · up to ${Math.floor(limits.max_upload_bytes / 1048576)} MiB.`;
  } catch (_) { $('file-help').textContent = 'JPEG, PNG or supported SDR MP4. Service status is unavailable.'; }
}
function addField(label, value) {
  if (value === undefined || value === null || value === '') return;
  const term = document.createElement('dt'), detail = document.createElement('dd');
  term.textContent = label; detail.textContent = String(value); $('provenance').append(term, detail);
}
function render(report) {
  lastReport = report; $('result').hidden = false;
  $('result-label').textContent = report.label || 'Unable to complete verification';
  const c = report.c2pa || {}, w = report.watermark || {}, r = report.recovery || {};
  $('credential').textContent = messages[c.status] || 'No supported credential result';
  $('trust').textContent = c.development_identity ? 'Development identity; not a production credential.' : c.issuer_trust === 'trusted' ? 'Issuer validated against this verifier’s trust configuration.' : 'Issuer trust has not been established.';
  $('watermark').textContent = messages[w.status] || 'Watermark check unavailable';
  const search = w.search;
  $('search').textContent = search ? `${search.frames_decoded} frames examined. ${search.file_exhausted ? 'The scan reached the end of the file.' : search.reason === 'two_concordant_ids' ? 'Stopped after two matching ID reads; whole-video coverage is not established.' : 'The search did not exhaust the file.'}` : 'Detection is limited to supported watermark schemes.';
  $('interpretation').textContent = w.status === 'multiple_ids' ? 'Each ID applies only to the positions where it was read. No single source is established for the whole file.' : w.status === 'not_checked' ? 'This is an incomplete check, not evidence that the file is unmarked.' : w.status === 'single_observation' ? 'The detector saw an ID once, but could not confirm it.' : w.status === 'not_found' ? 'No supported mark was recovered. This does not establish human origin.' : w.token && c.status !== 'verified_claim' ? 'The ID is recoverable. It does not authenticate the source of this copy.' : 'Read the credential and watermark evidence separately. Neither establishes factual truth.';
  $('provenance').replaceChildren();
  const record = c.record && c.record.publisher ? c.record : r.record || c.record || {};
  addField('Watermark ID', w.token);
  if (w.status === 'multiple_ids') (w.ids || []).forEach(e => addField(e.status === 'confirmed' ? 'Watermark ID (confirmed)' : 'Watermark ID (unconfirmed)',
    `${e.token}${typeof e.first_time_s === 'number' ? ` · seen ${e.first_time_s.toFixed(2)}–${e.last_time_s.toFixed(2)} s` : ''}`));
  addField('Provider', record.publisher);
  addField('System', record.system ? `${record.system.name} · ${record.system.version}` : null);
  addField('Operation', record.action); addField('Created / altered', record.created_at); addField('Public asset UUID', record.asset_id);
  if (r.manifest && r.manifest.soft_binding === 'matched') addField('Recovered C2PA', `Original manifest recovered · signature ${r.manifest.signature} · file binding ${r.manifest.asset_binding}`);
  if (r.status === 'found') addField('Registry binding', r.content_binding === 'exact_registered_file' ? 'Exact registered file' : 'ID entry found; this copy’s source is not authenticated');
  const redacted = report.public_output && report.public_output.redacted_fields || [];
  $('redaction').textContent = redacted.length ? 'Some system details are withheld by this verifier’s public-output policy. Unreviewed personal or free-text metadata is not displayed.' : '';
  $('json').textContent = JSON.stringify(report, null, 2);
  $('download').textContent = report.signed_report ? 'Download signed report' : 'Download unsigned report';
  $('report-signature').textContent = report.signed_report ? 'The download includes a signed receipt bound to this file. Verify it independently with the operator’s pinned public key.' : 'This verifier has not signed the downloadable report.';
  $('feedback').hidden = !(limits && limits.feedback_enabled);
  $('feedback-status').textContent = '';
  document.querySelectorAll('.feedback').forEach(b => b.disabled = false);
  $('external-feedback').replaceChildren();
  if (limits && limits.feedback_url) {
    const link = document.createElement('a'); link.href = limits.feedback_url;
    link.textContent = 'Report an issue to this verifier’s operator'; link.rel = 'noopener noreferrer';
    $('external-feedback').append(link);
  }
  $('result-label').focus();
}
$('verify-form').addEventListener('submit', async event => {
  event.preventDefault(); const file = $('file').files[0]; if (!file) return;
  const ext = file.name.split('.').pop().toLowerCase();
  if (!['jpg', 'jpeg', 'png', 'mp4'].includes(ext)) { $('progress').textContent = 'Choose a JPEG, PNG or MP4 file.'; return; }
  if (limits && file.size > limits.max_upload_bytes) { $('progress').textContent = 'This file exceeds the verifier’s upload limit.'; return; }
  mediaKind = ext === 'mp4' ? 'video' : 'image';
  controller = new AbortController(); const active = controller;
  const timer = setTimeout(() => active.abort(), 330000);
  $('check').disabled = true; $('cancel').hidden = false; $('progress').textContent = 'Uploading and checking… Video checks can take longer.';
  $('result').hidden = true; lastReport = null;
  $('feedback-status').textContent = ''; document.querySelectorAll('.feedback').forEach(b => b.disabled = false);
  try {
    const response = await fetch('/verify?format=' + ext, {method: 'POST', body: file, headers: {'Content-Type': 'application/octet-stream'}, signal: active.signal});
    const report = await response.json();
    if (!response.ok) {
      const errors = {429: 'The verifier is busy. Please try again shortly.', 408: 'The upload timed out. Try a smaller file or a faster connection.', 413: 'The upload exceeds this verifier’s limit.', 415: 'This format is not supported.', 422: 'The file could not be checked. It may be unsupported or the verification engine may be unavailable.', 504: 'The verification deadline was reached. No origin result was established; the worker was stopped.'};
      $('progress').textContent = errors[response.status] || 'The request could not be completed.';
      return;
    }
    render(report); $('progress').textContent = 'Check complete. The uploaded file has been deleted.';
  } catch (error) { $('progress').textContent = error.name === 'AbortError' ? 'Request cancelled or timed out. No verification result was returned.' : 'Could not reach the verifier. No result was returned.'; }
  finally { clearTimeout(timer); $('check').disabled = false; $('cancel').hidden = true; controller = null;
    $('feedback').hidden = !(limits && limits.feedback_enabled);
  }
});
$('cancel').addEventListener('click', () => controller && controller.abort());
$('download').addEventListener('click', () => {
  if (!lastReport) return;
  const url = URL.createObjectURL(new Blob([JSON.stringify(lastReport.signed_report || lastReport, null, 2)], {type: 'application/json'}));
  const link = document.createElement('a'); link.href = url; link.download = 'ariadne-verification.json'; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
});
document.querySelectorAll('.feedback').forEach(button => button.addEventListener('click', async () => {
  try {
    const response = await fetch('/feedback', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({rating: button.dataset.rating, media: mediaKind})});
    if (!response.ok) throw Error('feedback');
    $('feedback-status').textContent = 'Thank you. Your anonymous category was recorded.';
    document.querySelectorAll('.feedback').forEach(b => b.disabled = true);
  } catch (_) { $('feedback-status').textContent = 'Feedback could not be recorded. Please try again later.'; }
}));
getHealth();
