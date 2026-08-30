"""
Scratch script (not part of the automated test suite): manually trigger
a risk_check() call and confirm the decision gets written to the audit
trail via core/persistence/risk_audit.py.

The audit write happens on a background thread (see risk_audit.py),
so this script waits a bit afterward to give it time to finish and
print its own log line before the script exits.

Run with:
    python scripts/test_risk_audit.py
"""
from core.execution.executor import risk_check
from core.strategy.base import Signal

signal = Signal(symbol="BTCUSDT", action="buy", reason="manual test")
allowed = risk_check(signal, quantity=10, current_inventory=0)
print(f"risk_check returned: {allowed}")

import time
print("Waiting for background audit write to finish...")
time.sleep(20)
print("Done waiting.")