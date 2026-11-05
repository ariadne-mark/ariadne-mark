'use strict';
const form = document.getElementById('feedback-form');
const button = document.getElementById('submit-feedback');
const status = document.getElementById('feedback-status');
fetch('/health').then(r => r.json()).then(config => {
  if (!config.feedback_enabled) { button.disabled = true; status.textContent = 'Anonymous feedback storage is not configured by this operator.'; }
}).catch(() => { status.textContent = 'Service status is unavailable.'; });
form.addEventListener('submit', async event => {
  event.preventDefault(); button.disabled = true;
  try {
    const response = await fetch('/feedback', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({rating: document.getElementById('rating').value, media: document.getElementById('media').value})});
    if (!response.ok) throw Error('feedback');
    status.textContent = 'Thank you. Your anonymous category was recorded.';
  } catch (_) { status.textContent = 'Feedback could not be recorded. Please try again later.'; button.disabled = false; }
});
