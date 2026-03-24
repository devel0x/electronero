const requestBox = document.getElementById('requestBox');
const sessionId = document.getElementById('sessionId');
const output = document.getElementById('output');

function log(title, payload) {
  const ts = new Date().toISOString();
  output.textContent += `[${ts}] ${title}\n${JSON.stringify(payload, null, 2)}\n\n`;
  output.scrollTop = output.scrollHeight;
}

document.querySelectorAll('[data-tool]').forEach(btn => {
  btn.addEventListener('click', () => {
    const tool = btn.dataset.tool;
    requestBox.value = JSON.stringify({ tool, args: {} }, null, 2);
  });
});

document.getElementById('executeBtn').addEventListener('click', async () => {
  try {
    const req = JSON.parse(requestBox.value);
    if (!req.tool) throw new Error('Request must include tool');

    const body = {
      tool: req.tool,
      session_id: sessionId.value.trim(),
      args: req.args || {}
    };

    // Replace `/api/runtime/dispatch` with your control-plane proxied endpoint.
    const res = await fetch('/api/runtime/dispatch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });

    const payload = await res.json();
    if (!res.ok) {
      log(`❌ ${req.tool} failed`, payload);
      return;
    }
    log(`✅ ${req.tool}`, payload);
  } catch (err) {
    log('❌ client_error', { message: err.message });
  }
});

document.getElementById('clearBtn').addEventListener('click', () => {
  output.textContent = '';
});

log('UI ready', { message: 'Aceternity-like cockpit loaded. Connect API to execute tools.' });
