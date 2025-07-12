async function refreshStatus() {
  const res = await fetch('/status');
  const data = await res.json();
  document.getElementById('status').textContent = data.running ? 'Running' : 'Idle';
}

async function refreshLogs() {
  const res = await fetch('/logs');
  const data = await res.json();
  const logText = data.logs.map(log => {
    return `[${log.timestamp}] ${log.url} via ${log.proxy || 'no proxy'} → ${log.result}`;
  }).join("\n");
  document.getElementById('logs').textContent = logText;
}

async function start() {
  await fetch('/start');
  await refreshStatus();
  setTimeout(refreshLogs, 2000);
}

async function stop() {
  await fetch('/stop');
  await refreshStatus();
}

setInterval(() => {
  refreshStatus();
  refreshLogs();
}, 5000);

refreshStatus();
refreshLogs();
