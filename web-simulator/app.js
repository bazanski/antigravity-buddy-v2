let ws;
const statusBadge = document.getElementById("status-text");
const blobSvg = document.querySelector(".blob-svg");
const promptPanel = document.getElementById("prompt-panel");
const toolNameEl = document.getElementById("tool-name");
const toolHintEl = document.getElementById("tool-hint");

// 🖥️ DOM Bindings for Developer Tabs
const tabMascot = document.getElementById("tab-mascot");
const tabConsole = document.getElementById("tab-console");
const btnMascot = document.getElementById("btn-mascot");
const btnConsole = document.getElementById("btn-console");
const consoleLogs = document.getElementById("console-logs");
const consoleCountBadge = document.getElementById("console-count");

// 🔘 Multi-choice carousel bindings
const optsCarousel = document.getElementById("opts-carousel");
const optLabel = document.getElementById("opt-label");
const optPrev = document.getElementById("opt-prev");
const optNext = document.getElementById("opt-next");
const optIndexHint = document.getElementById("opt-index-hint");
const btnGroupBinary = document.getElementById("btn-group-binary");
const btnGroupMulti = document.getElementById("btn-group-multi");

let selectedOptIdx = 0;
let currentOpts = [];
let activePromptId = null;

let activeTab = "mascot";
let logCount = 0;
let unreadLogs = 0;

// 🎛️ Tab Toggle Switcher
function switchTab(tabName) {
  activeTab = tabName;
  if (tabName === "mascot") {
    tabMascot.classList.remove("hidden");
    tabConsole.classList.add("hidden");
    btnMascot.classList.add("active");
    btnConsole.classList.remove("active");
  } else {
    tabMascot.classList.add("hidden");
    tabConsole.classList.remove("hidden");
    btnMascot.classList.remove("active");
    btnConsole.classList.add("active");
    
    // Reset unread count once tab is viewed
    unreadLogs = 0;
    consoleCountBadge.innerText = logCount;
    consoleCountBadge.classList.remove("new-event");
  }
}

// 🧹 Clear Log Panel
function clearLogs() {
  consoleLogs.innerHTML = '<div class="console-placeholder">Awaiting hook telemetry...</div>';
  logCount = 0;
  unreadLogs = 0;
  consoleCountBadge.innerText = "0";
  consoleCountBadge.classList.remove("new-event");
}

// 🕒 Timestamp Formatter
function formatTime(timestamp) {
  const date = timestamp ? new Date(timestamp * 1000) : new Date();
  const hrs = String(date.getHours()).padStart(2, '0');
  const mins = String(date.getMinutes()).padStart(2, '0');
  const secs = String(date.getSeconds()).padStart(2, '0');
  return `${hrs}:${mins}:${secs}`;
}

// 📝 Append Event Item to Console Logs
function addLogEntry(item) {
  if (!item || !item.event) return;

  // Evict placeholder on first item received
  const placeholder = consoleLogs.querySelector(".console-placeholder");
  if (placeholder) {
    consoleLogs.innerHTML = "";
  }

  logCount++;
  if (activeTab !== "console") {
    unreadLogs++;
    consoleCountBadge.innerText = `+${unreadLogs}`;
    consoleCountBadge.classList.add("new-event");
  } else {
    consoleCountBadge.innerText = logCount;
  }

  // Create Log Container
  const entry = document.createElement("div");
  entry.className = "log-entry";

  const eventName = item.event;
  const timeStr = formatTime(item.timestamp);
  
  // Map badge style based on hook type
  let badgeClass = "badge-other";
  const evLower = eventName.toLowerCase();
  if (evLower.includes("pretooluse") || evLower.includes("beforetool")) {
    badgeClass = "badge-pretooluse";
  } else if (evLower.includes("posttooluse") || evLower.includes("aftertool")) {
    badgeClass = "badge-posttooluse";
  } else if (evLower.includes("promptresolved")) {
    badgeClass = "badge-promptresolved";
  } else if (evLower.includes("sessionstart")) {
    badgeClass = "badge-sessionstart";
  } else if (evLower.includes("beforeagent")) {
    badgeClass = "badge-beforeagent";
  } else if (evLower.includes("beforemodel")) {
    badgeClass = "badge-beforemodel";
  }

  // Generate dynamic readable summaries
  let summary = "";
  if (eventName === "PreToolUse" || eventName === "BeforeTool") {
    const tool = item.prompt?.tool || item.data?.tool_name || "tool";
    summary = `Blocked: ${tool}`;
  } else if (eventName === "PostToolUse" || eventName === "AfterTool") {
    const tool = item.data?.tool_name || "tool";
    summary = `Executed: ${tool}`;
  } else if (eventName === "PromptResolved") {
    const dec = item.data?.decision || "unknown";
    const reason = item.data?.reason || "";
    summary = `Decision: ${dec.toUpperCase()} (${reason})`;
  } else {
    summary = `Event: ${eventName}`;
  }

  entry.innerHTML = `
    <div class="log-header" onclick="this.parentElement.classList.toggle('open')">
      <span class="log-time">${timeStr}</span>
      <span class="log-badge ${badgeClass}">${eventName}</span>
      <span class="log-summary">${summary}</span>
      <span class="log-toggle">▶</span>
    </div>
    <div class="log-details">
      <pre>${JSON.stringify(item, null, 2)}</pre>
    </div>
  `;

  consoleLogs.appendChild(entry);
  
  // Maintain smooth terminal scroll following newly appended logs
  consoleLogs.scrollTop = consoleLogs.scrollHeight;
}

