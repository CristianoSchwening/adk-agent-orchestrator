# J-space agent monitoring

This directory contains the versioned contract and runtime traces for the
structured operational state exteriorized by orchestrator agents.

## Layout

- `schema/jspace-state-v1.schema.json`: machine-readable contract.
- `examples/jspace-state-v1.example.json`: representative valid snapshot.
- `traces/<session>/<agent>/<sequence>-<phase>.json`: immutable snapshots.
- `traces/<session>/manifest.json`: per-session trace index.

Runtime files intentionally remain eligible for Git versioning because this is
an educational repository. Review generated traces before committing them.

## Capture boundary

Snapshots may include complete user prompts, agent instructions, session
context, model messages, and tool results. The `jspace` object contains explicit
structured deliberation: plans, assumptions, hypotheses, evidence, decisions,
uncertainties, criticism, blockers, and next actions.

The monitor does not claim to capture private hidden chain-of-thought. The
integrity marker records this boundary explicitly.

## Enforcement

Agents must append exactly one `<jspace_metadata>...</jspace_metadata>` JSON
block to model responses. In `strict` mode, missing or invalid metadata raises a
`JSpaceValidationError`. In `audit` mode, execution continues and an immutable
`violation` snapshot is written.

Filesystem writes are atomic, paths are sanitized, snapshots have a configured
size limit, and the trace root must resolve inside the repository.
