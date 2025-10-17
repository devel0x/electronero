const API_BASE = (window.PORTAL_API_URL || "http://localhost:8000").replace(/\/$/, "");

const state = {
  mode: "login",
  token: null,
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
    authPanel.hidden = true;
    dashboard.hidden = false;
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
          </header>
          <div class="node-meta">
            <span>P2P: ${node.p2p_host}:${node.p2p_port}</span>
            <span>RPC: ${node.rpc_host}:${node.rpc_port}</span>
            <span>Wallet: ${node.wallet_address}</span>
          </div>
          <footer class="node-meta">
            <span>Uptime: ${(node.uptime.uptime_ratio * 100).toFixed(2)}%</span>
            <span>Checks: ${node.uptime.successful_checks}/${node.uptime.total_checks}</span>
            <span>Latency: ${node.uptime.average_latency_ms ? node.uptime.average_latency_ms.toFixed(1) : "–"} ms</span>
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
            <span>Uptime Score: ${(reward.uptime.uptime_ratio * 100).toFixed(2)}%</span>
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
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(state.token ? { Authorization: `Bearer ${state.token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || "Request failed");
  }
  return response.status === 204 ? {} : response.json();
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
