const API_BASE = (window.PORTAL_API_URL || "http://localhost:8000").replace(/\/$/, "");

const state = {
  mode: "login",
  token: null,
  isAdmin: false,
  email: null,
  adminUnlocked: false,
  adminPortalKey: null,
};

const authPanel = document.getElementById("authPanel");
const dashboard = document.getElementById("dashboard");
const authTitle = document.getElementById("authTitle");
const authSubmit = document.getElementById("authSubmit");
const authForm = document.getElementById("authForm");
const loginToggle = document.getElementById("loginToggle");
const registerToggle = document.getElementById("registerToggle");
const nodeModal = document.getElementById("nodeModal");
const nodeModalToggle = document.getElementById("nodeModalToggle");
const closeModal = document.getElementById("closeModal");
const nodeForm = document.getElementById("nodeForm");
const adminPanel = document.getElementById("adminPanel");
const adminGate = document.getElementById("adminGate");
const adminGateForm = document.getElementById("adminGateForm");
const adminGatePassword = document.getElementById("adminPortalPassword");
const adminGateError = document.getElementById("adminGateError");
const poolBalanceEl = document.getElementById("poolBalance");
const poolDailyEl = document.getElementById("poolDaily");
const poolLastEl = document.getElementById("poolLast");
const adminStatusEl = document.getElementById("adminStatus");
const adminNodesEl = document.getElementById("adminNodes");
const poolAdjustForm = document.getElementById("poolAdjustForm");
const poolDailyForm = document.getElementById("poolDailyForm");
const poolAdjustmentInput = document.getElementById("poolAdjustment");
const dailyDistributionInput = document.getElementById("dailyDistribution");
const exportPayoutsBtn = document.getElementById("exportPayouts");

const totalNodesEl = document.getElementById("totalNodes");
const activeNodesEl = document.getElementById("activeNodes");
const flaggedNodesEl = document.getElementById("flaggedNodes");
const rewardPoolEl = document.getElementById("rewardPool");
const nodesList = document.getElementById("nodesList");
const rewardsList = document.getElementById("rewardsList");

function switchMode(mode) {
  state.mode = mode;
  if (mode === "login") {
    authTitle.textContent = "Login";
    authSubmit.textContent = "Login";
  } else {
    authTitle.textContent = "Register";
    authSubmit.textContent = "Create Account";
  }
}

loginToggle.addEventListener("click", () => switchMode("login"));
registerToggle.addEventListener("click", () => switchMode("register"));

authForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = document.getElementById("email").value.trim();
  const password = document.getElementById("password").value;

  try {
    if (state.mode === "register") {
      await apiRequest("/auth/register", "POST", { email, password });
    }
    const { access_token } = await apiRequest("/auth/login", "POST", { email, password });
    state.token = access_token;
    const claims = decodeToken(access_token);
    state.isAdmin = Boolean(claims?.is_admin);
    state.email = claims?.email || email;
    authPanel.hidden = true;
    dashboard.hidden = false;
    state.adminUnlocked = false;
    state.adminPortalKey = null;

    if (adminPanel) {
      adminPanel.hidden = true;
    }

    if (adminGate) {
      adminGate.hidden = true;
    }

    if (adminGatePassword) {
      adminGatePassword.value = "";
    }

    if (adminGateError) {
      adminGateError.hidden = true;
    }

    if (state.isAdmin) {
      if (adminStatusEl) {
        adminStatusEl.textContent = `Admin • ${state.email}`;
      }
      if (adminGate) {
        adminGate.hidden = false;
      }
    }
    fetchDashboard();
    fetchNodes();
    fetchRewards();
  } catch (error) {
    alert(error.message || "Unable to authenticate");
  }
});

nodeModalToggle.addEventListener("click", () => toggleModal(true));
closeModal.addEventListener("click", () => toggleModal(false));
nodeModal.addEventListener("click", (event) => {
  if (event.target === nodeModal) toggleModal(false);
});

nodeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const payload = {
    name: document.getElementById("nodeName").value.trim(),
    wallet_address: document.getElementById("walletAddress").value.trim(),
    p2p_host: document.getElementById("p2pHost").value.trim(),
    p2p_port: Number(document.getElementById("p2pPort").value),
    rpc_host: document.getElementById("rpcHost").value.trim(),
    rpc_port: Number(document.getElementById("rpcPort").value),
  };

  try {
    await apiRequest("/nodes", "POST", payload);
    toggleModal(false);
    nodeForm.reset();
    fetchNodes();
  } catch (error) {
    alert(error.message || "Unable to register node");
  }
});

poolAdjustForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.adminUnlocked) return;
  const amount = Number(poolAdjustmentInput.value);
  if (!Number.isFinite(amount) || amount === 0) return;
  try {
    const stateData = await apiRequest("/admin/pool/adjust", "POST", { amount });
    updateAdminOverview(stateData);
    poolAdjustmentInput.value = "";
  } catch (error) {
    alert(error.message || "Unable to adjust pool balance");
  }
});

poolDailyForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.adminUnlocked) return;
  const dailyDistribution = Number(dailyDistributionInput.value);
  if (!Number.isFinite(dailyDistribution) || dailyDistribution <= 0) return;
  try {
    const stateData = await apiRequest("/admin/pool/daily", "PUT", {
      daily_distribution: dailyDistribution,
    });
    updateAdminOverview(stateData);
    dailyDistributionInput.value = "";
  } catch (error) {
    alert(error.message || "Unable to update daily distribution");
  }
});

adminGateForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!state.isAdmin) return;
  const password = adminGatePassword?.value.trim();
  if (!password) {
    return;
  }

  state.adminPortalKey = password;
  state.adminUnlocked = true;

  try {
    const overview = await apiRequest("/admin/pool", "GET");
    updateAdminOverview(overview);
    await fetchAdminNodes();
    if (adminPanel) {
      adminPanel.hidden = false;
    }
    if (adminGate) {
      adminGate.hidden = true;
    }
    if (adminGatePassword) {
      adminGatePassword.value = "";
    }
    if (adminGateError) {
      adminGateError.hidden = true;
    }
  } catch (error) {
    state.adminUnlocked = false;
    state.adminPortalKey = null;
    if (adminGateError) {
      adminGateError.hidden = false;
      adminGateError.textContent = error.message || "Invalid admin portal password.";
    }
  }
});

adminNodesEl?.addEventListener("click", async (event) => {
  const button = event.target.closest("button[data-node-id]");
  if (!button) return;
  if (!state.adminUnlocked) return;
  const nodeId = button.dataset.nodeId;
  const action = button.dataset.action;
  try {
    await apiRequest(`/admin/nodes/${nodeId}/${action}`, "POST");
    await fetchAdminNodes();
  } catch (error) {
    alert(error.message || "Unable to update node status");
  }
});

exportPayoutsBtn?.addEventListener("click", async () => {
  if (!state.adminUnlocked) return;
  try {
    const rows = await apiRequest("/admin/exports/payouts", "GET");
    if (!rows.length) {
      alert("No payouts available for export.");
      return;
    }
    downloadCsv(rows);
  } catch (error) {
    alert(error.message || "Unable to export payouts");
  }
});

async function fetchDashboard() {
  try {
    const data = await apiRequest("/dashboard", "GET");
    totalNodesEl.textContent = data.total_nodes;
    activeNodesEl.textContent = data.active_nodes;
    flaggedNodesEl.textContent = data.flagged_nodes;
    rewardPoolEl.textContent = data.reward_pool_daily.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    });
  } catch (error) {
    console.error(error);
  }
}

