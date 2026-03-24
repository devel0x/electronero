const $ = (id) => document.getElementById(id);
const out = (id, data) => ($(id).textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2));

let sessionId = null;

async function api(path, payload) {
  const base = $("apiBase").value.trim().replace(/\/$/, "");
  const res = await fetch(`${base}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload ?? {}),
  });
  const body = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(body));
  return body;
}

async function apiGet(path) {
  const base = $("apiBase").value.trim().replace(/\/$/, "");
  const res = await fetch(`${base}${path}`);
  const body = await res.json();
  if (!res.ok) throw new Error(JSON.stringify(body));
  return body;
}

$("createSession").onclick = async () => {
  try {
    const data = await api("/sessions", {
      max_execution_seconds: 15,
      max_output_bytes: 50000,
      session_ttl_seconds: 3600,
      network_mode: "allowlisted",
    });
    sessionId = data.session_id;
    $("sessionId").textContent = sessionId;
    out("sessionPolicy", data.policy);
  } catch (err) {
    out("sessionPolicy", String(err));
  }
};

$("resetSession").onclick = async () => {
  if (!sessionId) return out("sessionPolicy", "Create session first");
  try { out("sessionPolicy", await api(`/session_reset/${sessionId}`)); }
  catch (err) { out("sessionPolicy", String(err)); }
};

$("runCode").onclick = async () => {
  if (!sessionId) return out("runCodeOut", "Create session first");
  try {
    out("runCodeOut", await api("/run_code", {
      session_id: sessionId,
      language: $("language").value,
      code: $("code").value,
    }));
  } catch (err) { out("runCodeOut", String(err)); }
};

$("installPackage").onclick = async () => {
  if (!sessionId) return out("installOut", "Create session first");
  try {
    out("installOut", await api("/install_package", {
      session_id: sessionId,
      ecosystem: $("ecosystem").value,
      package: $("pkgName").value,
      version: $("pkgVersion").value || null,
    }));
  } catch (err) { out("installOut", String(err)); }
};

$("listDir").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try { out("fsOut", await api("/list_directory", { session_id: sessionId, path: $("path").value })); }
  catch (err) { out("fsOut", String(err)); }
};

$("writeFile").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/write_file", {
      session_id: sessionId,
      path: `/runtime/workspaces/${sessionId}/sample.py`,
      content: "def hello(name):\n    print(f'hello {name}')\n\nhello('runtime')\n",
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("readFile").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/read_file", {
      session_id: sessionId,
      path: `/runtime/workspaces/${sessionId}/sample.py`,
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("searchFiles").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/search_in_files", {
      session_id: sessionId,
      root: `/runtime/workspaces/${sessionId}`,
      pattern: "runtime",
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("functionsMap").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/functions_mapping", {
      session_id: sessionId,
      path: `/runtime/workspaces/${sessionId}/sample.py`,
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("bracketTrack").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/bracket_tracker", {
      session_id: sessionId,
      path: `/runtime/workspaces/${sessionId}/sample.py`,
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("exportArtifact").onclick = async () => {
  if (!sessionId) return out("fsOut", "Create session first");
  try {
    out("fsOut", await api("/export_artifact", {
      session_id: sessionId,
      source_path: `/runtime/workspaces/${sessionId}/sample.py`,
    }));
  } catch (err) { out("fsOut", String(err)); }
};

$("refreshLogs").onclick = async () => {
  try {
    const logs = await apiGet("/logs?limit=50");
    out("logsOut", logs);
  } catch (err) {
    out("logsOut", String(err));
  }
};
