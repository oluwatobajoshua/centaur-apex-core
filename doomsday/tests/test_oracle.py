import pytest
from doomsday.oracle import (
    ConfigDrivenOracle,
    ConversionStatus,
    SimulationOracle,
    oracle_factory,
)


def test_simulation_quote_deterministic():
    o = SimulationOracle(fee_bps=10)
    q1 = o.quote("ETH", "USDT", 1.0)
    q2 = o.quote("ETH", "USDT", 1.0)
    assert q1 == q2
    assert q1.est_quantity_out == pytest.approx(0.999)
    assert q1.quote_ref  # stored before any action


def test_simulation_submit_and_status():
    o = SimulationOracle()
    q = o.quote("BTC", "USD", 0.5)
    order = o.submit_conversion_request(q)
    assert order.status is ConversionStatus.SUBMITTED
    assert order.quote_ref == q.quote_ref
    again = o.get_conversion_status(order.order_id)
    assert again.order_id == order.order_id
    o.settle(order.order_id)
    assert o.get_conversion_status(order.order_id).status is ConversionStatus.SETTLED


def test_simulation_unknown_order_raises():
    o = SimulationOracle()
    with pytest.raises(KeyError):
        o.get_conversion_status("nope")


def test_non_positive_quantity_rejected():
    o = SimulationOracle()
    with pytest.raises(ValueError):
        o.quote("ETH", "USDT", 0.0)


def test_config_driven_wraps_inner_oracle():
    inner = SimulationOracle()
    o = ConfigDrivenOracle(inner, label="custodian-A")
    q = o.quote("SOL", "USDT", 2.0)
    order = o.submit_conversion_request(q)
    assert o.get_conversion_status(order.order_id).asset_in == "SOL"
    assert o.label == "custodian-A"


def test_oracle_factory_unknown_fails_closed():
    with pytest.raises(ValueError):
        oracle_factory("mystery-custodian")


def test_oracle_factory_known_returns_working_oracle():
    o = oracle_factory("simulation_oracle")
    q = o.quote("BTC", "USDT", 1.0)
    assert o.submit_conversion_request(q).quote_ref == q.quote_ref


def test_quote_ref_binds_submission():
    o = SimulationOracle()
    forged = o.quote("ETH", "USDT", 1.0)
    forged.indicative = False
    order = o.submit_conversion_request(forged)
    assert order.quote_ref == forged.quote_ref