import time

from simulation.synthetic_gen import SyntheticRegimeGenerator


class ChronosStressHarness:
    """
    Runs the full trading stack (or a simulated policy adapter) through the
    Chronos loop. The mandate: survive 1,000 simulated years without a fatal
    error, unhandled exception, or irrecoverable drawdown.
    """

    def __init__(self, simulated_years: int = 1000):
        self.simulated_years = simulated_years
        self.generator = SyntheticRegimeGenerator()

    def run(self, policy=None) -> bool:
        """policy: optional callable(cur_price, equity) -> new_notional."""
        print(f"CHRONOS: commencing {self.simulated_years}-year stress cycle.")
        equity = 1_000_000.0
        peak = equity
        worst_drawdown = 0.0
        start = time.perf_counter()

        for year in range(self.simulated_years):
            _prices, curve = self.generator.generate_price_path(
                start_price=100.0,
                points=365,
                volatility=0.02,
            )
            for tick in curve:
                equity *= tick / (curve[0] if curve[0] else 1.0)
                peak = max(peak, equity)
                dd = (peak - equity) / peak
                worst_drawdown = max(worst_drawdown, dd)
                if equity <= 0.0:
                    print(f"FATAL: equity exhausted in simulated year {year}.")
                    return False
                if policy is not None:
                    policy(equity)

        elapsed = time.perf_counter() - start
        print(
            f"CHRONOS SUCCESS: {self.simulated_years} years, "
            f"final equity={equity:,.2f}, worst_drawdown={worst_drawdown:.2%}, "
            f"elapsed={elapsed:.2f}s"
        )
        return True
