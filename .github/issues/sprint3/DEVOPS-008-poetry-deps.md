---
name: DEVOPS Task
about: Dependency alignment for runtime scripts
title: "[DEVOPS] Align Poetry dependencies"
labels: "agent:devops, domain:ops, sprint-3"
assignees: ""
---

## Objective
Ensure missing runtime dependencies are declared in pyproject.toml.

## Context & Files
- Target: pyproject.toml
- Related: scripts/dry_run.py, src/data_handler/provider.py

## Technical Scope
1. Add yfinance, psutil, tkcalendar dependencies.
2. Keep existing versions compatible with Python 3.12.
3. Do not remove bokeh in this change.

## Dependencies / Blockers
- None.

## Definition of Done
- poetry install completes without missing imports.
- Imports for yfinance, psutil, tkcalendar work.
