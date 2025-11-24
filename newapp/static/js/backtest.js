// Backtest streaming client
(function() {
  const form = document.getElementById('btForm');
  const progressEl = document.getElementById('progressInfo');
  const logContainer = document.getElementById('activityLog');
  const statusEl = document.getElementById('bt-status');

  let ws = null;
  let chartCandles = null;
  let candleSeries = null;
  let candles = [];
  let processed = 0;

  function initChart() {
    if (chartCandles) return;
    chartCandles = LightweightCharts.createChart(document.getElementById('candlesChart'), {
      layout: { background: { color: '#182027' }, textColor: '#d0d2d6' },
      grid: { vertLines: { color: '#242f38' }, horzLines: { color: '#242f38' } },
      rightPriceScale: { borderColor: '#2c2e33' },
      timeScale: { borderColor: '#2c2e33' },
    });
    candleSeries = chartCandles.addCandlestickSeries({
      upColor: '#3bbf6b', downColor: '#ff4d4d', borderUpColor: '#3bbf6b', borderDownColor: '#ff4d4d', wickUpColor: '#3bbf6b', wickDownColor: '#ff4d4d'
    });
  }

  function setCandles(data) {
    candles = data.map(c => ({ time: c.time.substring(0,19).replace('T',' '), open: c.open, high: c.high, low: c.low, close: c.close }));
    candleSeries.setData(candles);
  }

  function addLogEntry(entry) {
    const div = document.createElement('div');
    div.className = 'log-entry ' + (entry.signal === 'BUY' ? 'info' : entry.signal === 'SELL' ? 'alert' : '');
    div.innerHTML = `<div class="log-timestamp">${entry.timestamp}</div>
      <div><strong>${entry.signal}</strong> @ ${entry.price.toFixed(2)} | EMA9: ${Number(entry.ema_9).toFixed(2)} | SMA20: ${Number(entry.sma_20).toFixed(2)}<br>${entry.message}</div>`;
    logContainer.prepend(div); // most recent on top
    // trim if too many
    if (logContainer.children.length > 300) {
      logContainer.removeChild(logContainer.lastChild);
    }
  }

  function updateStatus(connected) {
    if (connected) {
      statusEl.classList.remove('disconnected');
      statusEl.classList.add('connected');
      statusEl.querySelector('span').textContent = 'Conectado';
    } else {
      statusEl.classList.remove('connected');
      statusEl.classList.add('disconnected');
      statusEl.querySelector('span').textContent = 'Desconectado';
    }
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (ws) ws.close();
    initChart();
    logContainer.innerHTML = '';
    processed = 0;
    progressEl.textContent = 'Conectando...';

    const data = Object.fromEntries(new FormData(form).entries());
    ws = new WebSocket(`ws://${location.host}/ws/backtest`);

    ws.onopen = () => {
      updateStatus(true);
      ws.send(JSON.stringify({
        action: 'start',
        symbol: data.symbol,
        timeframe: data.timeframe,
        start: data.start || null,
        end: data.end || null,
        initial_capital: parseFloat(data.initial_capital),
        position_size: parseFloat(data.position_size),
        update_interval: parseInt(data.update_interval,10) || 5
      }));
      progressEl.textContent = 'Solicitando dados...';
    };

    ws.onmessage = (ev) => {
      let msg; try { msg = JSON.parse(ev.data); } catch { return; }
      if (msg.type === 'init') {
        setCandles(msg.candles);
        progressEl.textContent = `Iniciado. Total candles: ${msg.total}`;
      } else if (msg.type === 'progress') {
        processed = msg.index;
        progressEl.textContent = `Processado: ${processed}/${msg.total}`;
        addLogEntry(msg);
      } else if (msg.type === 'complete') {
        progressEl.textContent = `Concluído. BUY: ${msg.buy_signals} | SELL: ${msg.sell_signals}`;
        addLogEntry({
          timestamp: new Date().toISOString(),
          signal: 'FINISH',
          price: candles.length ? candles[candles.length-1].close : 0,
          ema_9: '-',
          sma_20: '-',
          message: `Backtest finalizado. Candles: ${msg.total_candles}, BUY: ${msg.buy_signals}, SELL: ${msg.sell_signals}`
        });
      } else if (msg.type === 'error') {
        progressEl.textContent = 'Erro: ' + msg.message;
        addLogEntry({
          timestamp: new Date().toISOString(),
            signal: 'ERROR',
            price: 0,
            ema_9: '-',
            sma_20: '-',
            message: msg.message
        });
      }
    };

    ws.onclose = () => {
      updateStatus(false);
      if (processed === 0) {
        progressEl.textContent = 'Conexão encerrada.';
      }
    };
  });
})();
