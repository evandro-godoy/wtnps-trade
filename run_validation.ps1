# Navigate to correct directory
cd C:\projects\wtnps-trade.worktrees\copilot-worktree-2026-01-31T13-26-42

Write-Host "=== WTNPS-Trade Implementation Validation ===" -ForegroundColor Cyan
Write-Host ""

# Task 1: Install Dependencies
Write-Host "[1/5] Installing dependencies..." -ForegroundColor Yellow
poetry install --quiet
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Dependencies installed" -ForegroundColor Green
} else {
    Write-Host "✗ Dependency installation failed" -ForegroundColor Red
    exit 1
}

# Task 2: Validate Imports
Write-Host "[2/5] Validating module imports..." -ForegroundColor Yellow
poetry run python -c "from src.gui.monitor_ui import MonitorApp; from src.gui.chart_widget import CandlestickChartWidget; from src.live.replay_engine import ReplayEngine; print('✓ All imports successful')"
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ All modules import correctly" -ForegroundColor Green
} else {
    Write-Host "✗ Import validation failed" -ForegroundColor Red
    exit 1
}

# Task 3: Syntax Validation
Write-Host "[3/5] Validating Python syntax..." -ForegroundColor Yellow
$files = @(
    "src\gui\chart_widget.py",
    "src\live\replay_engine.py",
    "src\gui\monitor_ui.py",
    "run_monitor_gui.py"
)

foreach ($file in $files) {
    poetry run python -m py_compile $file
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file" -ForegroundColor Red
        exit 1
    }
}

# Task 4: Test CLI Help
Write-Host "[4/5] Testing CLI arguments..." -ForegroundColor Yellow
poetry run python run_monitor_gui.py --help | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ CLI arguments validated" -ForegroundColor Green
} else {
    Write-Host "✗ CLI validation failed" -ForegroundColor Red
}

# Task 5: Documentation Check
Write-Host "[5/5] Checking documentation..." -ForegroundColor Yellow
if (Test-Path "IMPLEMENTATION_PLAN.md") {
    Write-Host "✓ IMPLEMENTATION_PLAN.md exists" -ForegroundColor Green
} else {
    Write-Host "✗ Documentation missing" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Validation Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor Yellow
Write-Host "1. Test Live Mode:   poetry run python run_monitor_gui.py --mode live"
Write-Host "2. Test Replay Mode: poetry run python run_monitor_gui.py --mode replay --date 2025-11-20 --speed 2.0"
Write-Host ""
