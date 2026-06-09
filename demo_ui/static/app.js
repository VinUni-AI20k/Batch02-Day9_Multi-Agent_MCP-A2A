const serviceGrid = document.getElementById("service-grid");
const logsContainer = document.getElementById("logs-container");
const responseBox = document.getElementById("response-box");
const askForm = document.getElementById("ask-form");
const questionInput = document.getElementById("question");
const submitButton = document.getElementById("submit-button");
const requestState = document.getElementById("request-state");
const refreshStatusButton = document.getElementById("refresh-status");
const loadLogsButton = document.getElementById("load-logs");
const uiPort = document.getElementById("ui-port");

uiPort.textContent = window.location.port || "8008";

function setRequestState(label, kind) {
  requestState.textContent = label;
  requestState.className = `badge ${kind}`;
}

function renderServices(services) {
  serviceGrid.innerHTML = "";
  for (const service of services) {
    const card = document.createElement("article");
    card.className = "service-card";

    const title = document.createElement("h3");
    title.textContent = service.label;

    const pill = document.createElement("span");
    pill.className = `status-pill ${service.ok ? "ok" : "bad"}`;
    pill.textContent = service.ok ? "Online" : "Offline";

    const meta = document.createElement("div");
    meta.className = "service-meta";
    meta.textContent = `${service.endpoint}\n${service.detail}`;

    card.append(title, pill, meta);
    serviceGrid.appendChild(card);
  }
}

function renderLogs(logs) {
  logsContainer.innerHTML = "";
  for (const [filename, text] of Object.entries(logs)) {
    const group = document.createElement("section");
    group.className = "log-group";

    const title = document.createElement("h3");
    title.textContent = filename;

    const pre = document.createElement("pre");
    pre.className = "log-box";
    pre.textContent = text || "No log lines yet.";

    group.append(title, pre);
    logsContainer.appendChild(group);
  }
}

async function loadStatus() {
  const response = await fetch("/api/status");
  const payload = await response.json();
  renderServices(payload.services || []);
}

async function loadLogs() {
  const response = await fetch("/api/logs");
  const payload = await response.json();
  renderLogs(payload.logs || {});
}

askForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const question = questionInput.value.trim();
  if (!question) {
    responseBox.textContent = "Please enter a question first.";
    setRequestState("Missing input", "bad");
    return;
  }

  submitButton.disabled = true;
  setRequestState("Running", "busy");
  responseBox.textContent = "Sending request to the customer agent...";

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ question }),
    });
    const payload = await response.json();

    if (payload.ok) {
      responseBox.textContent = payload.answer;
      setRequestState("Completed", "ok");
    } else {
      responseBox.textContent = payload.error || "The request failed.";
      setRequestState("Failed", "bad");
    }
  } catch (error) {
    responseBox.textContent = String(error);
    setRequestState("Failed", "bad");
  } finally {
    submitButton.disabled = false;
    loadLogs().catch(() => {});
  }
});

refreshStatusButton.addEventListener("click", () => {
  loadStatus().catch((error) => {
    responseBox.textContent = String(error);
    setRequestState("Status error", "bad");
  });
});

loadLogsButton.addEventListener("click", () => {
  loadLogs().catch((error) => {
    responseBox.textContent = String(error);
    setRequestState("Log error", "bad");
  });
});

async function bootstrap() {
  await Promise.all([loadStatus(), loadLogs()]);
}

bootstrap().catch((error) => {
  responseBox.textContent = String(error);
  setRequestState("Boot error", "bad");
});

window.setInterval(() => {
  loadStatus().catch(() => {});
}, 8000);

window.setInterval(() => {
  loadLogs().catch(() => {});
}, 10000);
