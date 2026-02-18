---
name: FULLSTACK Task
about: Hybrid UI improvements for live monitor
title: "[FULLSTACK] Hybrid UI: virtual scroll + Split.js + CSS Grid"
labels: "agent:fullstack, domain:ui, sprint-3"
assignees: ""
---

## Objective
Enhance the Plotly monitor UI with virtualized signal history, resizable panes, and a grid-based layout.

## Context & Files
- Target: templates/charts_clean.html
- Target: templates/static/css/charts_clean.css
- Target: templates/static/js/live_chart.js
- New: templates/static/js/virtual-scroll.js
- Related: src/api/main.py

## Technical Scope
1. Add Split.js CDN and initialize split panes for chart + sidebar.
2. Add CSS Grid layout and responsive tweaks.
3. Implement virtual scroll utility and use it for signal history.
4. Ensure static assets are served (mount root static if present).
5. Keep Tkinter GUI untouched.

## Dependencies / Blockers
- None.

## Definition of Done
- UI loads with resizable panes and virtualized history.
- No JS errors in console on page load.
- Existing WebSocket updates still render chart and latest signal.
