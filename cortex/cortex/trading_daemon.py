"""Continuous Cortex trading daemon.

Genesis DNA (G5 framework): provides the *mechanism* for continuous market
tick processing, proposal emission, Constitution adjudication, and Doomsday
integration. The concrete pricing/sizing heuristics remain System-Owned
(S2); this daemon only proves the pipeline wiring end-to-end.

Once the self-evolution engine is bootstrapped, it may replace this daemon
with a meta-learned version. This is Genesis scaffolding, not permanent alpha.
"""
import argparse
import json
import time
from typing import Any

from adapters.base import AbstractExchangeAdapter, UniversalOrderIntent
from adapters.proposal_bridge import verdict_to_order_action
from doomsday.config import DeadManConfig, EscalationStep, StepType
from doomsday.daemon import DeadManSwitchDaemon

from cortex.constitution_client import ConstitutionIPCClient
from cortex.engine import CortexEngine
from cortex.proposal_api import TradeProposal


def proposal_dict_to_trade_proposal(proposal: dict[str, Any]) -> TradeProposal:
    """Convert a dict (from TradeProposal.model_dump()) back to a typed proposal."""
    return TradeProposal(**{k: v for k, v in proposal.items() if k in TradeProposal.model_fields})


def _default_doomsday_config(heartbeat_interval_s: float = 5.0) -> DeadManConfig:
    return DeadManConfig(
        heartbeat_interval_s=heartbeat_interval_s,
        grace_multiplier=3,
        escalation_multiplier=6,
        escalation_enabled=True,
        abortable_until_step=2,
        liquidation_grace_multiplier=4,
        plan=[
            EscalationStep(step=StepType.NOTIFY, channels=["ops-slack"]),
            EscalationStep(step=StepType.HALT_PLACEMENTS),
            EscalationStep(step=StepType.REDUCE_EXPOSURE, target_percentage=50.0),
            EscalationStep(step=StepType.ACQUIRE_ASSETS, asset_out="USDC", via="simulation_oracle"),
            EscalationStep(step=StepType.SEAL),
        ],
        oracle="simulation_oracle",
        strict_heartbeat_signing=False,
        max_journal_entries=2048,
    )


