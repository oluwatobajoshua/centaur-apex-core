import random
from typing import ClassVar


class SyntheticRegimeGenerator:
    """
    Generates high-entropy synthetic market regimes: hyperinflation loops,
    sudden liquidity evaporation, quantum-era market structures, flash crashes.
    """

    REGIMES: ClassVar[list[str]] = [
        "NORMAL",
        "FLASH_CRASH",
        "HYPERINFLATION_LOOP",
        "LIQUIDITY_EVAPORATION",
        "SOVEREIGN_RESET",
        "LEDGER_FORK",
    ]

    def __init__(self, seed: int = 0xACE1):
        self._rng = random.Random(seed)

    def sample_next_regime(self) -> str:
        return self._rng.choice(self.REGIMES)

    def generate_price_path(
        self,
        start_price: float,
        points: int = 10_000,
        volatility: float = 0.02,
    ) -> tuple[list[float], list[float]]:
        prices = []
        equity_curve = []
        price = start_price
        for _ in range(points):
            regime = self.sample_next_regime()
            shock = {
                "NORMAL": 1.0,
                "FLASH_CRASH": -3.5,
                "HYPERINFLATION_LOOP": 0.8,
                "LIQUIDITY_EVAPORATION": -1.2,
                "SOVEREIGN_RESET": 0.4,
                "LEDGER_FORK": 0.6,
            }[regime]
            drift = self._rng.gauss(0.0, volatility) * shock
            price = max(price * (1.0 + drift), 0.0001)
            prices.append(round(price, 6))
            equity_curve.append(round(max(price, 0.0), 6))
        return prices, equity_curve
