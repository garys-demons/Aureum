"""
One-off runner for the Phase 5 parameter sensitivity sweep -
research/parameter_sensitivity.py is a library module with no
entry point of its own, so this drives run_parameter_sweep()
directly and writes the results CSV.
"""
from research.parameter_sensitivity import run_parameter_sweep
from core.strategy.baseline_market_maker import BaselineMarketMaker

param_grid = {
    "base_half_spread": [0.0003, 0.0005, 0.001],
    "inventory_skew_sensitivity": [0.00001, 0.00002, 0.00005],
}
window_datasets = [
    "adausdt_candles_1m_recent_24h",
    "adausdt_candles_1m_prior_24h",
    "adausdt_candles_1m_prior_48h",
]

df = run_parameter_sweep(
    strategy_factory=lambda **params: BaselineMarketMaker(symbol="ADAUSDT", **params),
    param_grid=param_grid,
    window_datasets=window_datasets,
)

df.to_csv("docs/phase5_parameter_sensitivity_results.csv", index=False)
print(f"Wrote {len(df)} rows to docs/phase5_parameter_sensitivity_results.csv")
print(df[["base_half_spread", "inventory_skew_sensitivity", "window", "final_inventory", "max_abs_inventory"]].to_string())