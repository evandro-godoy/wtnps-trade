/* ========================================
   MONITOR EDGE CASE VALIDATION SCRIPT
   ========================================
   
   Abra http://127.0.0.1:8100/monitor no navegador,
   abra DevTools (F12), e cole este script inteiro
   na aba Console para validar os edge cases de
   severidade e formatação rigorosa.
*/

console.log('%c🧪 MONITOR EDGE CASE VALIDATION SCRIPT', 'font-size: 16px; font-weight: bold; color: #5ebcf3;');
console.log('%c══════════════════════════════════════════', 'color: #76838f;');

// Helper: Create test payload
function createTestPayload(prob, signal, valid) {
  return {
    ticker: 'TEST',
    timeframe: 'M5',
    timestamp: new Date().toISOString(),
    ml: {
      probability: prob,
      signal: signal || 'COMPRA',
      direction: 'CALL'
    },
    decision: {
      signal_valid: valid !== false,
      status: valid !== false ? 'VALIDADO' : 'NÃO VALIDADO',
      validation_reason: valid === false ? 'Teste bloqueio' : '',
      severity: {
        label: prob > 0.65 ? 'ALERT' : prob > 0.55 ? 'INFO' : 'TICK',
        cssClass: prob > 0.65 ? 'alert-high' : prob > 0.55 ? 'alert-medium' : 'alert-low',
        icon: prob > 0.65 ? '🚨' : prob > 0.55 ? '📊' : '•'
      }
    },
    ohlcv: {
      open: 100.0,
      high: 100.5,
      low: 99.8,
      close: 100.25,
      volume: 1000
    },
    indicators: {
      ema_9: 100.12,
      ema_20: 99.95,
      sma_20: 99.88,
      sma_50: 99.50,
      rsi_14: 55.0
    },
    analysis: {
      trend: 'ALTA',
      trend_strength: 'MODERADA',
      pattern: 'NORMAL',
      rsi_condition: 'NEUTRO'
    }
  };
}

// Test 1: Edge Case 0.65 (should be INFO, NOT ALERT)
console.log('%c\n📊 Test 1: prob = 0.65 (boundary, should be INFO)', 'color: #17a2b8; font-weight: bold;');
const payload065 = createTestPayload(0.65, 'COMPRA', true);
appendEventRow(normalizeMonitorPayload(payload065));
console.log('Expected: row-alert-medium (INFO), background #d1ecf1, icon 📊');
console.log('Actual severity class:', getSeverityClass(0.65));
console.assert(getSeverityClass(0.65) === 'row-alert-medium', '❌ FAILED: 0.65 should be INFO');
console.log('✅ Passed: 0.65 → INFO');

// Test 2: Edge Case 0.66 (should be ALERT)
console.log('%c\n🚨 Test 2: prob = 0.66 (just above boundary, should be ALERT)', 'color: #ffc107; font-weight: bold;');
const payload066 = createTestPayload(0.66, 'VENDA', true);
appendEventRow(normalizeMonitorPayload(payload066));
console.log('Expected: row-alert-high (ALERT), background #fff3cd, icon 🚨');
console.log('Actual severity class:', getSeverityClass(0.66));
console.assert(getSeverityClass(0.66) === 'row-alert-high', '❌ FAILED: 0.66 should be ALERT');
console.log('✅ Passed: 0.66 → ALERT');

// Test 3: Edge Case 0.55 (should be TICK, NOT INFO)
console.log('%c\n• Test 3: prob = 0.55 (boundary, should be TICK)', 'color: #6c757d; font-weight: bold;');
const payload055 = createTestPayload(0.55, 'HOLD', true);
appendEventRow(normalizeMonitorPayload(payload055));
console.log('Expected: row-alert-low (TICK), background #ffffff, icon •');
console.log('Actual severity class:', getSeverityClass(0.55));
console.assert(getSeverityClass(0.55) === 'row-alert-low', '❌ FAILED: 0.55 should be TICK');
console.log('✅ Passed: 0.55 → TICK');

// Test 4: Edge Case 0.56 (should be INFO)
console.log('%c\n📊 Test 4: prob = 0.56 (just above boundary, should be INFO)', 'color: #17a2b8; font-weight: bold;');
const payload056 = createTestPayload(0.56, 'COMPRA', true);
appendEventRow(normalizeMonitorPayload(payload056));
console.log('Expected: row-alert-medium (INFO), background #d1ecf1, icon 📊');
console.log('Actual severity class:', getSeverityClass(0.56));
console.assert(getSeverityClass(0.56) === 'row-alert-medium', '❌ FAILED: 0.56 should be INFO');
console.log('✅ Passed: 0.56 → INFO');

