# 🔧 CI/CD Hardening - Implementation Guide

## Quick Start (10 minutes)

### Step 1: Install Dev Dependencies

```powershell
# Install linting tools
poetry add --group dev flake8 mypy ruff

# Verify installation
poetry show flake8 mypy ruff
```

**Expected Output:**
```
flake8  7.x.x ...
mypy    1.x.x ...
ruff    0.x.x ...
```

### Step 2: Run Local Tests

```powershell
# Run smoke tests
poetry run pytest tests/unit/test_smoke.py -v

# Expected: 5 passed
```

### Step 3: Run Linting Locally

```powershell
# Flake8
poetry run flake8 src/ newapp/src/ --max-line-length=100 --exclude=archive/

# Ruff (fast alternative)
poetry run ruff check src/ newapp/src/ --exclude archive

# MyPy (type checking)
poetry run mypy src/ --ignore-missing-imports
```

**Expected:** Some warnings acceptable initially, no critical errors.

### Step 4: Update CI Workflow

**Option A: Replace existing** (RECOMMENDED)
```powershell
# Backup current workflow
Copy-Item .github/workflows/ci.yml .github/workflows/ci.yml.backup

# Use enhanced workflow
Move-Item .github/workflows/ci_enhanced.yml.proposed .github/workflows/ci.yml
```

**Option B: Manual merge**  
Copy jobs from `ci_enhanced.yml.proposed` → `ci.yml`

### Step 5: Commit & Push

```powershell
git add .
git commit -m "ci: Add lint, type-check jobs and smoke tests"
git push origin main
```

**Verify:** Check GitHub Actions tab for green checkmarks.

---

## Checklist

### Immediate (Before Phase 3.3 Testing)
- [ ] `poetry add --group dev flake8 mypy ruff`
- [ ] `poetry install` (refresh lock)
- [ ] Run `poetry run pytest tests/unit/test_smoke.py` (verify 5 passed)
- [ ] Run `poetry run flake8 src/ --max-line-length=100` (review warnings)
- [ ] Replace `.github/workflows/ci.yml` with enhanced version
- [ ] Commit changes to `main`
- [ ] Verify GitHub Actions run successfully

### Optional Enhancements
- [ ] Add CI badge to README.md
- [ ] Enable branch protection for `main` (require CI pass)
- [ ] Configure Dependabot for security updates
- [ ] Add pre-commit hooks (`.pre-commit-config.yaml`)

---

## Troubleshooting

### Issue: Flake8 reports too many errors

**Solution:** Start with relaxed config:
```powershell
poetry run flake8 src/ --max-line-length=100 --ignore=E501,W503
```

Gradually fix categories over time.

### Issue: MyPy fails with import errors

**Solution:** Add stubs or ignore specific modules:
```powershell
poetry run mypy src/ --ignore-missing-imports --exclude 'src/live'
```

### Issue: pytest collects tests from newapp/

**Solution:** `pyproject.toml` already configured to only use `tests/` via:
```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
```

If still an issue, add to `.gitignore`:
```
newapp/.cache_data/
```

### Issue: CI workflow times out

**Solution:** Check timeout is set:
```yaml
jobs:
  test:
    timeout-minutes: 10  # Adjust as needed
```

---

## Next Steps

1. **Populate tests/** with 3-5 more unit tests:
   - `test_timeframe.py` - Test timeframe conversions
   - `test_config_loader.py` - Test YAML config loading
   - `test_strategy_base.py` - Test Strategy ABC methods

2. **Document testing strategy** in README:
   ```markdown
   ## Testing
   
   Run tests: `poetry run pytest`
   Run linting: `poetry run flake8 src/`
   Run type check: `poetry run mypy src/`
   ```

3. **Monitor CI health** during Phase 3.3:
   - Check Actions tab daily
   - Fix warnings as they appear
   - Maintain green status

---

## Reference

- **Report:** [reports/DEVOPS_CI_Validation_Report.md](../reports/DEVOPS_CI_Validation_Report.md)
- **Original Prompt:** [.github/prompts/plan-devopsCI.prompt.md](../.github/prompts/plan-devopsCI.prompt.md)
- **Workflow Reference:** [wtnps-backtest/.github/workflows/ci.yml](../wtnps-backtest/.github/workflows/ci.yml)

---

**Estimated Time:**
- Setup: 10 minutes
- First run validation: 5 minutes  
- **Total: 15 minutes**

Proceed to Phase 3.3 testing once CI is green! 🚀
