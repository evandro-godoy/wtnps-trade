/* Real-time Analytical Monitor WebSocket Client */

let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT = 10;
const MAX_EVENT_ROWS = 120;
let eventCounts = { total: 0, ml: 0, blocks: 0, indicators: 0 };
let activeMonitors = new Set();

function monitorKey(ticker, timeframe) {
  return `${ticker}-${timeframe}`;
}

function monitorCardId(ticker, timeframe) {
  return `monitor-${monitorKey(ticker, timeframe)}`;
}

function toNumberOrNull(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function toDisplayNumber(value, decimals = 2) {
  if (value === null || value === undefined) return 'N/A';
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return 'N/A';
  return parsed.toFixed(decimals);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function classifySeverity(probability) {
  const prob = toNumberOrNull(probability);
  if (prob === null) {
    return {
      label: 'TICK',
      cssClass: 'alert-low',
      icon: ''
    };
  }
  if (prob > 0.65) {
    return {
      label: 'ALERT',
      cssClass: 'alert-high',
      icon: '🚨'
    };
  }
  if (prob > 0.55) {
    return {
      label: 'INFO',
      cssClass: 'alert-medium',
      icon: '📊'
    };
  }
  return {
    label: 'TICK',
    cssClass: 'alert-low',
    icon: ''
  };
}

function normalizeMonitorPayload(message) {
  const payload = message?.payload || message?.data || message;
  if (!payload || !payload.ticker || !payload.timeframe) {
    return null;
  }

  const ohlcv = payload.ohlcv || {};
  const indicators = payload.indicators || {};
  const analysis = payload.analysis || {};
  const ml = payload.ml || {};
  const decision = payload.decision || {};

  const probability = toNumberOrNull(ml.probability);
  const derivedSeverity = classifySeverity(probability);
  const decisionSeverity = String(decision.severity || '').toUpperCase();
  const severity = ['ALERT', 'INFO', 'TICK'].includes(decisionSeverity)
    ? {
      label: decisionSeverity,
      cssClass: decisionSeverity === 'ALERT'
        ? 'alert-high'
        : decisionSeverity === 'INFO'
          ? 'alert-medium'
          : 'alert-low',
      icon: decisionSeverity === 'ALERT' ? '🚨' : decisionSeverity === 'INFO' ? '📊' : ''
    }
    : derivedSeverity;

  const signalValid = decision.signal_valid === true;

  return {
    timestamp: payload.timestamp || new Date().toISOString(),
    ticker: String(payload.ticker),
    timeframe: String(payload.timeframe),
    ohlcv: {
      open: toNumberOrNull(ohlcv.open),
      high: toNumberOrNull(ohlcv.high),
      low: toNumberOrNull(ohlcv.low),
      close: toNumberOrNull(ohlcv.close),
      volume: toNumberOrNull(ohlcv.volume)
    },
    indicators: {
      ema_9: toNumberOrNull(indicators.ema_9),
      ema_20: toNumberOrNull(indicators.ema_20),
      sma_20: toNumberOrNull(indicators.sma_20),
      sma_50: toNumberOrNull(indicators.sma_50),
      rsi_14: toNumberOrNull(indicators.rsi_14)
    },
    analysis: {
      trend: analysis.trend || 'N/A',
      trend_strength: analysis.trend_strength || 'N/A',
      pattern: analysis.pattern || 'N/A',
      rsi_condition: analysis.rsi_condition || 'N/A'
    },
    ml: {
      signal: ml.signal || 'N/A',
      direction: ml.direction || 'N/A',
      probability
    },
    decision: {
      signal_valid: signalValid,
      status: decision.status || (signalValid ? 'VALIDADO' : 'NÃO VALIDADO'),
      validation_reason: decision.validation_reason || '',
      severity
    }
  };
}

function formatTimestamp(value) {
  if (!value) return 'N/A';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'N/A';
  return `${date.getUTCDate().toString().padStart(2, '0')}/${(date.getUTCMonth() + 1).toString().padStart(2, '0')}/${date.getUTCFullYear()} ${date.getUTCHours().toString().padStart(2, '0')}:${date.getUTCMinutes().toString().padStart(2, '0')}:${date.getUTCSeconds().toString().padStart(2, '0')} UTC`;
}

function appendEventRow(data) {
  const tbody = document.getElementById('events-tbody');
  if (!tbody) return;

  if (tbody.querySelector('td[colspan="7"]')) {
    tbody.innerHTML = '';
  }

  const { ticker, timeframe, timestamp, ohlcv, ml, decision } = data;
  const row = document.createElement('tr');
  const severityClass = getSeverityClass(ml.probability);
  row.className = `event-row ${severityClass}`;

  const statusText = decision.signal_valid ? 'VALID' : 'BLOCK';
  const statusIcon = getStatusIcon(decision.signal_valid);

  row.innerHTML = `
    <td class="col-time">${formatTime(timestamp)}</td>
    <td class="col-ticker">${escapeHtml(ticker)}</td>
    <td class="col-type">${getSeverityIcon(ml.probability)}</td>
    <td class="col-price">${formatPrice(ohlcv.close)}</td>
    <td class="col-prob">${formatProbability(ml.probability)}</td>
    <td class="col-signal">${escapeHtml(ml.signal || 'N/A').toUpperCase()}</td>
    <td class="col-status">${statusIcon} ${statusText}</td>
  `;

  tbody.insertBefore(row, tbody.firstChild);
  pruneOldEvents();
  updateEventCounts(data);
  updateStickyHeader(timestamp);
}

function pruneOldEvents() {
  const tbody = document.getElementById('events-tbody');
  if (!tbody) return;
  while (tbody.children.length > MAX_EVENT_ROWS) {
    tbody.removeChild(tbody.lastChild);
  }
}

function updateEventCounts(data) {
  eventCounts.total += 1;
  if (data.ml && data.ml.signal && data.ml.signal !== 'HOLD') {
    eventCounts.ml += 1;
  }
  if (data.decision && !data.decision.signal_valid) {
    eventCounts.blocks += 1;
  }
  if (data.indicators) {
    eventCounts.indicators += 1;
  }

  const countEventsEl = document.getElementById('count-events');
  const countMlEl = document.getElementById('count-ml');
  const countBlocksEl = document.getElementById('count-blocks');
  const countIndicatorsEl = document.getElementById('count-indicators');

  if (countEventsEl) countEventsEl.textContent = eventCounts.total;
  if (countMlEl) countMlEl.textContent = eventCounts.ml;
  if (countBlocksEl) countBlocksEl.textContent = eventCounts.blocks;
  if (countIndicatorsEl) countIndicatorsEl.textContent = eventCounts.indicators;
}

function updateStickyHeader(timestamp) {
  const lastTickEl = document.getElementById('last-tick-time');
  if (lastTickEl) {
    lastTickEl.textContent = formatTime(timestamp);
  }
  const countMonitorsEl = document.getElementById('count-monitors');
  if (countMonitorsEl) {
    countMonitorsEl.textContent = activeMonitors.size;
  }
    timeEl.textContent = formatTimestamp(timestamp);
  }

  if (mlEl) {
    const probabilityText = ml.probability === null ? 'N/A' : `${(ml.probability * 100).toFixed(2)}%`;
    const icon = decision.severity.icon ? `${decision.severity.icon} ` : '';
    mlEl.textContent = `${icon}Sinal: ${ml.signal} | Direção: ${ml.direction} | Prob: ${probabilityText} | Severidade: ${decision.severity.label}`;
  }

  if (decisionEl) {
    const stateLabel = decision.signal_valid ? '✅ VALIDADO' : '⚠️ NÃO VALIDADO';
    const reason = !decision.signal_valid && decision.validation_reason
      ? ` | Motivo: ${decision.validation_reason}`
      : '';
    decisionEl.textContent = `${stateLabel}${reason}`;
  }

  if (analysisEl) {
    analysisEl.textContent = [
      `Trend: ${analysis.trend || 'N/A'}`,
      `Strength: ${analysis.trend_strength || 'N/A'}`,
      `Pattern: ${analysis.pattern || 'N/A'}`,
      `RSI Condition: ${analysis.rsi_condition || 'N/A'}`
    ].join(' | ');
  }

  if (indicatorsEl) {
    indicatorsEl.textContent = [
      `EMA9: ${toDisplayNumber(indicators.ema_9)}`,
      `EMA20: ${toDisplayNumber(indicators.ema_20)}`,
      `SMA20: ${toDisplayNumber(indicators.sma_20)}`,
      `SMA50: ${toDisplayNumber(indicators.sma_50)}`,
      `RSI14: ${toDisplayNumber(indicators.rsi_14)}`
    ].join(' | ');
  }

  setAlertClass(card, decision.severity.cssClass);
  setDecisionClass(decisionBlock, decision.signal_valid);
  activateCard(card);
}



function setConnectionStatus(connected) {
  const statusEl = document.getElementById('ws-status');
  if (!statusEl) return;
  statusEl.classList.remove('connected', 'disconnected');
  statusEl.classList.add(connected ? 'connected' : 'disconnected');
  statusEl.innerHTML = connected
    ? '<i class="fas fa-circle"></i><span>Conectado</span>'
    : '<i class="fas fa-circle"></i><span>Desconectado</span>';
}

function connectWebSocket() {
  try {
    ws = new WebSocket(`ws://${window.location.host}/ws/monitor`);

    ws.onopen = () => {
      reconnectAttempts = 0;
      setConnectionStatus(true);
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        const payload = normalizeMonitorPayload(data);
        if (!payload) return;
        updateMonitorCard(payload);
        appendLogEntry(payload);
      } catch (error) {
        console.error('Invalid WS message:', error);
      }
    };

    ws.onclose = () => {
      setConnectionStatus(false);
      console.warn('WebSocket disconnected');
      attemptReconnect();
    };

    ws.onerror = (error) => {
      console.error('WebSocket error:', error);
    };
  } catch (error) {
    console.error('WS connection failed:', error);
    attemptReconnect();
  }
}

