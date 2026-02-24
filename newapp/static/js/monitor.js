/* Real-time Analytical Monitor WebSocket Client */

let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT = 10;
const MAX_LOG_ITEMS = 120;

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

function createMonitorCard(ticker, timeframe) {
  const grid = document.getElementById('monitors-grid');
  if (!grid) return null;

  const id = monitorCardId(ticker, timeframe);
  let card = document.getElementById(id);
  if (card) return card;

  card = document.createElement('article');
  card.id = id;
  card.dataset.ticker = ticker;
  card.dataset.timeframe = timeframe;
  card.className = 'monitor-card inactive alert-low';
  card.innerHTML = `
    <div class="monitor-header">
      <div class="monitor-title">
        <span class="status-dot"></span>
        <span class="asset-label">${escapeHtml(ticker)} - ${escapeHtml(timeframe)}</span>
      </div>
      <div class="monitor-controls">
        <button class="btn btn-sm btn-success" data-action="start" data-ticker="${escapeHtml(ticker)}" data-timeframe="${escapeHtml(timeframe)}" aria-label="Iniciar ${escapeHtml(ticker)} ${escapeHtml(timeframe)}">
          <i class="fas fa-play"></i>
        </button>
        <button class="btn btn-sm btn-danger" data-action="stop" data-ticker="${escapeHtml(ticker)}" data-timeframe="${escapeHtml(timeframe)}" disabled aria-label="Parar ${escapeHtml(ticker)} ${escapeHtml(timeframe)}">
          <i class="fas fa-stop"></i>
        </button>
      </div>
    </div>
    <div class="monitor-summary">
      <div class="summary-price" id="close-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</div>
      <div class="summary-change alert-low" id="change-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</div>
      <div class="summary-time" id="time-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</div>
    </div>
    <div class="analytic-grid">
      <section class="analytic-block" id="ml-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">
        <h3>ML</h3>
        <p id="ml-value-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</p>
      </section>
      <section class="analytic-block" id="decision-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">
        <h3>Decision</h3>
        <p id="decision-value-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</p>
      </section>
      <section class="analytic-block" id="analysis-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">
        <h3>Analysis</h3>
        <p id="analysis-value-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</p>
      </section>
      <section class="analytic-block" id="indicators-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">
        <h3>Indicators</h3>
        <p id="indicators-value-${escapeHtml(ticker)}-${escapeHtml(timeframe)}">N/A</p>
      </section>
    </div>
  `;

  grid.appendChild(card);
  return card;
}

function setAlertClass(element, cssClass) {
  if (!element) return;
  element.classList.remove('alert-high', 'alert-medium', 'alert-low');
  element.classList.add(cssClass);
}

function setDecisionClass(element, isValid) {
  if (!element) return;
  element.classList.remove('decision-valid', 'decision-blocked');
  element.classList.add(isValid ? 'decision-valid' : 'decision-blocked');
}

function activateCard(card) {
  if (!card) return;
  card.classList.remove('inactive');
  card.classList.add('active');
  const dot = card.querySelector('.status-dot');
  if (dot) dot.classList.add('active');
  const stopBtn = card.querySelector('[data-action="stop"]');
  if (stopBtn) stopBtn.disabled = false;
}

function deactivateCard(card) {
  if (!card) return;
  card.classList.remove('active');
  card.classList.add('inactive');
  const dot = card.querySelector('.status-dot');
  if (dot) dot.classList.remove('active');
  const stopBtn = card.querySelector('[data-action="stop"]');
  if (stopBtn) stopBtn.disabled = true;
}

function updateMonitorCard(data) {
  const { ticker, timeframe, ohlcv, indicators, analysis, ml, decision, timestamp } = data;
  const card = createMonitorCard(ticker, timeframe);
  if (!card) return;

  const closeEl = document.getElementById(`close-${ticker}-${timeframe}`);
  const changeEl = document.getElementById(`change-${ticker}-${timeframe}`);
  const timeEl = document.getElementById(`time-${ticker}-${timeframe}`);
  const mlEl = document.getElementById(`ml-value-${ticker}-${timeframe}`);
  const decisionEl = document.getElementById(`decision-value-${ticker}-${timeframe}`);
  const analysisEl = document.getElementById(`analysis-value-${ticker}-${timeframe}`);
  const indicatorsEl = document.getElementById(`indicators-value-${ticker}-${timeframe}`);
  const decisionBlock = document.getElementById(`decision-${ticker}-${timeframe}`);

  if (closeEl) {
    closeEl.textContent = toDisplayNumber(ohlcv.close);
  }

  const openValue = ohlcv.open;
  const closeValue = ohlcv.close;
  if (changeEl) {
    if (openValue === null || closeValue === null || openValue === 0) {
      changeEl.textContent = 'N/A';
    } else {
      const change = closeValue - openValue;
      const changePct = (change / openValue) * 100;
      changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(2)} (${changePct.toFixed(2)}%)`;
    }
    setAlertClass(changeEl, decision.severity.cssClass);
  }

  if (timeEl) {
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

function appendLogEntry(data) {
  const logEl = document.getElementById('activity-log');
  if (!logEl) return;

  const { timestamp, ticker, timeframe, ohlcv, ml, decision } = data;
  const entry = document.createElement('div');
  entry.className = `log-entry ${decision.severity.cssClass}`;

  const change = ohlcv.close !== null && ohlcv.open !== null
    ? ohlcv.close - ohlcv.open
    : null;
  const changePct = ohlcv.close !== null && ohlcv.open !== null && ohlcv.open !== 0
    ? (change / ohlcv.open) * 100
    : null;

  const probabilityText = ml.probability === null ? 'N/A' : `${(ml.probability * 100).toFixed(2)}%`;
  const decisionState = decision.signal_valid ? '✅ VALIDADO' : '⚠️ NÃO VALIDADO';
  const reasonSuffix = !decision.signal_valid && decision.validation_reason
    ? ` | ${decision.validation_reason}`
    : '';
  const icon = decision.severity.icon ? `${decision.severity.icon} ` : '';

  entry.innerHTML = `
    <div class="log-timestamp">${formatTimestamp(timestamp)} | ${escapeHtml(ticker)} ${escapeHtml(timeframe)}</div>
    <div>
      ${icon}Close: ${toDisplayNumber(ohlcv.close)} | Var: ${change === null ? 'N/A' : change.toFixed(2)} (${changePct === null ? 'N/A' : `${changePct.toFixed(2)}%`})
      | ML: ${escapeHtml(ml.signal)} ${escapeHtml(ml.direction)} (${probabilityText})
      | Decisão: ${decisionState}${reasonSuffix}
    </div>
  `;

  logEl.insertBefore(entry, logEl.firstChild);

  while (logEl.querySelectorAll('.log-entry').length > MAX_LOG_ITEMS) {
    if (logEl.lastChild) {
      logEl.removeChild(logEl.lastChild);
    } else {
      break;
    }
  }
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
      }
    })
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
    }
  });
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
  setupControls();
  connectWebSocket();
  heartbeat();
});