async function fetchNodes() {
  try {
    const nodes = await apiRequest("/nodes", "GET");
    nodesList.innerHTML = nodes
      .map(
        (node) => `
        <article class="node-card">
          <header class="panel-header">
            <h3>${node.name}</h3>
            ${node.flagged ? '<span class="badge">Flagged</span>' : ""}
            ${node.status === "rejected" ? '<span class="badge danger">Rejected</span>' : ""}
          </header>
          <div class="node-meta">
            <span>P2P: ${node.p2p_host}:${node.p2p_port}</span>
            <span>RPC: ${node.rpc_host}:${node.rpc_port}</span>
            <span>Wallet: ${node.wallet_address}</span>
          </div>
          <div class="node-meta">
            <span>RPC Status: ${(node.last_health && node.last_health.online) ? "Online" : "Offline"}</span>
            <span>P2P Status: ${(node.last_health && node.last_health.p2p_online) ? "Online" : "Offline"}</span>
            <span>Checks: ${node.uptime.successful_checks}/${node.uptime.total_checks}</span>
          </div>
          <footer class="node-meta">
            <span>RPC Uptime: ${(node.uptime.uptime_ratio * 100).toFixed(2)}%</span>
            <span>P2P Uptime: ${(node.uptime.p2p_uptime_ratio * 100).toFixed(2)}%</span>
            <span>RPC Latency: ${node.uptime.average_latency_ms ? node.uptime.average_latency_ms.toFixed(1) : "–"} ms</span>
            <span>P2P Latency: ${node.uptime.p2p_average_latency_ms ? node.uptime.p2p_average_latency_ms.toFixed(1) : "–"} ms</span>
          </footer>
        </article>`
      )
      .join("");
  } catch (error) {
    console.error(error);
  }
}

async function fetchRewards() {
  try {
    const rewards = await apiRequest("/rewards", "GET");
    rewardsList.innerHTML = rewards
      .map(
        (reward) => `
        <article class="reward-card">
          <header class="panel-header">
            <h3>${reward.node.name}</h3>
            ${reward.node.flagged ? '<span class="badge">Bonus Eligible</span>' : ""}
          </header>
          <div class="node-meta">
            <span>Projected Reward: ${reward.projected_reward.toFixed(6)}</span>
            <span>RPC Uptime: ${(reward.uptime.uptime_ratio * 100).toFixed(2)}%</span>
            <span>P2P Uptime: ${(reward.uptime.p2p_uptime_ratio * 100).toFixed(2)}%</span>
          </div>
        </article>`
      )
      .join("");
  } catch (error) {
    console.error(error);
  }
}

function toggleModal(show) {
  nodeModal.classList.toggle("hidden", !show);
}

async function apiRequest(path, method = "GET", body) {
  if (!state.token && !path.startsWith("/auth")) {
    throw new Error("Authentication required");
  }
  const headers = {
    "Content-Type": "application/json",
    ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
  };
  if (path.startsWith("/admin/") && state.adminPortalKey) {
    headers["X-Admin-Portal-Key"] = state.adminPortalKey;
  }
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = await response.json();
      message = data?.detail || data?.message || message;
    } catch (parseError) {
      try {
        message = await response.text();
      } catch (textError) {
        // swallow parsing errors and use default message
      }
    }
    throw new Error(message || "Request failed");
  }
  if (response.status === 204) {
    return {};
  }
  return response.json();
}

function decodeToken(token) {
  try {
    const payload = token.split(".")[1];
    const normalized = payload.replace(/-/g, "+").replace(/_/g, "/");
    const decoded = atob(normalized);
    return JSON.parse(decoded);
  } catch (error) {
    console.error("Unable to decode token", error);
    return {};
  }
}

async function fetchAdminOverview() {
  if (!state.isAdmin || !state.adminUnlocked) return;
  try {
    const data = await apiRequest("/admin/pool", "GET");
    updateAdminOverview(data);
  } catch (error) {
    console.error(error);
  }
}