class TradingDaemon:
    """Continuous trading loop: market tick -> Cortex proposal -> Constitution verdict -> adapter execution.

    Also runs the Doomsday dead-man switch in-process: if the daemon's own
    heartbeat stops (crash, deadlock), the Doomsday daemon escalates to
    emergency liquidation.
    """

    def __init__(
        self,
        asset_id: str = "EURUSD",
        constitution_host: str = "127.0.0.1",
        constitution_port: int = 15565,
        equity: float = 100_000.0,
        heartbeat_interval_s: float = 5.0,
        tick_interval_s: float = 60.0,
        exchange_adapter: AbstractExchangeAdapter | None = None,
    ):
        self.asset_id = asset_id
        self.client = ConstitutionIPCClient(
            host=constitution_host,
            port=constitution_port,
            timeout=2.0,
        )
        self.engine = CortexEngine(asset_id=asset_id)
        self.heartbeat_interval_s = heartbeat_interval_s
        self.tick_interval_s = tick_interval_s
        self.adapter = exchange_adapter
        self.portfolio = {
            "timestamp": int(time.time()),
            "total_equity": equity,
            "cash_balance": round(equity * 0.9, 2),
            "high_water_mark": equity,
            "open_positions": [],
        }
        self._dormant = DeadManSwitchDaemon(
            config=_default_doomsday_config(heartbeat_interval_s),
        )
        self._running = False

    def start(self) -> None:
        """Open IPC session, start Doomsday daemon, and begin tick loop."""
        self.client.open_session()
        self.client.heartbeat()
        self._dormant.start(tick_interval_s=self.heartbeat_interval_s / 4)
        self._running = True
        print(f"[TradingDaemon] online — asset={self.asset_id}, equity={self.portfolio['total_equity']}", flush=True)

    def _process_tick(self, market_tick: dict[str, Any]) -> None:
        """Process one market tick: generate proposal, adjudicate, execute."""
        tick = dict(market_tick)
        tick.setdefault("account_equity", self.portfolio["total_equity"])
        tick.setdefault("asset_id", self.asset_id)

        result = self.engine.evaluate_market_tick(tick)
        if result["status"] == "NoAction":
            print("[TradingDaemon] NoAction — tick skipped", flush=True)
        else:
            proposal = result["proposal"]
            verdict = self.client.evaluate(self.portfolio, proposal)
            self._handle_verdict(verdict, proposal)

        # Pulse the Doomsday switch to prove liveness
        self._dormant.beat()

    def _handle_verdict(self, verdict: dict, proposal: dict[str, Any]) -> None:
        """Act on Constitution verdict: route approved orders through the adapter,
        update portfolio, log rejected/emergency."""
        if "Approved" in verdict:
            approved = verdict["Approved"]
            notional = approved.get("adjusted_notional", 0.0)
            print(f"[TradingDaemon] Approved — notional={notional}", flush=True)

            # G3: Bridge approved proposal → UniversalOrderIntent → adapter execution
            # I5: only the Constitution's verdict (above) authorises an order;
            # the adapter merely executes the routed intent.
            if self.adapter and self.adapter.health_check():
                intent = verdict_to_order_action(
                    verdict,
                    proposal_dict_to_trade_proposal(proposal),
                    proposal.get("_reference_price", 0.0),
                )
                if intent:
                    receipt = self.adapter.execute_order(intent)
                    print(f"[TradingDaemon] Executed — {receipt.status} @ {receipt.filled_price}", flush=True)
                    self._apply_execution(receipt, intent, notional)
            else:
                # Dry-run: update portfolio in-memory without adapter execution
                self._apply_approved_proposal(proposal, notional)
        elif "EmergencyLiquidationAll" in verdict:
            print("[TradingDaemon] EMERGENCY LIQUIDATION — Halt all trading", flush=True)
            self._dormant.disarm("")
        else:
            print(f"[TradingDaemon] Rejected — {verdict}", flush=True)

    def _apply_execution(self, receipt: Any, intent: UniversalOrderIntent, notional: float) -> None:
        """Update portfolio with actual execution results from the adapter."""
        if receipt.status == "FILLED":
            self.portfolio["open_positions"].append({
                "asset_id": intent.asset_id,
                "notional_value": notional,
                "entry_price": receipt.filled_price,
                "quantity": receipt.filled_quantity,
            })
        elif receipt.status == "DRY_RUN":
            # Fallback for dry-run adapters
            self._apply_approved_proposal({"asset_id": intent.asset_id, "target_notional": notional}, notional)

    def _apply_approved_proposal(self, proposal: dict, notional: float) -> None:
        """Update portfolio in-memory for approved proposals (dry-run mode)."""
        self.portfolio["open_positions"].append({
            "asset_id": proposal.get("asset_id", ""),
            "notional_value": notional,
            "entry_price": proposal.get("target_notional", 0.0) / max(notional, 1.0),
        })
    def _update_health(self) -> bool:
        """Check Constitution daemon health via Heartbeat."""
        try:
            self.client.heartbeat()
            return True
        except Exception:  # noqa: BLE001 - health check, any failure means unhealthy
            return False

    def run_loop(self, market_data_source: list[dict[str, Any]] | None = None) -> None:
        """Run the continuous trading loop.

        Args:
            market_data_source: Optional list of pre-loaded ticks for replay.
                If None, the loop blocks on stdin for JSON lines.
        """
        if market_data_source is None:
            print("[TradingDaemon] Awaiting market ticks via stdin (JSON lines)...", flush=True)

        try:
            for tick in self._iter_ticks(market_data_source):
                if not self._running:
                    break

                # Health check: Constitution daemon must be responsive
                if not self._update_health():
                    print("[TradingDaemon] WARNING — Constitution IPC unreachable", flush=True)
                    # Doomsday will catch this; we continue until it escalates

                self._process_tick(tick)
                time.sleep(self.tick_interval_s)
        except KeyboardInterrupt:
            print("\n[TradingDaemon] Shutting down...", flush=True)
        finally:
            self._dormant.stop()
            self.client.close_session()
            print("[TradingDaemon] Stopped.", flush=True)

    def _iter_tick(self, source: list[dict] | None):
        """Yield ticks from a list or stdin JSON-lines."""
        if source is not None:
            yield from source
        else:
            import sys
            for line in sys.stdin:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def _iter_ticks(self, source: list[dict] | None):
        yield from self._iter_tick(source)

    def stop(self) -> None:
        self._running = False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Centaur-Apex continuous trading daemon (G5 framework scaffold)",
    )
    parser.add_argument("--asset", default="EURUSD")
    parser.add_argument("--constitution-host", default="127.0.0.1")
    parser.add_argument("--constitution-port", type=int, default=15565)
    parser.add_argument("--equity", type=float, default=100_000.0)
    parser.add_argument("--heartbeat-interval", type=float, default=5.0)
    parser.add_argument("--tick-interval", type=float, default=60.0)
    parser.add_argument(
        "--market-data",
        default=None,
        help="JSON file with a list of market ticks to replay (default: stdin JSON lines)",
    )
    args = parser.parse_args(argv)

    daemon = TradingDaemon(
        asset_id=args.asset,
        constitution_host=args.constitution_host,
        constitution_port=args.constitution_port,
        equity=args.equity,
        heartbeat_interval_s=args.heartbeat_interval,
        tick_interval_s=args.tick_interval,
    )

    ticks = None
    if args.market_data:
        with open(args.market_data, encoding="utf-8") as f:
            ticks = json.load(f)

    daemon.start()
    daemon.run_loop(ticks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