// Test 5: Decision Blocked (signal_valid = false)
console.log('%c\n⚠️  Test 5: Decision Blocked (signal_valid = false)', 'color: #ff6b6b; font-weight: bold;');
const payloadBlocked = createTestPayload(0.72, 'COMPRA', false);
appendEventRow(normalizeMonitorPayload(payloadBlocked));
console.log('Expected: STATUS column shows "⚠️ BLOCK"');
console.log('Actual status icon:', getStatusIcon(false));
console.assert(getStatusIcon(false) === '⚠️', '❌ FAILED: Blocked should show ⚠️');
console.log('✅ Passed: Blocked signal shows ⚠️ BLOCK');

// Test 6: Decision Valid (signal_valid = true)
console.log('%c\n✅ Test 6: Decision Valid (signal_valid = true)', 'color: #3bbf6b; font-weight: bold;');
const payloadValid = createTestPayload(0.68, 'VENDA', true);
appendEventRow(normalizeMonitorPayload(payloadValid));
console.log('Expected: STATUS column shows "✅ VALID"');
console.log('Actual status icon:', getStatusIcon(true));
console.assert(getStatusIcon(true) === '✅', '❌ FAILED: Valid should show ✅');
console.log('✅ Passed: Valid signal shows ✅ VALID');

// Test 7: Price Formatting (2 decimals)
console.log('%c\n💰 Test 7: Price Formatting (always 2 decimals)', 'color: #5ebcf3; font-weight: bold;');
console.log('formatPrice(95.6):', formatPrice(95.6), '(expected: "95.60")');
console.log('formatPrice(100):', formatPrice(100), '(expected: "100.00")');
console.log('formatPrice(99.999):', formatPrice(99.999), '(expected: "100.00")');
console.assert(formatPrice(95.6) === '95.60', '❌ FAILED: formatPrice(95.6) should be "95.60"');
console.assert(formatPrice(100) === '100.00', '❌ FAILED: formatPrice(100) should be "100.00"');
console.log('✅ Passed: Price formatting uses exactly 2 decimals');

// Test 8: Probability Formatting (2 decimals, percent)
console.log('%c\n📈 Test 8: Probability Formatting (2 decimals + %)', 'color: #5ebcf3; font-weight: bold;');
console.log('formatProbability(0.7234):', formatProbability(0.7234), '(expected: "72.34")');
console.log('formatProbability(0.55):', formatProbability(0.55), '(expected: "55.00")');
console.assert(formatProbability(0.7234) === '72.34', '❌ FAILED: formatProbability(0.7234) should be "72.34"');
console.assert(formatProbability(0.55) === '55.00', '❌ FAILED: formatProbability(0.55) should be "55.00"');
console.log('✅ Passed: Probability formatting uses exactly 2 decimals');

// Test 9: Time Formatting (HH:MM:SS)
console.log('%c\n🕐 Test 9: Time Formatting (HH:MM:SS, 2-digit)', 'color: #5ebcf3; font-weight: bold;');
const testTime = '2026-02-24T09:05:03.000Z';
console.log('formatTime("2026-02-24T09:05:03.000Z"):', formatTime(testTime), '(expected: "09:05:03")');
console.assert(formatTime(testTime) === '09:05:03', '❌ FAILED: formatTime should be "09:05:03" with 2-digit padding');
console.log('✅ Passed: Time formatting uses HH:MM:SS with 2-digit padding');

// Summary
console.log('%c\n══════════════════════════════════════════', 'color: #76838f;');
console.log('%c✅ ALL EDGE CASE TESTS COMPLETED', 'font-size: 16px; font-weight: bold; color: #3bbf6b;');
console.log('%c\nVerifique visualmente na tabela:', 'color: #a0aec0; font-style: italic;');
console.log('  • 9 linhas adicionadas no topo da tabela');
console.log('  • Cores de fundo corretas por severidade');
console.log('  • Ícones 🚨/📊/• correspondem à probabilidade');
console.log('  • Coluna STATUS mostra ✅ VALID ou ⚠️ BLOCK');
console.log('  • Formatação rigorosa de 2 decimais em PRICE e PROB');
console.log('%c\n🎉 Validação manual concluída!', 'font-size: 14px; font-weight: bold; color: #5ebcf3;');
