// Theme toggle (persisted in localStorage — this is a real server-rendered
// site running on the user's own machine, not a claude.ai artifact).
(function () {
  const stored = localStorage.getItem("campusfit-theme");
  if (stored === "dark") document.documentElement.setAttribute("data-theme", "dark");
})();

function toggleTheme() {
  const root = document.documentElement;
  const isDark = root.getAttribute("data-theme") === "dark";
  if (isDark) {
    root.removeAttribute("data-theme");
    localStorage.setItem("campusfit-theme", "light");
  } else {
    root.setAttribute("data-theme", "dark");
    localStorage.setItem("campusfit-theme", "dark");
  }
}

function toggleNav() {
  document.querySelector(".nav-links").classList.toggle("open");
}

// Weekly activity chart on the student dashboard (Chart.js loaded via CDN).
function renderWeeklyChart(labels, minutes) {
  const el = document.getElementById("weeklyChart");
  if (!el || typeof Chart === "undefined") return;
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  new Chart(el, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [{
        label: "Minutes",
        data: minutes,
        backgroundColor: "#20c997",
        borderRadius: 6,
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        x: { ticks: { color: isDark ? "#93a4b8" : "#6b7c8f" }, grid: { display: false } },
        y: { beginAtZero: true, ticks: { color: isDark ? "#93a4b8" : "#6b7c8f" }, grid: { color: isDark ? "#26364a" : "#e8edf2" } },
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Interactive AI Coach Drawer & Chat
// ---------------------------------------------------------------------------

function toggleCoachDrawer() {
  const drawer = document.getElementById("coachDrawer");
  if (!drawer) return;
  drawer.classList.toggle("open");
  if (drawer.classList.contains("open")) {
    const input = document.getElementById("coachInput");
    if (input) setTimeout(() => input.focus(), 150);
  }
}

function askCoachPrompt(promptText) {
  const input = document.getElementById("coachInput");
  if (input) {
    input.value = promptText;
    sendCoachMessage();
  }
}

function formatCoachText(text) {
  if (!text) return "";
  // Escape basic HTML
  let clean = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  // Bold **text**
  clean = clean.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  // Line breaks
  clean = clean.replace(/\n/g, "<br>");
  return clean;
}

async function sendCoachMessage() {
  const input = document.getElementById("coachInput");
  const chatBody = document.getElementById("coachChatBody");
  const sendBtn = document.getElementById("coachSendBtn");
  if (!input || !chatBody) return;

  const msg = input.value.trim();
  if (!msg) return;

  // Render user bubble
  const userBubble = document.createElement("div");
  userBubble.className = "coach-bubble coach-user";
  userBubble.textContent = msg;
  chatBody.appendChild(userBubble);
  input.value = "";
  chatBody.scrollTop = chatBody.scrollHeight;

  // Render typing indicator
  const typingBubble = document.createElement("div");
  typingBubble.className = "coach-bubble coach-assistant";
  typingBubble.id = "coachTypingIndicator";
  typingBubble.innerHTML = "<em>AI Coach is thinking... 💭</em>";
  chatBody.appendChild(typingBubble);
  chatBody.scrollTop = chatBody.scrollHeight;

  if (sendBtn) sendBtn.disabled = true;

  try {
    const resp = await fetch("/api/coach/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: msg })
    });

    const data = await resp.json();
    typingBubble.remove();

    const coachBubble = document.createElement("div");
    coachBubble.className = "coach-bubble coach-assistant";
    coachBubble.innerHTML = formatCoachText(data.reply || "Sorry, I could not process that request.");
    chatBody.appendChild(coachBubble);

    // Render quick reply suggestions if available
    if (data.quick_replies && data.quick_replies.length > 0) {
      const quickRow = document.createElement("div");
      quickRow.className = "quick-prompts-row";
      data.quick_replies.forEach(qr => {
        const chip = document.createElement("button");
        chip.className = "chip-btn";
        chip.textContent = qr;
        chip.onclick = () => askCoachPrompt(qr);
        quickRow.appendChild(chip);
      });
      chatBody.appendChild(quickRow);
    }
  } catch (err) {
    typingBubble.remove();
    const errBubble = document.createElement("div");
    errBubble.className = "coach-bubble coach-assistant";
    errBubble.textContent = "Coach network error: " + err.message;
    chatBody.appendChild(errBubble);
  } finally {
    if (sendBtn) sendBtn.disabled = false;
    chatBody.scrollTop = chatBody.scrollHeight;
  }
}

// ---------------------------------------------------------------------------
// Send Daily Email Digest Action
// ---------------------------------------------------------------------------

async function sendDailyEmailDigest() {
  const btn = document.getElementById("sendEmailBtn");
  const statusDiv = document.getElementById("emailStatusMsg");
  if (!btn) return;

  const originalText = btn.innerHTML;
  btn.innerHTML = "⏳ Preparing &amp; Sending...";
  btn.disabled = true;
  if (statusDiv) statusDiv.style.display = "none";

  try {
    const res = await fetch("/api/notifications/send-daily-digest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });

    const data = await res.json();
    btn.innerHTML = data.success ? "✅ Done!" : "❌ Failed";

    if (statusDiv) {
      statusDiv.style.display = "block";
      if (data.success) {
        if (data.is_smtp) {
          statusDiv.className = "alert";
          statusDiv.style.background = "rgba(16, 185, 129, 0.15)";
          statusDiv.style.color = "#065f46";
          statusDiv.style.border = "1px solid #10b981";
          statusDiv.innerHTML = `<strong>🎉 Real Email Delivered!</strong> Sent directly to your inbox at <u>${data.recipient}</u>. Check your inbox/spam folder. <button class="btn small" style="margin-left:8px;" onclick="openEmailPreviewModal()">👁️ View Email</button>`;
        } else {
          statusDiv.className = "alert";
          statusDiv.style.background = "rgba(59, 130, 246, 0.12)";
          statusDiv.style.color = "#1e40af";
          statusDiv.style.border = "1px solid #3b82f6";
          statusDiv.innerHTML = `<strong>📧 Email Report Prepared!</strong> To have it land in your real Gmail/Outlook account, enter your SMTP details. <button class="btn small" style="margin-left:6px;" onclick="openSettingsModal()">⚙️ Setup SMTP</button> <button class="btn small ghost" style="margin-left:4px;" onclick="openEmailPreviewModal()">👁️ View Email Preview</button>`;
        }
      } else {
        statusDiv.className = "alert";
        statusDiv.style.background = "rgba(239, 68, 68, 0.15)";
        statusDiv.style.color = "#991b1b";
        statusDiv.style.border = "1px solid #ef4444";
        statusDiv.innerHTML = `<strong>⚠️ Dispatch Notice:</strong> ${data.error || "Could not dispatch email."} <button class="btn small" style="margin-left:8px;" onclick="openSettingsModal()">⚙️ Check Settings</button> <button class="btn small ghost" onclick="openEmailPreviewModal()">👁️ View Preview</button>`;
      }
    }
  } catch (err) {
    if (statusDiv) {
      statusDiv.style.display = "block";
      statusDiv.className = "alert";
      statusDiv.textContent = "Connection error: " + err.message;
    }
  } finally {
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }, 4000);
  }
}

// ---------------------------------------------------------------------------
// Email Preview Modal Handlers
// ---------------------------------------------------------------------------

async function openEmailPreviewModal() {
  const modal = document.getElementById("emailPreviewModal");
  const frame = document.getElementById("emailPreviewFrame");
  if (!modal) return;
  modal.classList.add("open");

  try {
    const res = await fetch("/api/notifications/preview-latest");
    const data = await res.json();
    if (data.html && frame) {
      frame.srcdoc = data.html;
    }
  } catch (e) {
    if (frame) frame.srcdoc = "<p style='padding:20px;'>Could not load email preview.</p>";
  }
}

function closeEmailPreviewModal() {
  const modal = document.getElementById("emailPreviewModal");
  if (modal) modal.classList.remove("open");
}

// ---------------------------------------------------------------------------
// Settings Modal Handlers (SMTP & Gemini Key)
// ---------------------------------------------------------------------------

async function openSettingsModal() {
  const modal = document.getElementById("settingsModal");
  if (!modal) return;
  modal.classList.add("open");

  const statusMsg = document.getElementById("settingsStatusMsg");
  if (statusMsg) statusMsg.style.display = "none";

  try {
    const res = await fetch("/api/settings");
    const data = await res.json();
    if (data.smtp) {
      if (document.getElementById("cfgSmtpHost")) document.getElementById("cfgSmtpHost").value = data.smtp.host || "";
      if (document.getElementById("cfgSmtpPort")) document.getElementById("cfgSmtpPort").value = data.smtp.port || "587";
      if (document.getElementById("cfgSmtpUser")) document.getElementById("cfgSmtpUser").value = data.smtp.user || "";
      if (document.getElementById("cfgSmtpFrom")) document.getElementById("cfgSmtpFrom").value = data.smtp.from || "";
      if (data.smtp.has_password && document.getElementById("cfgSmtpPass")) {
        document.getElementById("cfgSmtpPass").placeholder = "Password saved (leave blank to keep)";
      }
    }
  } catch (e) {
    console.error("Could not load settings:", e);
  }
}

function closeSettingsModal() {
  const modal = document.getElementById("settingsModal");
  if (modal) modal.classList.remove("open");
}

function applySmtpPreset(type) {
  const host = document.getElementById("cfgSmtpHost");
  const port = document.getElementById("cfgSmtpPort");
  const from = document.getElementById("cfgSmtpFrom");

  if (type === "gmail") {
    if (host) host.value = "smtp.gmail.com";
    if (port) port.value = "587";
    if (from) from.value = "CampusFit Coach <notifications@campusfit.com>";
  } else if (type === "outlook") {
    if (host) host.value = "smtp.office365.com";
    if (port) port.value = "587";
    if (from) from.value = "CampusFit Coach <notifications@campusfit.com>";
  } else if (type === "custom") {
    if (host) host.value = "";
    if (port) port.value = "587";
  }
}

async function saveAppSettings() {
  const host = document.getElementById("cfgSmtpHost") ? document.getElementById("cfgSmtpHost").value.trim() : "";
  const port = document.getElementById("cfgSmtpPort") ? document.getElementById("cfgSmtpPort").value.trim() : "587";
  const user = document.getElementById("cfgSmtpUser") ? document.getElementById("cfgSmtpUser").value.trim() : "";
  const pass = document.getElementById("cfgSmtpPass") ? document.getElementById("cfgSmtpPass").value.trim() : "";
  const from = document.getElementById("cfgSmtpFrom") ? document.getElementById("cfgSmtpFrom").value.trim() : "";
  const gemini = document.getElementById("cfgGeminiKey") ? document.getElementById("cfgGeminiKey").value.trim() : "";
  const statusMsg = document.getElementById("settingsStatusMsg");

  const payload = {
    smtp_host: host,
    smtp_port: port,
    smtp_user: user,
    smtp_from: from
  };
  if (pass) payload.smtp_pass = pass;
  if (gemini) payload.gemini_api_key = gemini;

  try {
    const res = await fetch("/api/settings", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (statusMsg) {
      statusMsg.style.display = "block";
      statusMsg.style.background = "rgba(16, 185, 129, 0.15)";
      statusMsg.style.color = "#065f46";
      statusMsg.textContent = "✅ Settings saved successfully! " + (data.smtp_configured ? "Real SMTP is now ACTIVE." : "Fill username and password to enable real email sending.");
    }
  } catch (e) {
    if (statusMsg) {
      statusMsg.style.display = "block";
      statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
      statusMsg.style.color = "#991b1b";
      statusMsg.textContent = "Failed to save: " + e.message;
    }
  }
}

async function testSmtpConnection() {
  const statusMsg = document.getElementById("settingsStatusMsg");
  if (statusMsg) {
    statusMsg.style.display = "block";
    statusMsg.style.background = "rgba(37, 99, 235, 0.12)";
    statusMsg.style.color = "#1e40af";
    statusMsg.textContent = "⏳ Testing SMTP connection... sending verification email...";
  }

  // First save current inputs
  await saveAppSettings();

  try {
    const res = await fetch("/api/settings/test-email", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({})
    });
    const data = await res.json();
    if (statusMsg) {
      if (data.success) {
        statusMsg.style.background = "rgba(16, 185, 129, 0.15)";
        statusMsg.style.color = "#065f46";
        statusMsg.textContent = "🎉 SUCCESS! " + data.message;
      } else {
        statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
        statusMsg.style.color = "#991b1b";
        statusMsg.textContent = "❌ Connection Failed: " + (data.error || "Please verify credentials.");
      }
    }
  } catch (e) {
    if (statusMsg) {
      statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
      statusMsg.style.color = "#991b1b";
      statusMsg.textContent = "Error testing connection: " + e.message;
    }
  }
}
