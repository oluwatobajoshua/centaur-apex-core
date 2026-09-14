# AUTHORS

Centaur-Apex Core is a proprietary project. All rights reserved.

## Human authors (Genesis Codebase)

- **Oluwatoba Ogunsakin** — project founder; chief architect of the Genesis
  Codebase (Constitution, Cortex, Evolution, Mesh, Adapters, Compliance,
  Chronos, Gateway scaffolding).

## Authorship conventions for an autonomous project

From Genesis onward, the *system itself* writes code (per `AGENTS.md` §3), and
those artifacts are **system-generated, not human-authored**:

- `evolution/patches/*` and anything produced via the Evolution Sub-Agent,
  sandbox runner, or Discovery Agent is authored by **Centaur-Apex Core** —
  never attributed to a human, but tracked by patch ID (see
  `evolution/evolution/code_agent.py`).
- Bootstrap stubs marked `SYSTEM-OWNED STUB (S1/S2)` in the source are
  hand-authored **only** to prove interfaces; final responsibility transfers
  to the system.

For lineage/legal purposes: human authorship is recorded in the git
history (commits). System authorship is recorded by patch SHA + policy —
not by git author fields. Do not attribute system-written bytes to a human
committer.