async function fetchAdminNodes() {
  if (!state.isAdmin || !state.adminUnlocked) return;
  try {
    const entries = await apiRequest("/admin/nodes", "GET");
    adminNodesEl.innerHTML = entries
      .map((entry) => {
        const node = entry.node;
        const uptime =
          node.uptime || {
            uptime_ratio: 0,
            successful_checks: 0,
            total_checks: 0,
            average_latency_ms: null,
            p2p_uptime_ratio: 0,
            p2p_average_latency_ms: null,
          };
        const statusBadge =
          node.status === "rejected"
            ? '<span class="badge danger">Rejected</span>'
            : '<span class="badge">Approved</span>';
        const actionButton =
          node.status === "rejected"
            ? `<button class="button ghost" data-node-id="${node.id}" data-action="reinstate">Reinstate</button>`
            : `<button class="button ghost" data-node-id="${node.id}" data-action="reject">Reject</button>`;
        return `
        <article class="node-card">
          <header class="panel-header">
            <h3>${node.name}</h3>
            ${statusBadge}
            ${node.flagged ? '<span class="badge">Flagged</span>' : ""}
          </header>
          <div class="node-meta">
            <span>Owner: ${entry.owner_email}</span>
            <span>Wallet: ${node.wallet_address}</span>
            <span>Registered: ${formatDate(node.created_at)}</span>
          </div>
          <div class="node-meta">
            <span>P2P: ${node.p2p_host}:${node.p2p_port} • ${(node.last_health && node.last_health.p2p_online) ? "Online" : "Offline"}</span>
            <span>RPC: ${node.rpc_host}:${node.rpc_port} • ${(node.last_health && node.last_health.online) ? "Online" : "Offline"}</span>
            <span>RPC Latency: ${uptime.average_latency_ms ? uptime.average_latency_ms.toFixed(1) : "–"} ms</span>
            <span>P2P Latency: ${uptime.p2p_average_latency_ms ? uptime.p2p_average_latency_ms.toFixed(1) : "–"} ms</span>
          </div>
          <footer class="admin-node-actions">
            <span>RPC Uptime: ${(uptime.uptime_ratio * 100).toFixed(2)}%</span>
            <span>P2P Uptime: ${(uptime.p2p_uptime_ratio * 100).toFixed(2)}%</span>
            <span>Checks: ${uptime.successful_checks}/${uptime.total_checks}</span>
            ${actionButton}
          </footer>
        </article>`;
      })
      .join("");
  } catch (error) {
    console.error(error);
  }
}

function updateAdminOverview(data) {
  poolBalanceEl.textContent = formatNumber(data.current_balance);
  poolDailyEl.textContent = formatNumber(data.daily_distribution);
  poolLastEl.textContent = data.last_distribution ? formatDate(data.last_distribution) : "–";
}

function downloadCsv(rows) {
  const headers = ["node_id", "node_name", "owner_email", "wallet_address", "projected_reward"];
  const csv = [headers.join(",")].concat(
    rows.map((row) =>
      headers
        .map((key) => {
          const value = row[key] ?? "";
          if (typeof value === "string" && value.includes(",")) {
            return `"${value}"`;
          }
          return value;
        })
        .join(",")
    )
  );
  const blob = new Blob([csv.join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `payout-cycle-${new Date().toISOString()}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString(undefined, {
    maximumFractionDigits: 4,
  });
}

function formatDate(value) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function animateStarfield() {
  const canvas = document.getElementById("starfield");
  const ctx = canvas.getContext("2d");
  let width;
  let height;
  let stars;

  function resize() {
    width = canvas.width = window.innerWidth;
    height = canvas.height = window.innerHeight;
    stars = Array.from({ length: Math.floor(width / 4) }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      z: Math.random() * 0.6 + 0.4,
      speed: Math.random() * 0.35 + 0.05,
    }));
  }

  function step() {
    ctx.clearRect(0, 0, width, height);
    for (const star of stars) {
      star.y += star.speed;
      if (star.y > height) star.y = 0;
      const size = star.z * 1.5;
      ctx.fillStyle = `rgba(123, 92, 255, ${star.z})`;
      ctx.fillRect(star.x, star.y, size, size);
    }
    requestAnimationFrame(step);
  }

  resize();
  window.addEventListener("resize", resize);
  requestAnimationFrame(step);
}

animateStarfield();
