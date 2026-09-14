# Risk Disclosure — Centaur-Apex Core

**Read this document in its entirety before using this system.**

---

## 1. No guarantees of performance

**THIS IS NOT INVESTMENT ADVICE.**

Centaur-Apex Core is a software research system. Nothing in this repository,
in its documentation, in its tests, in its simulation harness (Chronos), or
in its publicly visible track record constitutes a recommendation, warranty,
or guarantee that using this system will produce profit or avoid loss.

Past simulation results — including the 250-year Chronos integration test —
are **not indicative of future results.** Synthetic market data is generated
from statistical distributions that may not accurately represent real market
conditions, especially during tail events, liquidity crises, or unprecedented
regime changes.

---

## 2. Trading is speculative

All trading, including algorithmic and autonomous trading, carries substantial
risk of capital loss. The following risks are inherent and cannot be eliminated
by software:

- **Market risk:** Asset prices can move against a position at any time.
- **Liquidity risk:** Sufficient volume may not exist to exit a position at
  the expected price.
- **Execution risk:** Orders may be rejected, partially filled, or filled at
  significantly different prices than modeled.
- **Model risk:** Any quantitative model — no matter how sophisticated — can
  be wrong. A strategy that worked historically may fail in the future.
- **Infrastructure risk:** Network failures, API outages, or cybersecurity
  breaches can cause positions to be lost or liquidated at the wrong time.

---

## 3. Invariants are not guarantees

The 100-year invariants (I1–I8 in `AGENTS.md`) are risk-management controls.
They are **not** guarantees against loss.

- **I1 (Max drawdown ≥ 15%):** Liquidation occurs when this threshold is
  breached. Loss up to 15% of high-water-mark equity may occur *before*
  the liquidation triggers.
- **I2–I3 (Leverage and concentration limits):** These limit the size of
  new positions but do not prevent existing positions from losing value.
- **I4 (Numerical validity):** This prevents software bugs but does not
  prevent market-driven losses.
- **I6 (Fail-safe default → EmergencyHalt):** A halt is not equivalent to
  a profit-protecting exit. Being halted during a flash crash means the
  system is unable to act until it recovers.

---

## 4. Autonomous operation risks

This system is designed to operate autonomously for a minimum of 100 years
with zero human override (I7, I8). This means:

- If the system enters `EmergencyHalt`, only the cryptographic multi-sig
  governance layer can recover it. If the key quorum is lost, the system
  remains halted **permanently**.
- If a market regime occurs that the synthetic Chronos rig never modeled, the
  system's behavior is undefined. The system has been designed to default to
  safety, but safety here means liquidation — not profit preservation.
- The system's strategy is evolved by the Adaptive Cortex layer over time.
  The evolutionary path is unpredictable by design.

---

## 5. Simulation ≠ reality

The Chronos simulation harness (`simulation/`) generates synthetic market
conditions using statistical regime models (normal, flash crash, hyperinflation,
liquidity evaporation, sovereign default, ledger fork). These are research
tools, not proofs of real-world resilience.

Real markets exhibit:
- Adverse selection and latency arbitrage that synthetic models do not capture.
- Regulatory intervention, market halts, and forced liquidations.
- Counterparty failure and exchange insolvency.
- "Black swan" events that are, by definition, not in any finite simulation.

---

## 6. Regulatory compliance

Users of this system are solely responsible for compliance with all applicable
laws, regulations, and licensing requirements in their jurisdiction. Trading
financial instruments — whether directly or via algorithmic systems — may
require specific licenses (e.g., broker-dealer registration, investment
adviser registration) that the system does not provide.

---

## 7. No warranty

THE SOFTWARE IS PROVIDED "AS IS," WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.

IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT, OR
OTHERWISE, ARISING FROM, OUT OF, OR IN CONNECTION WITH THE SOFTWARE OR THE
USE OR OTHER DEALINGS IN THE SOFTWARE.