// 🔌 WebSockets Client Pipeline
function connect() {
  ws = new WebSocket("ws://127.0.0.1:38900/ws");
  
  ws.onopen = () => {
    statusBadge.innerText = "ONLINE";
    statusBadge.className = "status-badge connected";
  };
  
  ws.onclose = () => {
    statusBadge.innerText = "OFFLINE";
    statusBadge.className = "status-badge";
    setTimeout(connect, 2000); // Trigger auto-reconnection loop
  };
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === "state_sync") {
      updateMascotState(data.mascot_state);

      // Handle pending_prompts (queue) - show oldest, badge rest
      if (data.pending_prompts && data.pending_prompts.length > 0) {
        showPrompt(data.pending_prompts[0], data.pending_prompts.length);
      } else {
        hidePrompt();
      }

      // Hydrate historical logs on initial connection
      if (data.history && Array.isArray(data.history)) {
        consoleLogs.innerHTML = "";
        logCount = 0;
        const prevTab = activeTab;
        activeTab = "console"; // Temporarily suppress unread badge counts during hydration
        data.history.forEach(item => addLogEntry(item));
        activeTab = prevTab;
        
        // Correct counters for current view
        if (activeTab !== "console") {
          unreadLogs = 0;
          consoleCountBadge.innerText = logCount;
          consoleCountBadge.classList.remove("new-event");
        }
      }
      
      // Capture and display real-time events
      if (data.new_event) {
        addLogEntry(data.new_event);
      }
    }
  };
}

function updateMascotState(state) {
  blobSvg.className = "blob-svg";
  if (state) {
    blobSvg.classList.add(state);
  }
}

function showPrompt(prompt, queueCount) {
  activePromptId = prompt.id;
  toolNameEl.innerText = `executing: ${prompt.tool}`;
  toolHintEl.innerText = prompt.hint;

  // Show queue badge if more than 1 pending
  if (queueCount && queueCount > 1) {
    toolNameEl.innerHTML = `executing: ${prompt.tool} <span class="queue-badge">${queueCount} pending</span>`;
  }

  // Check for multi-choice options
  if (prompt.opts && Array.isArray(prompt.opts) && prompt.opts.length > 1) {
    currentOpts = prompt.opts;
    selectedOptIdx = 0;
    renderOptSelection();
    optsCarousel.style.display = "flex";
    optIndexHint.style.display = "block";
    btnGroupBinary.style.display = "none";
    btnGroupMulti.style.display = "flex";
  } else {
    currentOpts = [];
    optsCarousel.style.display = "none";
    optIndexHint.style.display = "none";
    btnGroupBinary.style.display = "flex";
    btnGroupMulti.style.display = "none";
  }

  promptPanel.classList.remove("hidden");
}

function renderOptSelection() {
  if (currentOpts.length === 0) return;
  optLabel.innerText = currentOpts[selectedOptIdx];
  optIndexHint.innerText = `Option ${selectedOptIdx + 1} / ${currentOpts.length}`;
}

function cycleOption(dir) {
  if (currentOpts.length === 0) return;
  selectedOptIdx = (selectedOptIdx + dir + currentOpts.length) % currentOpts.length;
  renderOptSelection();
}

function resolvePromptMulti() {
  if (currentOpts.length === 0) return;
  const decision = `opt_${selectedOptIdx}`;
  const optLabelText = currentOpts[selectedOptIdx];
  ws.send(JSON.stringify({
    event: "resolve",
    prompt_id: activePromptId,
    decision: decision,
    reason: `Selected: ${optLabelText}`
  }));
}

function hidePrompt() {
  promptPanel.classList.add("hidden");
  currentOpts = [];
  selectedOptIdx = 0;
  activePromptId = null;
}

function resolvePrompt(decision) {
  ws.send(JSON.stringify({
    event: "resolve",
    prompt_id: activePromptId,
    decision: decision,
    reason: "Approved from Web Simulator"
  }));
}

connect();
