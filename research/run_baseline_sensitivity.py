"""
Real parameter sensitivity analysis for the Phase 5 baseline strategy
(BaselineMarketMaker). Runs a grid of spread/skew parameters across
3 independent historical windows and reports results side by side -
a parameter that only looks good on ONE window is a look-ahead-via-
parameter-selection red flag, not a recommendation.
"""
from core.strategy.baseline_market_maker import BaselineMarketMaker
from research.parameter_sensitivity import run_parameter_sweep


def main():
    results = run_parameter_sweep(
        strategy_factory=lambda **params: BaselineMarketMaker(symbol="ADAUSDT", **params),
        param_grid={
            "base_half_spread": [0.0003, 0.0005, 0.001],       # narrower, default, wider
            "inventory_skew_sensitivity": [0.00001, 0.00002, 0.00005],  # gentler, default, stronger
        },
        window_datasets=[
            "adausdt_candles_1m_recent_24h",
            "adausdt_candles_1m_prior_24h",
            "adausdt_candles_1m_prior_48h",
        ],
    )

    print(results.to_string(index=False))

    output_path = "docs/phase5_parameter_sensitivity_results.csv"
    results.to_csv(output_path, index=False)
    print(f"\nSaved full results to {output_path}")


if __name__ == "__main__":
    main()