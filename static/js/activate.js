(() => {
  "use strict";

  const form = document.getElementById("activation-form");
  const message = document.getElementById("form-message");
  const submitButton = document.getElementById("submit-button");
  const serialInput = document.getElementById("serial-number");

  if (!form || !message || !submitButton || !serialInput) {
    console.error("EmpowerBands activation form elements were not found.");
    return;
  }

  const urlParameters = new URLSearchParams(window.location.search);
  const qrSerialNumber = urlParameters.get("serial");

  if (qrSerialNumber) {
    serialInput.value = qrSerialNumber.trim().toUpperCase();
    serialInput.readOnly = true;
  }

  function showMessage(text, type) {
    message.textContent = text;
    message.className = `form-message ${type}`;
  }

  function normalizeSerial(value) {
    return value.trim().toUpperCase();
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    message.textContent = "";
    message.className = "form-message";

    if (!form.checkValidity()) {
      form.reportValidity();
      return;
    }

    const password = document.getElementById("password").value;
    const confirmPassword =
      document.getElementById("confirm-password").value;

    if (password !== confirmPassword) {
      showMessage("The passwords do not match.", "error");
      return;
    }

    const config = window.EMPOWERBANDS_CONFIG;

    if (
      !config ||
      !config.supabaseUrl ||
      !config.supabaseAnonKey ||
      config.supabaseUrl.includes("YOUR_PROJECT") ||
      config.supabaseAnonKey.includes("YOUR_PUBLIC")
    ) {
      showMessage(
        "Your Supabase Project URL and public anon key must be added to config.js.",
        "error"
      );
      return;
    }

    if (!window.supabase) {
      showMessage(
        "The Supabase library did not load. Refresh the page and try again.",
        "error"
      );
      return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Activating...";

    try {
      const supabaseClient = window.supabase.createClient(
        config.supabaseUrl,
        config.supabaseAnonKey
      );

      const registration = {
        serial_number: normalizeSerial(serialInput.value),
        full_name: document.getElementById("full-name").value.trim(),
        phone:
          document.getElementById("phone").value.trim() || null,
        product_updates:
          document.getElementById("product-updates").checked,
        safety_updates:
          document.getElementById("safety-updates").checked,
        partner_offers:
          document.getElementById("partner-offers").checked
      };

      const email = document
        .getElementById("email")
        .value.trim()
        .toLowerCase();

      const { data: authData, error: authError } =
        await supabaseClient.auth.signUp({
          email: email,
          password: password,
          options: {
            emailRedirectTo: `${window.location.origin}/activate`,
            data: {
              full_name: registration.full_name,
              phone: registration.phone
            }
          }
        });

      if (authError) {
        throw authError;
      }

      if (!authData.session) {
        localStorage.setItem(
          "empowerbands_pending_activation",
          JSON.stringify(registration)
        );

        showMessage(
          "Check your email to confirm your account. Return to this page after confirmation to complete activation.",
          "success"
        );

        return;
      }

      const { error: activationError } =
        await supabaseClient.rpc("claim_empowerband", {
          p_serial_number: registration.serial_number,
          p_full_name: registration.full_name,
          p_phone: registration.phone,
          p_product_updates: registration.product_updates,
          p_safety_updates: registration.safety_updates,
          p_partner_offers: registration.partner_offers
        });

      if (activationError) {
        throw activationError;
      }

      localStorage.removeItem(
        "empowerbands_pending_activation"
      );

      showMessage(
        "Your EmpowerBand has been activated successfully.",
        "success"
      );

      form.reset();

      if (qrSerialNumber) {
        serialInput.value =
          normalizeSerial(qrSerialNumber);
      }
    } catch (error) {
      console.error(error);

      showMessage(
        error.message ||
          "Your EmpowerBand could not be activated.",
        "error"
      );
    } finally {
      submitButton.disabled = false;
      submitButton.textContent =
        "Activate My EmpowerBand";
    }
  });
})();
