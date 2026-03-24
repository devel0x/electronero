const $ = (id) => document.getElementById(id);
const out = (id, data) => ($(id).textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2));
let sessionId = null;

async function post(path, body) {
  const base = $("apiBase").value.trim().replace(/\/$/, "");
  const r = await fetch(`${base}${path}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const j = await r.json();
  if (!r.ok) throw new Error(JSON.stringify(j));
  return j;
}

function sid() {
  if (!sessionId) throw new Error("Create session first");
  return sessionId;
}
const samplePath = () => `/runtime/workspaces/${sid()}/sample.py`;

$("createSession").onclick = async () => {
  try {
    const r = await post("/sessions", {});
    sessionId = r.session_id;
    $("sessionId").textContent = sessionId;
    out("sessionOut", r);
  } catch (e) { out("sessionOut", String(e)); }
};
$("resetSession").onclick = async () => {
  try { out("sessionOut", await post(`/session_reset/${sid()}`, {})); }
  catch (e) { out("sessionOut", String(e)); }
};

$("cloneRepo").onclick = async () => {
  try { out("repoOut", await post("/clone_repo", { session_id: sid(), repo_url: $("repoUrl").value, target_dir: $("targetDir").value })); }
  catch (e) { out("repoOut", String(e)); }
};
$("checkoutRef").onclick = async () => {
  try { out("repoOut", await post("/checkout_ref", { session_id: sid(), repo_dir: $("targetDir").value, ref: $("ref").value })); }
  catch (e) { out("repoOut", String(e)); }
};
$("detectStack").onclick = async () => {
  try { out("repoOut", await post("/detect_stack", { session_id: sid(), repo_dir: $("targetDir").value })); }
  catch (e) { out("repoOut", String(e)); }
};
$("installNode").onclick = async () => {
  try { out("repoOut", await post("/install_node_deps", { session_id: sid(), repo_dir: $("targetDir").value, frozen_lockfile: true })); }
  catch (e) { out("repoOut", String(e)); }
};
$("installPython").onclick = async () => {
  try { out("repoOut", await post("/install_python_deps", { session_id: sid(), repo_dir: $("targetDir").value, requirements_file: "requirements.txt" })); }
  catch (e) { out("repoOut", String(e)); }
};
$("writeEnv").onclick = async () => {
  try { out("repoOut", await post("/write_env_file", { session_id: sid(), repo_dir: $("targetDir").value, env: { NODE_ENV: "production", PORT: $("port").value } })); }
  catch (e) { out("repoOut", String(e)); }
};

$("startProcess").onclick = async () => {
  try { out("procOut", await post("/start_process", { session_id: sid(), repo_dir: $("targetDir").value, name: $("procName").value, command: JSON.parse($("command").value), port: Number($("port").value) })); }
  catch (e) { out("procOut", String(e)); }
};
$("checkPort").onclick = async () => {
  try { out("procOut", await post("/check_port", { session_id: sid(), port: Number($("port").value), host: "127.0.0.1" })); }
  catch (e) { out("procOut", String(e)); }
};
$("httpHealth").onclick = async () => {
  try { out("procOut", await post("/http_health_check", { session_id: sid(), url: `http://127.0.0.1:${Number($("port").value)}` })); }
  catch (e) { out("procOut", String(e)); }
};
$("captureMeta").onclick = async () => {
  try { out("procOut", await post("/capture_preview_metadata", { session_id: sid(), name: $("procName").value, base_url: `http://127.0.0.1:${Number($("port").value)}` })); }
  catch (e) { out("procOut", String(e)); }
};
$("streamLogs").onclick = async () => {
  try { out("procOut", await post("/stream_logs", { session_id: sid(), name: $("procName").value, lines: 120 })); }
  catch (e) { out("procOut", String(e)); }
};
$("stopProcess").onclick = async () => {
  try { out("procOut", await post("/stop_process", { session_id: sid(), name: $("procName").value })); }
  catch (e) { out("procOut", String(e)); }
};
$("exportArtifacts").onclick = async () => {
  try { out("procOut", await post("/export_artifacts", { session_id: sid(), source_dir: $("targetDir").value })); }
  catch (e) { out("procOut", String(e)); }
};

$("runCode").onclick = async () => {
  try { out("safeOut", await post("/run_code", { session_id: sid(), language: "python", code: $("code").value })); }
  catch (e) { out("safeOut", String(e)); }
};
$("installPackage").onclick = async () => {
  try { out("safeOut", await post("/install_package", { session_id: sid(), ecosystem: "python", package: "requests", version: "2.32.3" })); }
  catch (e) { out("safeOut", String(e)); }
};
$("listDir").onclick = async () => {
  try { out("safeOut", await post("/list_directory", { session_id: sid(), path: `/runtime/workspaces/${sid()}` })); }
  catch (e) { out("safeOut", String(e)); }
};
$("writeFile").onclick = async () => {
  try { out("safeOut", await post("/write_file", { session_id: sid(), path: samplePath(), content: "def hello(name):\n    return f'hi {name}'\n" })); }
  catch (e) { out("safeOut", String(e)); }
};
$("readFile").onclick = async () => {
  try { out("safeOut", await post("/read_file", { session_id: sid(), path: samplePath() })); }
  catch (e) { out("safeOut", String(e)); }
};
$("searchFiles").onclick = async () => {
  try { out("safeOut", await post("/search_in_files", { session_id: sid(), root: `/runtime/workspaces/${sid()}`, pattern: "hello" })); }
  catch (e) { out("safeOut", String(e)); }
};
$("functionsMap").onclick = async () => {
  try { out("safeOut", await post("/functions_mapping", { session_id: sid(), path: samplePath() })); }
  catch (e) { out("safeOut", String(e)); }
};
$("bracketTrack").onclick = async () => {
  try { out("safeOut", await post("/bracket_tracker", { session_id: sid(), path: samplePath() })); }
  catch (e) { out("safeOut", String(e)); }
};
$("exportArtifact").onclick = async () => {
  try { out("safeOut", await post("/export_artifact", { session_id: sid(), source_path: samplePath() })); }
  catch (e) { out("safeOut", String(e)); }
};
