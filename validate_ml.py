#!/usr/bin/env python
"""Quick ML validation script for QUANT agent."""
import yaml
import os
from pathlib import Path

def main():
    # 1. Validate YAML
    try:
        with open('configs/main.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        print("✓ YAML VALID")
        print(f"  Assets configured: {len(config['assets'])}")
        print(f"  Model directory: {config['global_settings']['model_directory']}")
        
        # List enabled assets and strategies
        for asset in config['assets']:
            status = "ENABLED" if asset.get('enabled', False) else "DISABLED"
            print(f"  - {asset['ticker']}: {status}")
            for strat in asset.get('strategies', []):
                print(f"    └─ {strat['name']} ({strat['module']})")
    except Exception as e:
        print(f"✗ YAML INVALID: {e}")
        return False
    
    # 2. Check models directory
    print("\n✓ MODEL ARTIFACTS:")
    models_dir = Path('models')
    prod_files = sorted(models_dir.glob('*_prod_*'))
    
    wdo_files = [f for f in prod_files if f.name.startswith('WDO$')]
    win_files = [f for f in prod_files if f.name.startswith('WIN$')]
    
    print(f"  WDO$ artifacts: {len(wdo_files)}")
    for f in wdo_files:
        print(f"    - {f.name}")
    
    print(f"  WIN$ artifacts: {len(win_files)}")
    for f in win_files:
        print(f"    - {f.name}")
    
    # 3. Validate strategy code
    print("\n✓ STRATEGY CODE:")
    lstm_path = Path('src/strategies/lstm_volatility.py')
    if lstm_path.exists():
        size = lstm_path.stat().st_size
        print(f"  lstm_volatility.py exists ({size} bytes)")
    else:
        print("  ✗ lstm_volatility.py NOT FOUND")
    
    # 4. Check for complete model sets
    print("\n✓ MODEL COMPLETENESS:")
    for ticker in ['WDO$', 'WIN$']:
        required = [f"{ticker}_LSTMVolatilityStrategy_M5_prod_{ext}" 
                   for ext in ['lstm.keras', 'params.joblib', 'scaler.joblib']]
        missing = [r for r in required if not (models_dir / r).exists()]
        if missing:
            print(f"  ✗ {ticker}: INCOMPLETE - missing {missing}")
        else:
            print(f"  ✓ {ticker}: COMPLETE (3/3 artifacts)")
    
    return True

if __name__ == '__main__':
    main()
