
from simulation.synthetic_gen import SyntheticRegimeGenerator


class TestSyntheticRegimeGenerator:
    def test_sample_returns_valid_regime(self):
        gen = SyntheticRegimeGenerator()
        regime = gen.sample_next_regime()
        assert regime in SyntheticRegimeGenerator.REGIMES

    def test_deterministic_with_same_seed(self):
        gen1 = SyntheticRegimeGenerator(seed=42)
        gen2 = SyntheticRegimeGenerator(seed=42)
        regimes1 = [gen1.sample_next_regime() for _ in range(100)]
        regimes2 = [gen2.sample_next_regime() for _ in range(100)]
        assert regimes1 == regimes2

    def test_different_seeds_differ(self):
        gen1 = SyntheticRegimeGenerator(seed=1)
        gen2 = SyntheticRegimeGenerator(seed=2)
        r1 = [gen1.sample_next_regime() for _ in range(100)]
        r2 = [gen2.sample_next_regime() for _ in range(100)]
        # Not guaranteed to differ on every element, but not all identical
        assert r1 != r2

    def test_price_path_length(self):
        gen = SyntheticRegimeGenerator()
        prices, equity = gen.generate_price_path(start_price=100.0, points=500)
        assert len(prices) == 500
        assert len(equity) == 500

    def test_prices_positive(self):
        gen = SyntheticRegimeGenerator()
        prices, _ = gen.generate_price_path(start_price=100.0, points=1000)
        for p in prices:
            assert p > 0.0

    def test_equity_positive(self):
        gen = SyntheticRegimeGenerator()
        _, equity = gen.generate_price_path(start_price=100.0, points=1000)
        for e in equity:
            assert e > 0.0

    def test_start_price_appears_in_equity(self):
        gen = SyntheticRegimeGenerator()
        prices, equity = gen.generate_price_path(start_price=100.0, points=10)
        assert equity[0] == prices[0]

    def test_custom_volatility(self):
        gen = SyntheticRegimeGenerator()
        prices_low, _ = gen.generate_price_path(start_price=100.0, points=1000, volatility=0.001)
        gen2 = SyntheticRegimeGenerator()
        prices_high, _ = gen2.generate_price_path(start_price=100.0, points=1000, volatility=0.1)
        # Both should have valid prices
        assert all(p > 0 for p in prices_low)
        assert all(p > 0 for p in prices_high)