function attemptReconnect() {
  if (reconnectAttempts >= MAX_RECONNECT) return;
  reconnectAttempts += 1;
  const delay = Math.min(5000, reconnectAttempts * 1000);
  setTimeout(connectWebSocket, delay);
}

function startMonitor(ticker, timeframe) {
  fetch('/api/monitor/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, timeframe })
  })
    .then((response) => response.json())
    .then((json) => {
      if (json.status === 'started' || json.status === 'already_running') {
        const card = createMonitorCard(ticker, timeframe);
        activateCard(card);
      }appendEventRow
    .catch((error) => console.error('Start monitor failed:', error));
}

function stopMonitor(ticker, timeframe) {
  fetch('/api/monitor/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, timeframe })
  })
    .then((response) => response.json())
    .then((json) => {
      if (json.status === 'stopped') {
        const card = document.getElementById(monitorCardId(ticker, timeframe));
        deactivateCard(card);
      }
    })
    .catch((error) => console.error('Stop monitor failed:', error));
}

function setupControls() {
  const monitorsGrid = document.getElementById('monitors-grid');
  if (!monitorsGrid) return;

  monitorsGrid.addEventListener('click', (event) => {
    const target = event.target.closest('button[data-action]');
    if (!target) return;

    const action = target.dataset.action;
    const ticker = target.dataset.ticker;
    const timeframe = target.dataset.timeframe;
    if (!ticker || !timeframe) return;

    if (action === 'start') {
      startMonitor(ticker, timeframe);
    }
    if (action === 'stop') {
      stopMonitor(ticker, timeframe);
    }activeMonitors.add(`${ticker}-${timeframe}`);
        updateStickyHeader(new Date().toISOString()
}

function heartbeat() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    try {
      ws.send('ping');
    } catch (_) {
      // no-op
    }
  }
  setTimeout(heartbeat, 15000);
}

window.addEventListener('DOMContentLoaded', () => {
  setupCactiveMonitors.delete(`${ticker}-${timeframe}`);
        updateStickyHeader(new Date().toISOString()
  heartbeat();
});
document.body