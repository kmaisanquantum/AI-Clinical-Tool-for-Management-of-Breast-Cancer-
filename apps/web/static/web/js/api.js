/* Shared helpers for the clinical UI. All data comes from the DRF API. */
const CDS = (() => {
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  async function api(path, { method = "GET", body } = {}) {
    const options = {
      method,
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
    if (!["GET", "HEAD", "OPTIONS"].includes(method.toUpperCase())) {
      options.headers["X-CSRFToken"] = getCookie("csrftoken");
    }

    const response = await fetch(path, options);
    if (response.status === 403 && !window.location.pathname.startsWith("/login/")) {
      // Session expired or CSRF rejected: send the user back to sign in.
      window.location.href = "/login/?next=" + encodeURIComponent(window.location.pathname);
      return;
    }
    if (!response.ok) {
      let detail = `Request failed (${response.status})`;
      try {
        const payload = await response.json();
        detail = payload.detail || JSON.stringify(payload);
      } catch (_) {
        /* response had no JSON body */
      }
      throw new Error(detail);
    }
    return response.status === 204 ? null : response.json();
  }

  async function requireAuth() {
    return api("/api/v1/accounts/me/");
  }

  function escape(value) {
    if (value === null || value === undefined) return "";
    return String(value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function titleCase(value) {
    return String(value || "")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }

  function formatDate(value) {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return escape(value);
    return date.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "2-digit",
      hour: "2-digit", minute: "2-digit",
    });
  }

  function sexLabel(code) {
    return { F: "Female", M: "Male", O: "Other", U: "Unknown" }[code] || code;
  }

  function link(href, text) {
    return `<a href="${href}">${escape(text)}</a>`;
  }

  function statusPill(status) {
    return `<span class="pill pill-status-${escape(status)}">${escape(titleCase(status))}</span>`;
  }

  function triagePill(level) {
    return `<span class="pill pill-${escape(String(level).toLowerCase())}">${escape(level)}</span>`;
  }

  function detailRow(label, value) {
    return `<dt>${escape(label)}</dt><dd>${value}</dd>`;
  }

  function errorMessage(err) {
    return escape(err && err.message ? err.message : "Unexpected error");
  }

  function fillTable(selector, rows, toCells) {
    const tbody = document.querySelector(selector);
    if (!tbody) return;
    if (!rows.length) {
      const cols = tbody.closest("table").querySelectorAll("thead th").length;
      tbody.innerHTML = `<tr><td colspan="${cols}" class="muted">No records found.</td></tr>`;
      return;
    }
    tbody.innerHTML = rows
      .map((row) => `<tr>${toCells(row).map((cell) => `<td>${cell}</td>`).join("")}</tr>`)
      .join("");
  }

  async function initShell() {
    const nameEl = document.getElementById("user-name");
    if (!nameEl) return;
    try {
      const user = await requireAuth();
      const label = user.first_name || user.username;
      nameEl.textContent = label;
      document.getElementById("user-initial").textContent = label.charAt(0).toUpperCase();
      document.getElementById("user-roles").textContent =
        user.roles.length ? user.roles.join(", ") : "No role assigned";
    } catch (_) {
      nameEl.textContent = "Not signed in";
    }
  }

  return {
    api, requireAuth, escape, titleCase, formatDate, sexLabel, link,
    statusPill, triagePill, detailRow, errorMessage, fillTable, initShell,
  };
})();
