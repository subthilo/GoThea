// ============================================================================
// Eltern-Modus & Rechte-Verwaltung (Thea-Modus vs. Eltern-Modus)
// ============================================================================
let isParentActive = false;
let isDefaultParentPin = false;

// UI-Synchronisation
function updateParentModeUI(active, isDefault = isDefaultParentPin) {
  isParentActive = Boolean(active);
  isDefaultParentPin = Boolean(isDefault);

  // Body classes
  document.body.classList.toggle("parent-mode-active", isParentActive);
  document.body.classList.toggle("thea-mode-active", !isParentActive);

  // Header Pill
  const pillBtn = document.getElementById("btn-parent-toggle");
  const pillIcon = document.getElementById("parent-pill-icon");
  const pillText = document.getElementById("parent-pill-text");

  if (pillBtn && pillIcon && pillText) {
    if (isParentActive) {
      pillBtn.classList.add("is-parent-active");
      pillIcon.innerHTML = '<img src="/static/Icons/Erwachsener.svg" class="pill-svg-icon" alt="Eltern-Modus">';
      pillText.textContent = "Eltern-Modus (Aktiv)";
      pillBtn.title = "Klicken, um den Eltern-Modus zu sperren (zurück zu Thea)";
    } else {
      pillBtn.classList.remove("is-parent-active");
      pillIcon.innerHTML = '<img src="/static/Icons/Kind.svg" class="pill-svg-icon" alt="Thea-Modus">';
      pillText.textContent = "Thea-Modus";
      pillBtn.title = "Klicken, um Eltern-PIN einzugeben (Einstellungen & Prüfungen freischalten)";
    }
  }

  // Profile Card
  const profBadge = document.getElementById("prof-parent-badge");
  const secLocked = document.getElementById("parent-security-locked");
  const secUnlocked = document.getElementById("parent-security-unlocked");
  const defPinWarn = document.getElementById("parent-default-pin-warn");
  const defPinHint = document.getElementById("parent-pin-default-hint");

  if (profBadge) {
    profBadge.textContent = isParentActive ? "Eltern-Modus aktiv" : "Thea-Modus aktiv";
  }
  if (secLocked) secLocked.style.display = isParentActive ? "none" : "block";
  if (secUnlocked) secUnlocked.style.display = isParentActive ? "block" : "none";
  if (defPinWarn) defPinWarn.style.display = (isParentActive && isDefaultParentPin) ? "block" : "none";
  if (defPinHint) defPinHint.style.display = isDefaultParentPin ? "block" : "none";

  // Formular-Sperre im Profil für Thea
  const profInputs = document.querySelectorAll("#tab-profile input, #tab-profile select");
  profInputs.forEach((el) => {
    if (el.id.startsWith("input-current-pin") || el.id.startsWith("input-new-pin")) return;
    el.disabled = !isParentActive;
  });

  if (currentDetailSubjectId) {
    loadSubjectScores(currentDetailSubjectId);
  }
}

async function checkParentAuthStatus() {
  try {
    const res = await fetch("/api/v1/auth/parent/status", {
      headers: getParentToken() ? { "X-Parent-Token": getParentToken() } : {}
    });
    if (res.ok) {
      const data = await res.json();
      updateParentModeUI(data.is_parent, data.is_default_pin);
    }
  } catch (err) {
    console.warn("Konnte Eltern-Status nicht abrufen:", err);
  }
}

