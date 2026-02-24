# ISSUE: Monitor UI Density & Visual Formatting Improvement

**Sprint:** 2026-02-20  
**Owner:** @Fullstack  
**Status:** READY FOR IMPLEMENTATION  
**Reference:** Architecture Decision in `.memory-bank/activeContext.md` (Section "UI/UX Visual Density & Formatting Guidelines")

---

## 📋 Objetivo

Eliminar o gap de usabilidade entre a UI legada (`src/gui/monitor_ui.py` com ~20-25 eventos visíveis) e a UI nova (`newapp/templates/monitor.html` com ~8 itens visíveis). A nova implementação deve:

1. **Aumentar densidade visual** da exibição de eventos de 8 para 25+ linhas simultâneas.
2. **Aplicar formatação rigorosa** (2 casas decimais, larguras de coluna fixas) equivalente ao legado.
3. **Mapear corretamente cores de severidade** por evento (not per card).
4. **Implementar tabela densa** com suporte a scroll interno e header sticky.

---

## 🎨 Especificação Visual

### Layout (Seção Monitor)
```
┌─ STICKY HEADER (50px)
│  Status: 5 monitores | Last Tick: 15:30:42 | Total Events: 237
├─ HORIZONTAL RESUMO CARDS (3x cards, 120px height each)
│  [📊 ML Signals: 156] [⚙️ Decision Blocks: 23] [📈 Indicators: 4]
├─ DENSE EVENT TABLE (25+ rows visible, ~500px height, overflow-y scroll)
│  ┌ HEADER ─────────────────────────────────────────────
│  │ TIME      │ TICKER │ TYPE │ PRICE       │ PROB  │ SIGNAL │ STATUS
│  ├ ROW 1    ─────────────────────────────────────────────
│  │ 15:30:42  │ WDO$   │ 🚨   │ 95.60       │ 72.00 │ COMPRA │ ✅
│  │           │ BKG    │ 📊   │ 27.53       │ 62.50 │ VENDA  │ ⚠️
│  │ ...
│  └─────────────────────────────────────────────────────
```

### Column Specifications

| Column | Width | Content | Format | Align |
|--------|-------|---------|--------|-------|
| **TIME** | 70px | HH:MM:SS | 2-digit time | right |
| **TICKER** | 65px | Symbol | "WDO$", "WIN$", etc. | center |
| **TYPE** | 60px | Severity Icon | 🚨 / 📊 / • | center |
| **PRICE** | 90px | Last candle close | 2-decimal (e.g., 95.60) | right |
| **PROB(%)** | 70px | ML probability | 2-decimal (e.g., 72.00) | right |
| **SIGNAL** | 80px | Action | "COMPRA" / "VENDA" / "HOLD" | center |
| **STATUS** | 75px | Decision state | ✅ / ⚠️ icon + text | center |

**Total table width:** ~510px (fits 1024+ screens with left margin)

### Color & Icon Mapping

| Category | Icon | Background | Text | Border | Condition |
|----------|------|------------|------|--------|-----------|
| **ALERT** | 🚨 | #fff3cd | #856404 | #ffc107 | `prob > 0.65` |
| **INFO** | 📊 | #d1ecf1 | #0c5460 | #17a2b8 | `0.55 < prob ≤ 0.65` |
| **TICK** | • | #ffffff | #6c757d | #dee2e6 | `prob ≤ 0.55` |

### Status Indicator

| Status | Icon | Display | Condition |
|--------|------|---------|-----------|
| **VALID** | ✅ | Green checkmark | `decision.signal_valid == true` |
| **BLOCKED** | ⚠️ | Orange warning | `decision.signal_valid == false` (incl. RSI/pattern blocks) |

---

## 💾 Payload Contract

Backend must supply (via WebSocket, same structure as current):

```json
{
  "ticker": "WDO$",
  "timeframe": "M5",
  "timestamp": "2026-02-24T15:30:42.000Z",
  "ml": {
    "probability": 0.72,
    "signal": "COMPRA",
    "confidence": 0.85
  },
  "decision": {
    "signal_valid": true,
    "validation_reason": "",
    "blocked_by": null
  },
  "analysis": {
    "rsi": 65.2,
    "macd_signal": "bullish",
    "pattern": "NORMAL"
  },
  "indicators": {
    "sma21": 95.45,
    "sma200": 94.80,
    "ema9": 95.52
  },
  "candle": {
    "close": 95.60,
    "high": 95.75,
    "low": 95.45
  }
}
```

---

## 📝 Implementation Tasks

### Task 1: CSS Table Structure
- [ ] Create dense table in `.monitor-events-table` with:
  - Fixed-width columns (70px, 65px, 60px, 90px, 70px, 80px, 75px total ~510px).
  - `max-height: 500px` with `overflow-y: auto`.
  - Sticky `<thead>` with 50px height.
  - Row height: 32px (fits ~15-16 rows without scroll, 25+ with scroll).
  - Font-size: 12px for density.
  - Border: `#e0e0e0` 1px per row.

