// SSE event schema v2 parser (002-dsa-hub-pinnacle).
//
// v2 is additive over v1. The wire envelope adds a `v: 2` field plus 11
// new event kinds for the provisioning DAG (`agent.started`,
// `agent.progress`, `agent.completed`, `agent.failed`, `kpi.tick`,
// `artifact.produced`, `validation.started`, `validation.result`,
// `run.completed`, `run.needs_replan`, `heartbeat`).
//
// This stub re-exports the v1 parser API so consumers can import from `v2`
// without breaking; the full v2 event types and dispatcher land in tasks
// T078 + T087 (US3) when the provisioning event stream is wired.
//
// See specs/002-dsa-hub-pinnacle/contracts/provision.openapi.yaml for the
// authoritative event schema.

export * from "../v1";
