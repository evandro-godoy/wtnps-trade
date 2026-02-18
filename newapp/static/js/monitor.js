/* Real-time Monitor WebSocket Client */

let ws = null;
let reconnectAttempts = 0;
const MAX_RECONNECT = 10;

function connectWebSocket() {
  try {
    ws = new WebSocket(`ws://${window.location.host}/ws/monitor`);
    const statusEl = document.getElementById('ws-status');

    ws.onopen = () => {
      reconnectAttempts = 0;
      statusEl.classList.remove('disconnected');
      statusEl.classList.add('connected');
      statusEl.innerHTML = '<i class="fas fa-circle"></i><span>Conectado</span>';
      console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return; // heartbeat
        updateMonitorCard(data);
        appendLogEntry(data);
      } catch (err) {
        console.error('Invalid WS message:', err);
      }
    };

    ws.onclose = () => {
      statusEl.classList.remove('connected');
      statusEl.classList.add('disconnected');
      statusEl.innerHTML = '<i class="fas fa-circle"></i><span>Desconectado</span>';
      console.warn('WebSocket disconnected');
      attemptReconnect();
    };

    ws.onerror = (err) => {
      console.error('WebSocket error:', err);
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
  console.log(`Reconnecting WebSocket in ${delay}ms...`);
  setTimeout(connectWebSocket, delay);
}

function startMonitor(ticker, timeframe) {
  fetch('/api/monitor/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, timeframe })
  })
  .then(r => r.json())
  .then(json => {
    console.log('Start response:', json);
    if (json.status === 'started' || json.status === 'already_running') {
      const card = document.getElementById(`monitor-${ticker}-${timeframe}`);
      card.classList.remove('inactive');
      card.classList.add('active');
      // Enable stop button
      card.querySelector('.btn-danger').disabled = false;
    }
  })
  .catch(err => console.error('Start monitor failed:', err));
}

function stopMonitor(ticker, timeframe) {
  fetch('/api/monitor/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ticker, timeframe })
  })
  .then(r => r.json())
  .then(json => {
    console.log('Stop response:', json);
    if (json.status === 'stopped') {
      const card = document.getElementById(`monitor-${ticker}-${timeframe}`);
      card.classList.remove('active');
      card.classList.add('inactive');
      // Disable stop button
      card.querySelector('.btn-danger').disabled = true;
    }
  })
  .catch(err => console.error('Stop monitor failed:', err));
}

function updateMonitorCard(data) {
  const { ticker, timeframe, ohlcv, indicators, analysis } = data;
  const card = document.getElementById(`monitor-${ticker}-${timeframe}`);
  if (!card) return;

  // Update price
  const priceEl = document.getElementById(`price-${ticker}-${timeframe}`);
  if (priceEl) priceEl.textContent = ohlcv.close.toFixed(2);

  // Compute change (requires previous value - for simplicity, using open vs close)
  const change = ohlcv.close - ohlcv.open;
  const changePct = (change / ohlcv.open) * 100;
  const changeEl = document.getElementById(`change-${ticker}-${timeframe}`);
  if (changeEl) {
    changeEl.classList.remove('positive', 'negative');
    changeEl.classList.add(change >= 0 ? 'positive' : 'negative');
    changeEl.innerHTML = `
      <i class="fas ${change >= 0 ? 'fa-arrow-up' : 'fa-arrow-down'}"></i>
      ${Math.abs(change).toFixed(2)} (${changePct.toFixed(2)}%)
    `;
  }

  // Update indicators
  const emaEl = document.getElementById(`ema9-${ticker}-${timeframe}`);
  const sma20El = document.getElementById(`sma20-${ticker}-${timeframe}`);
  const rsiEl = document.getElementById(`rsi-${ticker}-${timeframe}`);
  const trendEl = document.getElementById(`trend-${ticker}-${timeframe}`);

  if (emaEl) emaEl.textContent = indicators.ema_9 ? indicators.ema_9.toFixed(2) : '--';
  if (sma20El) sma20El.textContent = indicators.sma_20 ? indicators.sma_20.toFixed(2) : '--';
  if (rsiEl) rsiEl.textContent = indicators.rsi_14 ? indicators.rsi_14.toFixed(2) : '--';
  if (trendEl) trendEl.textContent = analysis.trend || '--';
}

function appendLogEntry(data) {
  const logEl = document.getElementById('activity-log');
  if (!logEl) return;

  const { timestamp, ticker, timeframe, ohlcv, indicators } = data;
  // Format timestamp to UTC without timezone info
  const dt = new Date(timestamp);
  const timeStr = `${dt.getUTCDate().toString().padStart(2, '0')}/${(dt.getUTCMonth() + 1).toString().padStart(2, '0')}/${dt.getUTCFullYear()} ${dt.getUTCHours().toString().padStart(2, '0')}:${dt.getUTCMinutes().toString().padStart(2, '0')}`;
  const change = ohlcv.close - ohlcv.open;
  const changePct = (change / ohlcv.open) * 100;

  const entry = document.createElement('div');
  entry.classList.add('log-entry');

  // Determine entry type based on RSI or volatility (placeholder logic)
  if (indicators.rsi_14 !== undefined) {
    if (indicators.rsi_14 > 70) entry.classList.add('alert');
    else if (indicators.rsi_14 > 55) entry.classList.add('info');
  }

  entry.innerHTML = `
    <div class="log-timestamp">${timeStr} | ${ticker} ${timeframe}</div>
    <div>
      Close: ${ohlcv.close.toFixed(2)} | Var: ${change.toFixed(2)} (${changePct.toFixed(2)}%)
      | EMA9: ${indicators.ema_9 ? indicators.ema_9.toFixed(2) : '--'}
      | RSI14: ${indicators.rsi_14 ? indicators.rsi_14.toFixed(2) : '--'}
    </div>
  `;

  // Prepend entry
  logEl.insertBefore(entry, logEl.firstChild);

  // Limit log size
  const entries = logEl.querySelectorAll('.log-entry');
  if (entries.length > 200) {
    logEl.removeChild(logEl.lastChild);
  }
}

// Heartbeat ping
function heartbeat() {
  if (ws && ws.readyState === WebSocket.OPEN) {
    try { ws.send('ping'); } catch (e) {}
  }
  setTimeout(heartbeat, 15000);
}

// Initialize when DOM ready
window.addEventListener('DOMContentLoaded', () => {
  connectWebSocket();
  heartbeat();
});
