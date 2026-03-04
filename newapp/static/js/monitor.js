let ws = null;
let reconnectAttempts = 0;

const MAX_RECONNECT = 10;
const MAX_EVENT_ROWS = 120;
const HEARTBEAT_MS = 15000;

const eventCounts = {
  total: 0,
  ml: 0,
  blocks: 0,
  indicators: 0
};

const activeMonitors = new Set();

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function formatTime(timestamp) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return '--:--:--';
  }

  return date.toLocaleTimeString('pt-BR', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  });
}

function formatPrice(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric.toFixed(2) : '--';
}

function formatProbability(value) {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? `${(numeric * 100).toFixed(2)}` : '--';
}

function getSeverityMeta(severity) {
  switch (severity) {
    case 'ALERT':
      return { rowClass: 'row-alert-high', icon: '🚨' };
    case 'INFO':
      return { rowClass: 'row-alert-medium', icon: '📊' };
    case 'TICK':
    default:
      return { rowClass: 'row-alert-low', icon: '' };
  }
}

function setConnectionStatus(connected) {
  const statusEl = document.getElementById('ws-status');
  if (!statusEl) {
    return;
  }

  statusEl.classList.remove('connected', 'disconnected');
  statusEl.classList.add(connected ? 'connected' : 'disconnected');
  statusEl.innerHTML = connected
    ? '<i class="fas fa-circle"></i><span>Conectado</span>'
    : '<i class="fas fa-circle"></i><span>Desconectado</span>';
}

function isCanonicalPayload(payload) {
  return Boolean(
    payload
      && payload.ticker
      && payload.timeframe
      && payload.ohlcv
      && payload.ml
      && payload.decision
  );
}

function appendEventRow(payload) {
  const tbody = document.getElementById('events-tbody');
  if (!tbody) {
    return;
  }

  if (tbody.querySelector('td[colspan]')) {
    tbody.innerHTML = '';
  }

  const severity = String(payload.decision.severity || 'TICK').toUpperCase();
  const severityMeta = getSeverityMeta(severity);
  const row = document.createElement('tr');
  row.className = `event-row ${severityMeta.rowClass}`;

  const signal = String(payload.ml.signal || 'HOLD').toUpperCase();
  const statusIcon = payload.decision.signal_valid ? '✅' : '⚠️';
  const statusText = payload.decision.signal_valid ? 'VALID' : 'BLOCKED';
  const validationReason = String(payload.decision.validation_reason ?? '');
  const escapedValidationReason = escapeHtml(validationReason);

  row.innerHTML = `
    <td class="col-time">${formatTime(payload.timestamp)}</td>
    <td class="col-ticker">${escapeHtml(payload.ticker)}</td>
    <td class="col-type">${severityMeta.icon}</td>
    <td class="col-price">${formatPrice(payload.ohlcv.close)}</td>
    <td class="col-prob">${formatProbability(payload.ml.probability)}</td>
    <td class="col-signal">${escapeHtml(signal)}</td>
    <td class="col-status">${statusIcon} ${statusText}</td>
    <td class="col-reason"><span class="reason-text" title="${escapedValidationReason}">${escapedValidationReason}</span></td>
  `;

  tbody.insertBefore(row, tbody.firstChild);

  while (tbody.children.length > MAX_EVENT_ROWS) {
    tbody.removeChild(tbody.lastChild);
  }
}

function updateEventCounts(payload) {
  eventCounts.total += 1;

  if (String(payload.ml.signal || 'HOLD').toUpperCase() !== 'HOLD') {
    eventCounts.ml += 1;
  }

  if (payload.decision.signal_valid === false) {
    eventCounts.blocks += 1;
  }

  if (payload.indicators) {
    eventCounts.indicators += 1;
  }

  const countEventsEl = document.getElementById('count-events');
  const countMlEl = document.getElementById('count-ml');
  const countBlocksEl = document.getElementById('count-blocks');
  const countIndicatorsEl = document.getElementById('count-indicators');

  if (countEventsEl) {
    countEventsEl.textContent = String(eventCounts.total);
  }
  if (countMlEl) {
    countMlEl.textContent = String(eventCounts.ml);
  }
  if (countBlocksEl) {
    countBlocksEl.textContent = String(eventCounts.blocks);
  }
  if (countIndicatorsEl) {
    countIndicatorsEl.textContent = String(eventCounts.indicators);
  }
}

function updateStickyHeader(payload) {
  activeMonitors.add(`${payload.ticker}-${payload.timeframe}`);

  const lastTickEl = document.getElementById('last-tick-time');
  const countMonitorsEl = document.getElementById('count-monitors');
  const lastValidationReasonEl = document.getElementById('last-validation-reason');

  if (lastTickEl) {
    lastTickEl.textContent = formatTime(payload.timestamp);
  }

  if (countMonitorsEl) {
    countMonitorsEl.textContent = String(activeMonitors.size);
  }

  if (lastValidationReasonEl) {
    const validationReason = String(payload.decision.validation_reason ?? '');
    lastValidationReasonEl.textContent = validationReason || '--';
    lastValidationReasonEl.title = validationReason || '--';
  }
}

function handleMonitorMessage(message) {
  const payload = message?.payload || message;

  if (!isCanonicalPayload(payload)) {
    return;
  }

  appendEventRow(payload);
  updateEventCounts(payload);
  updateStickyHeader(payload);
}

function wsUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${protocol}://${window.location.host}/ws/monitor`;
}

function attemptReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT) {
    return;
  }

  reconnectAttempts += 1;
  const delayMs = Math.min(5000, reconnectAttempts * 1000);
  window.setTimeout(connectWebSocket, delayMs);
}

function connectWebSocket() {
  try {
    ws = new WebSocket(wsUrl());

    ws.onopen = () => {
      reconnectAttempts = 0;
      setConnectionStatus(true);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data?.type === 'pong') {
          return;
        }
        handleMonitorMessage(data);
      } catch (error) {
        console.error('Invalid WS payload:', error);
      }
    };

    ws.onclose = () => {
      setConnectionStatus(false);
      attemptReconnect();
    };

    ws.onerror = () => {
      setConnectionStatus(false);
    };
  } catch (error) {
    console.error('WebSocket connection failed:', error);
    setConnectionStatus(false);
    attemptReconnect();
  }
}

function heartbeat() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send('ping');
    } catch (_error) {
    }
  }

  window.setTimeout(heartbeat, HEARTBEAT_MS);
}

window.addEventListener('DOMContentLoaded', () => {
  setConnectionStatus(false);
  connectWebSocket();
  heartbeat();
});