/**
 * WTNPS Trade Dashboard - App Logic
 * 
 * Fetches latest candle and technical analysis data.
 * Chart rendering is handled by Bokeh (server-side generated).
 */

document.addEventListener('DOMContentLoaded', () => {
  console.log('App initialized');
  fetchLatestData();
  fetchAnalysis();
});

/**
 * Fetch latest candle data from API
 */
async function fetchLatestData() {
  try {
    const response = await fetch('/api/ohlc?limit=1');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const json = await response.json();
    if (!json.latest) {
      document.getElementById('latest').innerHTML = '<p>Nenhum dado disponível</p>';
      return;
    }
    
    const latest = json.latest;
    const dt = new Date(latest.time);
    const time = `${dt.getUTCDate().toString().padStart(2, '0')}/${(dt.getUTCMonth() + 1).toString().padStart(2, '0')}/${dt.getUTCFullYear()} ${dt.getUTCHours().toString().padStart(2, '0')}:${dt.getUTCMinutes().toString().padStart(2, '0')}`;
    const change = latest.close - latest.open;
    const changeClass = change >= 0 ? 'positive' : 'negative';
    const changeSymbol = change >= 0 ? '▲' : '▼';
    
    document.getElementById('latest').innerHTML = `
      <div class="latest-candle">
        <div class="candle-time">${time}</div>
        <div class="candle-prices">
          <div class="price-item">
            <span class="label">Open:</span>
            <span class="value">${latest.open.toFixed(2)}</span>
          </div>
          <div class="price-item">
            <span class="label">High:</span>
            <span class="value">${latest.high.toFixed(2)}</span>
          </div>
          <div class="price-item">
            <span class="label">Low:</span>
            <span class="value">${latest.low.toFixed(2)}</span>
          </div>
          <div class="price-item">
            <span class="label">Close:</span>
            <span class="value ${changeClass}">${latest.close.toFixed(2)} ${changeSymbol}</span>
          </div>
          <div class="price-item">
            <span class="label">Volume:</span>
            <span class="value">${latest.volume.toLocaleString('pt-BR')}</span>
          </div>
        </div>
      </div>
    `;
  } catch (error) {
    console.error('Error fetching latest data:', error);
    document.getElementById('latest').innerHTML = 
      `<p class="error">Erro ao carregar dados: ${error.message}</p>`;
  }
}

/**
 * Fetch technical analysis from API
 */
async function fetchAnalysis() {
  try {
    const response = await fetch('/api/analysis?limit=200');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    
    const json = await response.json();
    const analysis = json.analysis;
    
    if (!analysis) {
      document.getElementById('analysis').innerHTML = '<p>Análise indisponível</p>';
      return;
    }
    
    const trend = analysis.trend || analysis.trend?.direction || 'N/A';
    const trendStrength = analysis.trend_strength || analysis.trend?.strength || 'N/A';
    const rsi = Number(analysis.rsi ?? analysis.rsi_14 ?? 0);
    const ema9 = Number(analysis.ema_9 ?? analysis.ema_fast ?? 0);
    const sma20 = Number(analysis.sma_20 ?? analysis.sma_fast ?? 0);
    const sma50 = Number(analysis.sma_50 ?? analysis.sma_slow ?? 0);
    const pattern = analysis.pattern || 'Nenhum padrão detectado';
    const support = Number(analysis.support ?? 0);
    const resistance = Number(analysis.resistance ?? 0);
    
    document.getElementById('analysis').innerHTML = `
      <div class="analysis-card">
        <h3>Tendência</h3>
        <p class="trend-value">${trend}</p>
        <p class="trend-strength">Força: ${trendStrength}</p>
      </div>
      
      <div class="analysis-card">
        <h3>RSI (14)</h3>
        <p class="rsi-value">${rsi > 0 ? rsi.toFixed(2) : 'N/A'}</p>
      </div>
      
      <div class="analysis-card">
        <h3>Médias Móveis</h3>
        <p><strong>EMA(9):</strong> ${ema9 > 0 ? ema9.toFixed(2) : 'N/A'}</p>
        <p><strong>SMA(20):</strong> ${sma20 > 0 ? sma20.toFixed(2) : 'N/A'}</p>
        <p><strong>SMA(50):</strong> ${sma50 > 0 ? sma50.toFixed(2) : 'N/A'}</p>
      </div>
      
      <div class="analysis-card">
        <h3>Padrões de Price Action</h3>
        <div class="patterns-container"><span class="pattern-badge">${pattern}</span></div>
      </div>
      
      <div class="analysis-card">
        <h3>Suportes</h3>
        <ul class="levels-list"><li>${support > 0 ? support.toFixed(2) : 'Não detectado'}</li></ul>
      </div>
      
      <div class="analysis-card">
        <h3>Resistências</h3>
        <ul class="levels-list"><li>${resistance > 0 ? resistance.toFixed(2) : 'Não detectado'}</li></ul>
      </div>
    `;
  } catch (error) {
    console.error('Error fetching analysis:', error);
    document.getElementById('analysis').innerHTML = 
      `<p class="error">Erro ao carregar análise: ${error.message}</p>`;
  }
}
