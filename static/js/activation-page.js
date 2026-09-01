// Frontend-only activation page logic (no backend integration).
// FUTURE BACKEND INTEGRATION:
// - validateActivationCode(code): currently local validation; replace with API call later.
// - activateDevice(payload): called on confirm; replace with API call later.

(() => {
  'use strict';

  // Helpers
  const qs = (sel, root = document) => root.querySelector(sel);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  // Elements
  const form = qs('#activation-form');
  const nextBtn = qs('#next-button');
  const prevBtn = qs('#prev-button');
  const submitBtn = qs('#submit-button');
  const reviewPanel = qs('#review-panel');
  const backToEditBtn = qs('#back-to-edit');
  const confirmActivationBtn = qs('#confirm-activation');
  const reviewSummary = qs('#review-summary');
  const successPanel = qs('#success-panel');
  const formMessage = qs('#form-message');

  // Steps
  const steps = qsa('.form-section');
  const totalSteps = steps.length;
  let currentStepIndex = 0; // 0-based index matching data-step order

  // Field elements
  const activationCodeEl = qs('#activation-code');
  const deviceIdEl = qs('#device-id');
  const firstNameEl = qs('#first-name');
  const lastNameEl = qs('#last-name');
  const profileTypeEl = qs('#profile-type');
  const emailEl = qs('#email');
  const phoneEl = qs('#phone');
  const confirmOwnershipEl = qs('#confirm-ownership');

  // Error elements map
  const errors = {
    activationCode: qs('#error-activation-code'),
    deviceId: qs('#error-device-id'),
    firstName: qs('#error-first-name'),
    lastName: qs('#error-last-name'),
    email: qs('#error-email'),
    phone: qs('#error-phone'),
    confirm: qs('#error-confirm')
  };

  // Phone formatting helper (US simple)
  function formatUSPhone(value) {
    const digits = value.replace(/\D/g, '').slice(0,10);
    if (digits.length <= 3) return digits;
    if (digits.length <= 6) return `(${digits.slice(0,3)}) ${digits.slice(3)}`;
    return `(${digits.slice(0,3)}) ${digits.slice(3,6)}-${digits.slice(6)}`;
  }

  function setFieldError(elError, message) {
    elError.textContent = message || '';
  }

  // Simple email validator
  function isValidEmail(email) {
    // Simple, client-side-only validation
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(String(email).trim());
  }

  // Activation code validator (frontend only)
  function validateActivationCode(code) {
    // FUTURE BACKEND INTEGRATION: replace this with call to server to verify code validity
    if (!code || !code.trim()) return { ok: false, message: 'Activation code is required.' };
    // Accept any non-empty string for demo purposes, but apply minimal format checks:
    if (code.trim().length < 4) return { ok: false, message: 'Activation code looks too short.' };
    return { ok: true };
  }

  function validateDeviceId(id) {
    if (!id || !id.trim()) return { ok: false, message: 'Safety ID is required.' };
    if (!/^[A-Za-z0-9\-]+$/.test(id.trim())) return { ok: false, message: 'Safety ID may only contain letters, numbers, and hyphens.' };
    return { ok: true };
  }

  function validateProfileFields() {
    let ok = true;
    // First name
    if (!firstNameEl.value.trim()) {
      setFieldError(errors.firstName, 'First name is required.');
      ok = false;
    } else setFieldError(errors.firstName, '');

    // Last name
    if (!lastNameEl.value.trim()) {
      setFieldError(errors.lastName, 'Last name is required.');
      ok = false;
    } else setFieldError(errors.lastName, '');

    // Email
    if (!emailEl.value.trim()) {
      setFieldError(errors.email, 'Email address is required.');
      ok = false;
    } else if (!isValidEmail(emailEl.value.trim())) {
      setFieldError(errors.email, 'Please enter a valid email address.');
      ok = false;
    } else setFieldError(errors.email, '');

    // Phone
    if (!phoneEl.value.trim()) {
      setFieldError(errors.phone, 'Phone number is required.');
      ok = false;
    } else if (phoneEl.value.replace(/\D/g, '').length < 10) {
      setFieldError(errors.phone, 'Please enter a valid U.S. phone number.');
      ok = false;
    } else setFieldError(errors.phone, '');

    // Confirm ownership checkbox
    if (!confirmOwnershipEl.checked) {
      setFieldError(errors.confirm, 'You must confirm you are authorized to activate this Safety ID.');
      ok = false;
    } else setFieldError(errors.confirm, '');

    return ok;
  }

  function updateProgressUI() {
    const stepEls = qsa('.activation-steps li');
    stepEls.forEach((li, idx) => {
      if (idx === currentStepIndex) li.classList.add('is-current');
      else li.classList.remove('is-current');
    });
    // show/hide step fieldsets
    steps.forEach((s, idx) => {
      const hidden = idx !== currentStepIndex;
      s.hidden = hidden;
    });
    prevBtn.hidden = currentStepIndex === 0;
    // Next button shown on steps before final profile step, submit shown at last step (but we use review modal)
    nextBtn.hidden = currentStepIndex >= (totalSteps - 1);
    submitBtn.hidden = true;
    // Clear general messages
    formMessage.textContent = '';
  }

  function goToStep(index) {
    currentStepIndex = Math.max(0, Math.min(index, totalSteps - 1));
    updateProgressUI();
    // move focus to the first input of the visible step for accessibility
    const visible = steps[currentStepIndex];
    const firstInput = visible.querySelector('input, select, textarea, button');
    if (firstInput) firstInput.focus();
  }

  // Initialize
  goToStep(0);

  // Input formatting handlers
  phoneEl.addEventListener('input', (e) => {
    const caret = phoneEl.selectionStart;
    const formatted = formatUSPhone(phoneEl.value);
    phoneEl.value = formatted;
  });

  // Next button handler: validate current step then advance
  nextBtn.addEventListener('click', (e) => {
    e.preventDefault();
    if (currentStepIndex === 0) {
      // validate activation & device id
      const codeResult = validateActivationCode(activationCodeEl.value);
      const deviceResult = validateDeviceId(deviceIdEl.value);
      let ok = true;
      if (!codeResult.ok) {
        setFieldError(errors.activationCode, codeResult.message);
        ok = false;
      } else setFieldError(errors.activationCode, '');

      if (!deviceResult.ok) {
        setFieldError(errors.deviceId, deviceResult.message);
        ok = false;
      } else setFieldError(errors.deviceId, '');

      if (!ok) return;

      // Activation code validated locally — Move to profile step
      goToStep(1);
      return;
    }

    // If somehow on other steps, try to advance if valid
    if (currentStepIndex < totalSteps - 1) {
      goToStep(currentStepIndex + 1);
    }
  });

  prevBtn.addEventListener('click', (e) => {
    e.preventDefault();
    goToStep(currentStepIndex - 1);
  });

  // When user clicks "Continue Activation" from Profile step or earlier, open review if profile validated
  // We'll reuse nextBtn for both steps: if on Profile step, validate and show review
  nextBtn.addEventListener('click', (e) => {
    if (currentStepIndex === 1) {
      // validate entire profile
      const ok = validateProfileFields();
      if (!ok) return;
      // Prepare and show review
      showReview();
    }
  });

  // Prepare review summary
  function showReview() {
    const summaryHtml = `
      <dl>
        <dt>Activation Code</dt><dd>${escapeHtml(activationCodeEl.value)}</dd>
        <dt>Safety ID</dt><dd>${escapeHtml(deviceIdEl.value)}</dd>
        <dt>First name</dt><dd>${escapeHtml(firstNameEl.value)}</dd>
        <dt>Last name</dt><dd>${escapeHtml(lastNameEl.value)}</dd>
        <dt>Profile type</dt><dd>${escapeHtml(profileTypeEl.value)}</dd>
        <dt>Email</dt><dd>${escapeHtml(emailEl.value)}</dd>
        <dt>Phone</dt><dd>${escapeHtml(phoneEl.value)}</dd>
      </dl>
    `;
    reviewSummary.innerHTML = summaryHtml;
    reviewPanel.hidden = false;
    // trap focus in modal (basic)
    const focusEl = reviewPanel.querySelector('button, a, [tabindex]');
    if (focusEl) focusEl.focus();
    // Update progress UI visually to the Review step
    const stepEls = qsa('.activation-steps li');
    stepEls.forEach((li, idx) => {
      li.classList.toggle('is-current', idx === 2);
    });
  }

  // Close review and go back to edit
  backToEditBtn.addEventListener('click', (ev) => {
    ev.preventDefault();
    reviewPanel.hidden = true;
    goToStep(1);
  });

  // Confirm activation (demo only) — do not call any backend
  confirmActivationBtn.addEventListener('click', (ev) => {
    ev.preventDefault();
    reviewPanel.hidden = true;

    // FUTURE BACKEND INTEGRATION:
    // Build payload and send to server here via fetch/AJAX:
    // const payload = { activationCode: activationCodeEl.value.trim(), deviceId: deviceIdEl.value.trim(), firstName: firstNameEl.value.trim(), ... };
    // await activateDevice(payload) // implement server call later

    // For now, show success/demo screen
    successPanel.hidden = false;
    // Update progress UI to 'Complete'
    const stepEls = qsa('.activation-steps li');
    stepEls.forEach((li, idx) => {
      li.classList.toggle('is-current', idx === 3);
    });
    // Hide form to prevent repeated edits
    form.hidden = true;
    formMessage.textContent = '';
  });

  // Prevent real form submission from trying to navigate
  form.addEventListener('submit', (e) => {
    e.preventDefault();
  });

  // Utility: escape HTML for review
  function escapeHtml(str) {
    if (str == null) return '';
    return String(str).replace(/[&<>"']/g, (s) => {
      const m = { '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' };
      return m[s];
    });
  }

})();
