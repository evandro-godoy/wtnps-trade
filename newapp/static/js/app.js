(function(){
  const cfg = window.DEMO_CONFIG;
  const latestBox = document.getElementById('latest');
  const chartDiv = document.getElementById('chart');

  async function fetchOHLC(){
    const url = `/api/ohlc?symbol=${encodeURIComponent(cfg.symbol)}&timeframe=${encodeURIComponent(cfg.timeframe)}&limit=${cfg.limit}`;
    const res = await fetch(url);
    if(!res.ok){throw new Error('Falha ao obter dados OHLC');}
    return res.json();
  }

  function renderLatest(latest){
    if(!latest){latestBox.textContent='Sem dados.';return;}
    const dir = latest.close >= latest.open ? 'alta' : 'baixa';
    const cls = latest.close >= latest.open ? 'green' : 'red';
    latestBox.innerHTML = `
      <strong>Último Candle:</strong> <span>${latest.time}</span><br>
      <span>Abertura:</span> <span>${latest.open.toFixed(2)}</span> | 
      <span>Máxima:</span> <span>${latest.high.toFixed(2)}</span> | 
      <span>Mínima:</span> <span>${latest.low.toFixed(2)}</span> | 
      <span>Fechamento:</span> <span class="${cls}">${latest.close.toFixed(2)}</span> | 
      <span>Volume:</span> <span>${latest.volume}</span> | 
      <span>Direção:</span> <span class="${cls}">${dir}</span>
    `;
  }

  function renderChart(data){
    if(!data || !data.length){chartDiv.textContent='Sem dados para exibir.';return;}
    const times = data.map(d=>d.time);
    const opens = data.map(d=>d.open);
    const highs = data.map(d=>d.high);
    const lows = data.map(d=>d.low);
    const closes = data.map(d=>d.close);

    const trace = {
      x: times,
      open: opens,
      high: highs,
      low: lows,
      close: closes,
      increasing: {line: {color: '#25c97d'}, fillcolor: '#25c97d'},
      decreasing: {line: {color: '#ff4d4d'}, fillcolor: '#ff4d4d'},
      type: 'candlestick',
      name: cfg.symbol
    };

    const layout = {
      dragmode: 'zoom',
      showlegend: false,
      paper_bgcolor: '#101418',
      plot_bgcolor: '#101418',
      xaxis: {gridcolor: '#2d3a44'},
      yaxis: {gridcolor: '#2d3a44'},
      margin: {l:40,r:20,t:10,b:40},
    };

    Plotly.newPlot(chartDiv, [trace], layout, {responsive:true, displaylogo:false});
  }

  async function init(){
    try{
      const payload = await fetchOHLC();
      renderLatest(payload.latest);
      renderChart(payload.data);
    }catch(err){
      latestBox.textContent = 'Erro ao carregar dados.';
      console.error(err);
    }
  }

  init();
})();
