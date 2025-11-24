// Backtest streaming client
(function() {
  const form = document.getElementById('btForm');
  const progressEl = document.getElementById('progressInfo');
  const tradesTbody = document.querySelector('#tradesTable tbody');
  const summaryEl = document.getElementById('summary');
  const startBtn = document.getElementById('startBtn');

  let ws = null;
  let candleSeries = null;
  let equitySeries = null;
  let chartCandles = null;
  let chartEquity = null;
  let candles = [];
  let processed = 0;

  function initCharts() {
    if (chartCandles) return; // only once
    chartCandles = LightweightCharts.createChart(document.getElementById('candlesChart'), {
      layout: { background: { color: '#1e1f24' }, textColor: '#d0d2d6' },
      grid: { vertLines: { color: '#2c2e33' }, horzLines: { color: '#2c2e33' } },
      rightPriceScale: { borderColor: '#555' },
      timeScale: { borderColor: '#555' },
    });
    candleSeries = chartCandles.addCandlestickSeries({ upColor: '#18c27a', downColor: '#ff4d4f', borderUpColor: '#18c27a', borderDownColor: '#ff4d4f', wickUpColor: '#18c27a', wickDownColor: '#ff4d4f' });

    chartEquity = LightweightCharts.createChart(document.getElementById('equityChart'), {
      layout: { background: { color: '#1e1f24' }, textColor: '#d0d2d6' },
      grid: { vertLines: { color: '#2c2e33' }, horzLines: { color: '#2c2e33' } },
      rightPriceScale: { borderColor: '#555' },
      timeScale: { borderColor: '#555' },
    });
    equitySeries = chartEquity.addLineSeries({ color: '#4da6ff', lineWidth: 2 });
  }

  function setCandles(data) {
    candles = data.map(c => ({ time: c.time.substring(0,19).replace('T',' '), open: c.open, high: c.high, low: c.low, close: c.close }));
    candleSeries.setData(candles);
  }

  function appendTrade(trade) {
    const idx = tradesTbody.children.length + 1;
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${idx}</td><td>${trade.entry_time}</td><td class="${trade.direction==='BUY'?'badge-buy':'badge-sell'}">${trade.direction}</td><td>${trade.entry_price.toFixed(2)}</td><td>${trade.exit_time || '-'}</td><td>${trade.exit_price!==undefined && trade.exit_price!==null?trade.exit_price.toFixed(2):'-'}</td><td>${trade.pnl!==undefined && trade.pnl!==null?trade.pnl.toFixed(2):'-'}</td><td>${trade.return_pct!==undefined && trade.return_pct!==null?(trade.return_pct*100).toFixed(2)+'%':'-'}</td>`;
    tradesTbody.appendChild(tr);
  }

  function updateSummary(summary) {
    summaryEl.innerHTML = '';
    const items = [
      ['Run ID', summary.run_id],
      ['Trades', summary.total_trades],
      ['Win Rate', (summary.win_rate*100).toFixed(2)+'%'],
      ['Profit Factor', (summary.profit_factor===Infinity?'∞':summary.profit_factor.toFixed(2))],
      ['Net Profit', summary.net_profit.toFixed(2)],
      ['Final Capital', summary.final_capital.toFixed(2)],
      ['Drawdown', (summary.max_drawdown*100).toFixed(2)+'%'],
      ['Avg Trade %', (summary.avg_trade_return*100).toFixed(2)+'%'],
    ];
    items.forEach(([k,v]) => {
      const div = document.createElement('div');
      div.className = 'stat';
      div.innerHTML = `<strong>${k}</strong><br>${v}`;
      summaryEl.appendChild(div);
    });
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (ws) { ws.close(); }
    initCharts();
    tradesTbody.innerHTML='';
    summaryEl.innerHTML='';
    processed = 0;
    progressEl.textContent = 'Conectando...';

    const data = Object.fromEntries(new FormData(form).entries());
    const url = `ws://${location.host}/ws/backtest`;
    ws = new WebSocket(url);

    ws.onopen = () => {
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
        equitySeries.setData([]);
        progressEl.textContent = `Iniciado. Total candles: ${msg.total}`;
      } else if (msg.type === 'progress') {
        processed = msg.index;
        progressEl.textContent = `Processado: ${processed}/${msg.total} | Equity: ${msg.equity.toFixed(2)} | DD: ${(msg.drawdown*100).toFixed(2)}%`;
        equitySeries.update({ time: msg.timestamp.substring(0,19).replace('T',' '), value: msg.equity });
        if (msg.trade_opened) {
          appendTrade({
            entry_time: msg.trade_opened.entry_time,
            direction: msg.trade_opened.direction,
            entry_price: msg.trade_opened.entry_price,
          });
        }
        if (msg.trade_closed) {
          appendTrade({
            entry_time: msg.trade_closed.entry_time,
            exit_time: msg.trade_closed.exit_time,
            direction: msg.trade_closed.direction,
            entry_price: msg.trade_closed.entry_price,
            exit_price: msg.trade_closed.exit_price,
            pnl: msg.trade_closed.pnl,
            return_pct: msg.trade_closed.return_pct,
          });
        }
      } else if (msg.type === 'complete') {
        progressEl.textContent = 'Concluído.';
        updateSummary(msg);
      } else if (msg.type === 'error') {
        progressEl.textContent = 'Erro: ' + msg.message;
      }
    };

    ws.onclose = () => {
      if (processed === 0) {
        progressEl.textContent = 'Conexão encerrada.';
      }
    };
  });
})();