// PIN Modal Öffnen / Schließen
function openParentPinModal(customHint = "") {
  const modal = document.getElementById("modal-parent-pin");
  const pinInput = document.getElementById("input-parent-pin");
  const errorBox = document.getElementById("parent-pin-error");
  if (!modal) return;

  if (errorBox) {
    if (customHint) {
      errorBox.textContent = customHint;
      errorBox.style.display = "block";
      errorBox.style.background = "rgba(99, 102, 241, 0.12)";
      errorBox.style.color = "var(--accent-light)";
      errorBox.style.borderColor = "rgba(99, 102, 241, 0.35)";
    } else {
      errorBox.style.display = "none";
    }
  }

  if (pinInput) {
    pinInput.value = "";
    pinInput.type = "password";
  }

  const eyeBtn = document.getElementById("btn-toggle-pin-visibility");
  if (eyeBtn) {
    eyeBtn.innerHTML = `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
  }

  modal.style.display = "flex";
  setTimeout(() => pinInput && pinInput.focus(), 80);
}

function closeParentPinModal() {
  const modal = document.getElementById("modal-parent-pin");
  if (modal) modal.style.display = "none";
}

// Entsperren via PIN
async function submitParentPin() {
  const pinInput = document.getElementById("input-parent-pin");
  const errorBox = document.getElementById("parent-pin-error");
  const pin = (pinInput ? pinInput.value : "").trim();

  if (!pin) {
    if (errorBox) {
      errorBox.textContent = "Bitte gib eine PIN ein.";
      errorBox.style.display = "block";
      errorBox.style.background = "rgba(239, 68, 68, 0.12)";
      errorBox.style.color = "#f87171";
      errorBox.style.borderColor = "rgba(239, 68, 68, 0.35)";
    }
    return;
  }

  try {
    const res = await fetch("/api/v1/auth/parent/unlock", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ pin })
    });

    if (res.ok) {
      const data = await res.json();
      setParentToken(data.token, data.expires_at);
      updateParentModeUI(true, data.is_default_pin);
      closeParentPinModal();
    } else {
      const errData = await res.json().catch(() => ({}));
      const msg = errData.detail || "Falsche PIN. Bitte erneut versuchen.";
      if (errorBox) {
        errorBox.textContent = msg;
        errorBox.style.display = "block";
        errorBox.style.background = "rgba(239, 68, 68, 0.12)";
        errorBox.style.color = "#f87171";
        errorBox.style.borderColor = "rgba(239, 68, 68, 0.35)";
      }
      if (pinInput) {
        pinInput.value = "";
        pinInput.focus();
      }
    }
  } catch (err) {
    if (errorBox) {
      errorBox.textContent = "Netzwerkfehler beim Entsperren.";
      errorBox.style.display = "block";
    }
  }
}

// Sofort sperren
function lockParentMode() {
  clearParentToken();
  updateParentModeUI(false);
}

// PIN ändern
async function handleParentPinChange() {
  const curInput = document.getElementById("input-current-pin");
  const newInput = document.getElementById("input-new-pin");
  const confInput = document.getElementById("input-new-pin-confirm");
  const msgBox = document.getElementById("parent-pin-change-msg");

  const currentPin = (curInput ? curInput.value : "").trim();
  const newPin = (newInput ? newInput.value : "").trim();
  const confirmPin = (confInput ? confInput.value : "").trim();

  if (!currentPin || !newPin) {
    if (msgBox) {
      msgBox.textContent = "❌ Bitte alle Felder ausfüllen.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  if (newPin !== confirmPin) {
    if (msgBox) {
      msgBox.textContent = "❌ Die neue PIN stimmt nicht mit der Bestätigung überein.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  if (!/^\d{4,8}$/.test(newPin)) {
    if (msgBox) {
      msgBox.textContent = "❌ Die PIN muss aus 4 bis 8 Ziffern bestehen.";
      msgBox.style.color = "var(--warning)";
    }
    return;
  }

  try {
    const res = await apiFetch("/api/v1/auth/parent/change-pin", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ current_pin: currentPin, new_pin: newPin })
    });

    if (res.ok) {
      const data = await res.json();
      setParentToken(data.token, data.expires_at);
      updateParentModeUI(true, false);
      if (curInput) curInput.value = "";
      if (newInput) newInput.value = "";
      if (confInput) confInput.value = "";
      if (msgBox) {
        msgBox.textContent = "✅ PIN erfolgreich geändert! Die neue PIN ist ab sofort aktiv.";
        msgBox.style.color = "var(--success)";
        setTimeout(() => { if (msgBox) msgBox.textContent = ""; }, 4000);
      }
    } else {
      const errData = await res.json().catch(() => ({}));
      if (msgBox) {
        msgBox.textContent = `❌ ${errData.detail || "Fehler beim Ändern der PIN."}`;
        msgBox.style.color = "var(--warning)";
      }
    }
  } catch (err) {
    if (msgBox) {
      msgBox.textContent = "❌ Netzwerkfehler.";
      msgBox.style.color = "var(--warning)";
    }
  }
}

// Event Listeners registrieren
function setupParentModeEvents() {
  const toggleBtn = document.getElementById("btn-parent-toggle");
  if (toggleBtn) {
    toggleBtn.addEventListener("click", () => {
      if (isParentActive) {
        lockParentMode();
      } else {
        openParentPinModal();
      }
    });
  }

  const profUnlockBtn = document.getElementById("btn-prof-unlock-parent");
  if (profUnlockBtn) {
    profUnlockBtn.addEventListener("click", () => openParentPinModal());
  }

  const profLockBtn = document.getElementById("btn-prof-lock-parent");
  if (profLockBtn) {
    profLockBtn.addEventListener("click", () => lockParentMode());
  }

  const closeBtn = document.getElementById("btn-close-parent-pin-modal");
  if (closeBtn) closeBtn.addEventListener("click", closeParentPinModal);

  const cancelBtn = document.getElementById("btn-cancel-parent-pin");
  if (cancelBtn) cancelBtn.addEventListener("click", closeParentPinModal);

  const submitBtn = document.getElementById("btn-submit-parent-pin");
  if (submitBtn) submitBtn.addEventListener("click", submitParentPin);

  const pinInput = document.getElementById("input-parent-pin");
  if (pinInput) {
    pinInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        submitParentPin();
      }
    });
  }

  const eyeBtn = document.getElementById("btn-toggle-pin-visibility");
  if (eyeBtn && pinInput) {
    eyeBtn.addEventListener("click", () => {
      const isPassword = pinInput.type === "password";
      pinInput.type = isPassword ? "text" : "password";
      eyeBtn.innerHTML = isPassword
        ? `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>`
        : `<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>`;
    });
  }

  const changeBtn = document.getElementById("btn-change-parent-pin");
  if (changeBtn) changeBtn.addEventListener("click", handleParentPinChange);
}

