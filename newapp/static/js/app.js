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
    const time = new Date(latest.time).toLocaleString('pt-BR');
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
    
    // Format price action patterns
    const patterns = analysis.price_action?.patterns || [];
    const patternHtml = patterns.length > 0
      ? patterns.map(p => `<span class="pattern-badge">${p}</span>`).join(' ')
      : '<span class="pattern-badge neutral">Nenhum padrão detectado</span>';
    
    // Format support/resistance levels
    const supports = analysis.levels?.supports || [];
    const resistances = analysis.levels?.resistances || [];
    
    const supportHtml = supports.length > 0
      ? supports.map(s => `<li>${s.toFixed(2)}</li>`).join('')
      : '<li>Não detectado</li>';
    
    const resistanceHtml = resistances.length > 0
      ? resistances.map(r => `<li>${r.toFixed(2)}</li>`).join('')
      : '<li>Não detectado</li>';
    
    document.getElementById('analysis').innerHTML = `
      <div class="analysis-card">
        <h3>Tendência</h3>
        <p class="trend-value">${analysis.trend?.direction || 'N/A'}</p>
        <p class="trend-strength">Força: ${analysis.trend?.strength?.toFixed(2) || 'N/A'}</p>
      </div>
      
      <div class="analysis-card">
        <h3>RSI (14)</h3>
        <p class="rsi-value">${analysis.rsi?.toFixed(2) || 'N/A'}</p>
      </div>
      
      <div class="analysis-card">
        <h3>Médias Móveis</h3>
        <p><strong>EMA(9):</strong> ${analysis.moving_averages?.ema9?.toFixed(2) || 'N/A'}</p>
        <p><strong>SMA(20):</strong> ${analysis.moving_averages?.sma20?.toFixed(2) || 'N/A'}</p>
        <p><strong>SMA(50):</strong> ${analysis.moving_averages?.sma50?.toFixed(2) || 'N/A'}</p>
      </div>
      
      <div class="analysis-card">
        <h3>Padrões de Price Action</h3>
        <div class="patterns-container">${patternHtml}</div>
      </div>
      
      <div class="analysis-card">
        <h3>Suportes</h3>
        <ul class="levels-list">${supportHtml}</ul>
      </div>
      
      <div class="analysis-card">
        <h3>Resistências</h3>
        <ul class="levels-list">${resistanceHtml}</ul>
      </div>
    `;
  } catch (error) {
    console.error('Error fetching analysis:', error);
    document.getElementById('analysis').innerHTML = 
      `<p class="error">Erro ao carregar análise: ${error.message}</p>`;
  }
}
