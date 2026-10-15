// GoThea – zentraler Zugang zum Backend.
// Alle Anfragen ans Backend laufen über apiFetch(): Im Eltern-Modus wird das Token mitgeschickt,
// und meldet der Server „Eltern-Modus erforderlich“ (403), öffnet sich der PIN-Dialog.

// ============================================================================
// Eltern-Token (sessionStorage: gilt bis zum Schließen des Tabs bzw. bis zum Ablauf)
// ============================================================================
const PARENT_TOKEN_STORAGE_KEY = "gothea_parent_token";
const PARENT_EXPIRES_STORAGE_KEY = "gothea_parent_expires_at";

function getParentToken() {
  const token = sessionStorage.getItem(PARENT_TOKEN_STORAGE_KEY);
  const exp = parseInt(sessionStorage.getItem(PARENT_EXPIRES_STORAGE_KEY) || "0", 10);
  if (!token) return null;
  if (exp && exp < Math.floor(Date.now() / 1000)) {
    clearParentToken();
    return null;
  }
  return token;
}

function setParentToken(token, expiresAt) {
  if (token) {
    sessionStorage.setItem(PARENT_TOKEN_STORAGE_KEY, token);
    if (expiresAt) {
      sessionStorage.setItem(PARENT_EXPIRES_STORAGE_KEY, String(expiresAt));
    }
  } else {
    clearParentToken();
  }
}

function clearParentToken() {
  sessionStorage.removeItem(PARENT_TOKEN_STORAGE_KEY);
  sessionStorage.removeItem(PARENT_EXPIRES_STORAGE_KEY);
}

// ============================================================================
// Anfragen
// ============================================================================

// Wie fetch(), liefert die Response. Zusätzlich: options.json wird als JSON-Body gesendet.
async function apiFetch(url, options = {}) {
  options = Object.assign({}, options);
  if (options.json !== undefined) {
    options.body = JSON.stringify(options.json);
    options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers);
    delete options.json;
  }

  const token = getParentToken();
  if (token) {
    if (options.headers instanceof Headers) {
      if (!options.headers.has("X-Parent-Token")) {
        options.headers.set("X-Parent-Token", token);
      }
    } else if (Array.isArray(options.headers)) {
      options.headers.push(["X-Parent-Token", token]);
    } else {
      options.headers = Object.assign({}, options.headers, { "X-Parent-Token": token });
    }
  }

  const response = await fetch(url, options);

  if (response.status === 403) {
    try {
      const data = await response.clone().json();
      if (data && typeof data.detail === "string" && data.detail.includes("Eltern-Modus")) {
        openParentPinModal("Für diese Aktion ist der Eltern-Modus erforderlich.");
      }
    } catch (_) {}
  }

  return response;
}

// Fehler einer API-Anfrage; message ist die Meldung des Servers (detail), sonst „HTTP <Status>“.
class ApiError extends Error {
  constructor(message, status, url) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.url = url;
  }
}

// Liefert die JSON-Antwort (null bei 204) oder wirft ApiError.
async function apiJson(url, options = {}) {
  const res = await apiFetch(url, options);
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    const detail = data && typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
    throw new ApiError(detail, res.status, url);
  }
  if (res.status === 204) return null;
  return res.json();
}