### Task 2: Dynamic Class Assignment
- [ ] In `monitor.js`, for each event in log:
  - Compute severity class based on `ml.probability`:
    - `prob > 0.65` → `row-alert-high` (🚨 background #fff3cd).
    - `0.55 < prob ≤ 0.65` → `row-alert-medium` (📊 background #d1ecf1).
    - `prob ≤ 0.55` → `row-alert-low` (• background white).
  - Add `valid` or `invalid` class based on `decision.signal_valid`.
  - Compute icon from probability band (not from static class name).

### Task 3: HTML Event Row Template
- [ ] Create template for event row:
  ```html
  <tr class="event-row row-alert-{severity} {valid-state}">
    <td class="col-time">HH:MM:SS</td>
    <td class="col-ticker">SYMBOL</td>
    <td class="col-type">{icon}</td>
    <td class="col-price">99.99</td>
    <td class="col-prob">72.00</td>
    <td class="col-signal">COMPRA</td>
    <td class="col-status">{icon} TEXT</td>
  </tr>
  ```

### Task 4: Header Resumo Cards (Sticky)
- [ ] Replace or augment existing 4-block grid with 3-card horizontal bar:
  - `.resumo-card` container (flex row, gap 10px, height 60px, bg light gray).
  - Each card: count + label (e.g., "📊 ML Signals: 156").
  - Position: above table, sticky on scroll.

### Task 5: Format Functions
- [ ] Implement in `monitor.js`:
  - `formatTime(isoString)` → "HH:MM:SS" (2-digit hours, minutes, seconds).
  - `formatPrice(float)` → string with 2 decimals (e.g., 95.60).
  - `formatProbability(float)` → string with 2 decimals + "%" (e.g., 72.00%).
  - `getSeverityClass(probability)` → "row-alert-high" | "row-alert-medium" | "row-alert-low".
  - `getStatusIcon(decision.signal_valid)` → "✅" | "⚠️".

### Task 6: Deprecation (if applicable)
- [ ] Remove or hide the old 4-card grid layout (`.monitor-grid` with 2x2 or 4x1 layout).
- [ ] OR transform it to sticky header area only (resumo cards above table).

---

## 🧪 Test Cases (QA Check)

### Edge Cases: Probability Boundaries
```
Probability = 0.65 → row-alert-medium (NOT high) ✓
Probability = 0.66 → row-alert-high ✓
Probability = 0.55 → row-alert-low (NOT medium) ✓
Probability = 0.56 → row-alert-medium ✓
```

### Visual Verification
```
✓ 25+ rows visible on 1024×768 screen without scroll.
✓ Row height consistent 32px per event.
✓ Column borders visible and aligned.
✓ Header sticky (top: 0) when scrolling past 10th row.
✓ Colors match exactly: #fff3cd (ALERT), #d1ecf1 (INFO), #ffffff (TICK).
✓ Status icons (✅/⚠️) visible and centered in last column.
```

### Data Integrity
```
✓ Events render in reverse chronological order (newest top).
✓ Price/Probability formatted to exactly 2 decimals.
✓ Signal text always UPPERCASE (COMPRA/VENDA/HOLD).
✓ Icon matches severity band (not hardcoded).
```

### Payload Sync
```
✓ Payload includes all required fields (ml.probability, decision.signal_valid, candle.close).
✓ WebSocket emit frequency same as current (no degradation).
✓ No console errors related to missing fields.
```

---

## 📦 Acceptance Criteria

1. **Visual Density:** Monitor displays 25+ events simultaneously without horizontal scroll.
2. **Formatting Rigor:** All prices and probabilities formatted to 2 decimals; time in HH:MM:SS.
3. **Severity Mapping:** Per-row color coding (background + border) based on probability band.
4. **Status Indicators:** Decision state displayed via ✅/⚠️ in last column.
5. **Sticky Header:** Time range and total count remain visible during scroll.
6. **Resumo Cards:** Aggregate counts (ML Signals, Decision Blocks, Indicators) updated in real time.
7. **No Breaking Changes:** Payload format, WebSocket frequency, and backend logic unchanged.

---

## 🔗 Related Documentation

- **Memory Bank:** [`.memory-bank/activeContext.md`](.memory-bank/activeContext.md) — UI/UX Visual Density & Formatting Guidelines section.
- **System Patterns:** [`.memory-bank/systemPatterns.md`](.memory-bank/systemPatterns.md) — Section 8: Signal Consolidation Rule.
- **Backend Payload:** [ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md](ISSUE_BACKENDQUANT_UNIFICACAO_ML_ANALISE_FIRST_TICK.md) — Payload contract and decision block logic.

---

## ⏱️ Estimated Effort
**L (Large):** 2–3 days (CSS table layout + JS logic + testing edge cases).

---

## 📌 Notes

- **No backend changes required** for this task; all logic is frontend rendering and formatting.
- **Preserve backward compatibility:** Existing WebSocket payload format and frequency must not change.
- **DPI-aware:** Test on both standard (96 DPI) and high-DPI (144 DPI+) screens to ensure column widths remain readable.
