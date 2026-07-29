# Verbalized workspace monitoring

This directory contains the versioned contract and runtime traces for the
structured operational state explicitly verbalized by orchestrator agents.

## Layout

- `schema/verbalized-workspace-v1.schema.json`: machine-readable contract.
- `examples/verbalized-workspace-v1.example.json`: representative valid snapshot.
- `traces/<session>/<agent>/<sequence>-<phase>.json`: immutable snapshots.
- `traces/<session>/manifest.json`: per-session trace index.

Runtime files intentionally remain eligible for Git versioning because this is
an educational repository. Review generated traces before committing them.

## Capture boundary

Snapshots may include complete user prompts, agent instructions, session
context, model messages, and tool results. The `workspace` object contains explicit
structured deliberation: plans, assumptions, hypotheses, evidence, decisions,
uncertainties, criticism, blockers, and next actions.

This is a behavioral proxy inspired by verbal-report properties discussed in
[J-space research](https://transformer-circuits.pub/2026/workspace/). It does
not extract residual-stream activations, Jacobians, J-lens vectors, private
hidden chain-of-thought, or the mechanistic J-space.

## Enforcement

Agents use ADK `output_schema` to return one complete `{workspace, result}` JSON
object. The runtime validates the entire object before exposing `result`. In
`strict` mode, missing or invalid output raises `WorkspaceValidationError`. In
`audit` mode, execution continues and an immutable `violation` snapshot is written.

The design deliberately does not use client-reported confidence as calibrated
correctness probability, does not act on partial JSON, and does not depend on
stream cancellation for correctness or performance claims.

Filesystem writes are atomic, paths are sanitized, snapshots have a configured
size limit, and the trace root must resolve inside the repository.
