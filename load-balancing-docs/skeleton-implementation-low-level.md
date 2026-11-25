# Low-level HALO plan for the networking project

This document maps the inspected code to proposed integration points. Linked files exist; new paths in backticks are proposals. The mathematics is defined in [algorithm.md](algorithm.md), not replaced by another objective here.

## Existing execution map

```text
server.register -> proxy.New -> Env.Resolver -> Proxy.SetResolver -> Listen
packet -> Datapath.outgoingProxy -> cache Lookup
       -> resolveRoute -> resolver table lookup -> cache Revalidate
       -> random destination -> cache Install

MQTT job update -> RefreshServiceTable -> responseParser
               -> ReplaceJobEntries -> generation increment
```

| Existing file | Verified behavior | HALO integration |
|---|---|---|
| [server/server.go](../node-net-manager/server/server.go) | Worker registration, MQTT initialization, proxy construction | Create selector/prober before packet loops start |
| [proxy/Datapath.go](../node-net-manager/proxy/Datapath.go) | `rand.IntN` selection in `resolveRoute` | Invoke HALO only for its policy; return `ok=false` when no destination can be selected |
| [proxy/ProxyTunnel.go](../node-net-manager/proxy/ProxyTunnel.go) | Owns I/O and Datapath instance | Pass the selector reference; keep optimization outside packet loops |
| [resolver/ServiceResolver.go](../node-net-manager/resolver/ServiceResolver.go) | Background resolution, installation, refresh | Validate policy versions before replacing tables |
| [resolver/tableQueryRequests.go](../node-net-manager/resolver/tableQueryRequests.go) | Converts responses into `TableEntry` | Copy policy and real destination/cluster identity; currently assigns `Cluster: 0` |
| [mqtt/Tablequery.go](../node-net-manager/mqtt/Tablequery.go) | `Sip` and `ServiceInstance` decoding | Add policy and cluster identity to the receive contract |
| [TableEntryCache/serviceTranslationTable.go](../node-net-manager/TableEntryCache/serviceTranslationTable.go) | Three indexes, table generation, job replacement | Carry immutable policy data and preserve atomic job replacement |
| [mqtt/MqttJobUpdates.go](../node-net-manager/mqtt/MqttJobUpdates.go) | Update notification and `RefreshServiceTable` | Preserve the existing refresh path; extend its response |
| [mqtt/MqttMainClient.go](../node-net-manager/mqtt/MqttMainClient.go) | Publisher adds `nodes/<id>/net/` prefix | Publish probes; handle actual publication errors/timeouts |
| [model/NetManager.go](../node-net-manager/model/NetManager.go) and [config/netcfg.json](../node-net-manager/config/netcfg.json) | NetManager configuration type/file | Add optional HALO probe/freshness settings without changing existing settings |

The current publisher ultimately returns `nil` and does not consistently expose timeout as an error. HALO must not infer guaranteed delivery from that return value. Message identity, duplicate detection, and stale-data rejection remain necessary.

## Proposed new files

| Repository-relative path | Required content |
|---|---|
| `node-net-manager/balancing/types.go` | `HALOPolicy`, `HALORow`, `HALODestination`, and source/destination identities |
| `node-net-manager/balancing/halo.go` | Go selector struct, policy installation, WRR state, cleanup, and explicit unavailable result |
| `node-net-manager/telemetry/ping.go` | Independent probing interval, aggregation, validity, and publishing; probe-report types can stay here |
| `cluster-service-manager/service-manager/algorithms/halo_cluster.py` | Cluster class, input types, per-service state, and solver outputs |
| `root-service-manager/service-manager/algorithms/halo_root.py` | Root class, summaries, shares, and decision states |
| `cluster-service-manager/service-manager/algorithms/__init__.py` | Python package marker |
| `root-service-manager/service-manager/algorithms/__init__.py` | Python package marker |

Suggested cluster methods are `on_report`, `compute_local`, `on_root_decision`, and `build_policy`; the root can expose `compute_shares`. These are proposed names, not existing interfaces. Inject transport/storage callbacks and keep numerical calculations separate from I/O.

The Go selector's `Pick` result should explicitly indicate whether selection succeeded. There is no need to reproduce an older fork's index-only interface limitation. This checkout has no algorithm registry or fixed algorithm-count test to update.

Add future implementation tests beside their classes. Proposed test files are not production files. Keep the four existing English Markdown guides. The requested `latex-reference` directory is a reference snapshot, not an additional implementation guide.

## Cluster-manager edits

| Existing file | Proposed change |
|---|---|
| [service_manager.py](../cluster-service-manager/service-manager/service_manager.py) | Import/create the class after Mongo and before MQTT; retain its instance; add decision-receive route |
| [interfaces/mqtt_client.py](../cluster-service-manager/service-manager/interfaces/mqtt_client.py) | Exact `net/halo/paths` dispatch; subscribe/dispatch `nodes/+/halo/telemetry`; submit without solving in callback |
| [interfaces/mongodb_requests.py](../cluster-service-manager/service-manager/interfaces/mongodb_requests.py) | Write complete versioned policy into the relevant RR service entry; preserve it through lifecycle refresh |
| [interfaces/root_service_manager_requests.py](../cluster-service-manager/service-manager/interfaces/root_service_manager_requests.py) | Send capacity summaries over existing root HTTP connectivity using registered cluster identity |
| [network/tablequery/resolution.py](../cluster-service-manager/service-manager/network/tablequery/resolution.py) | Carry policy in `service_ip`; return a compatible policy and destination snapshot |
| [operations/instances_management.py](../cluster-service-manager/service-manager/operations/instances_management.py) | Schedule recomputation on deployment/removal changes |

The MQTT client already subscribes to `nodes/+/net/#`, but no HALO producer/handler exists yet. NodeEngine's proposed message is outside that wildcard and requires its own subscription.

For an existing job, `mongo_update_job` refreshes instances rather than weights. Add an explicit policy-writing function and publish only after storage completes. `mongo_init` drops the jobs cache, so startup must rebuild policies from valid reports.

After writing, invoke existing `mqtt_notify_service_change(job_name)`. Do not signal a fake deployment through `/api/net/job/update` just to announce weights. A source cluster's locally computed policy must not be overwritten by a root's general job snapshot or another cluster's cache.

## Root-manager edits

| Existing file | Proposed change |
|---|---|
| [service_manager.py](../root-service-manager/service-manager/service_manager.py) | Create class after Mongo and before WSGI; receive summaries |
| [interfaces/clusters_interface.py](../root-service-manager/service-manager/interfaces/clusters_interface.py) | Push HALO decisions outside the receive callback/request path |
| [network/routes_interests.py](../root-service-manager/service-manager/network/routes_interests.py) | Reuse interested recipients, also covering reporting clusters that only originate traffic |
| [interfaces/mongodb_requests.py](../root-service-manager/service-manager/interfaces/mongodb_requests.py) | Reuse registered-cluster/instance mappings; persist active-version metadata alongside existing state only if needed |

Match cluster identity to registration. In [operations/instances_management.py](../root-service-manager/service-manager/operations/instances_management.py), `cluster_id` is a string; the numeric `TableEntry.Cluster` is not a reliable replacement. Preserve string cluster identity in HALO types and decoding.

## Shared window envelope

Field names below are proposed. The [core low-level plan](https://github.com/ECTLab/oakestra-load-balancing-project/blob/lb_develop/load-balancing-docs/skeleton-implementation-low-level.md) uses the same production contract. Wire reports contain window deltas; the receiver must not differentiate them again.

| Field | Meaning |
|---|---|
| `schema_version` | Wire-schema version, separate from publication sequence |
| `producer_id`, `producer_epoch`, `sequence` | Producer identity, execution epoch, increasing sequence within that epoch |
| `window_start`, `window_end` | UTC measurement boundaries for age/window identification |
| `duration_seconds` | Actual monotonic-clock window duration |
| `deployment_revision`, `cpu_allocation_revision` | Per-instance deployment and CPU-allocation identity |
| `validity`, `missing_reason` | Per-measurement validity and absence reason; missing is not measured zero |

Use wall-clock time for observation age and monotonic clocks for durations. Approximate clock synchronization does not make all machines' windows identical. Solve from the latest valid observations with explicit age; the capacity bound is a fixed-plan statement.

## NodeEngine input

The new `nodes/<worker>/halo/telemetry` message contains the shared envelope and separate `source_metrics` and `destination_metrics` arrays. One role's array may be empty: absence of a destination container does not imply absence of source demand.

| Record / field | Meaning and unit |
|---|---|
| Both: `service_key` | Complete unique service/job identity, not only a short service name |
| Source: `source_key` | Worker, or worker plus calling instance; not a TCP port |
| Source: `attempts_started`, `open_start`, `open_end` | Demand and boundary counts of open attempts |
| Source: `completed_succeeded`, `completed_failed` | Authoritative counts of all terminal outcomes, even when route identity is unknown |
| Source: `duration_sum_seconds`, `duration_count` | Whole-source completed-duration sum/count; separate from the optional per-path breakdown |
| Source: `unrouted_failed` | Diagnostic subset of `completed_failed` for failure before destination selection; never added again |
| Source: `outcomes[]` | Results identified by `cluster_id`, `instance_number`, `host_id`, and `deployment_revision` |
| Outcome: `succeeded`, `failed` | Completed successful/failed attempts on that path; failure includes configured timeout/application errors |
| Outcome: `duration_sum_seconds`, `duration_count` | Completed-duration sum/count for monitoring, not a substitute for ping |
| Destination: `instance_number`, `host_id` | Actual service instance and physical host |
| Destination: `cpu_allocated_cores`, `cpu_used_core_seconds` | Effective CPU allocation and whole-container window usage delta |
| Destination: `arrivals`, `processed` | All arrivals and actual processing completions, across every sender |
| Destination: `service_starts`, `queue_wait_sum_seconds` | Service-start cohort and its total enqueue-to-start wait |
| Destination: `queue_waiting_end`, `in_service_end` | Waiting and in-service request counts, separately |
| Destination: `ready`, `validity` | Application readiness and measurement validity; host reachability alone is not readiness |

Counts are nonnegative and times are seconds. `processed` includes unsuccessful processing that actually executed, but excludes pre-service rejection. An attempt completing in a later window is counted in that completion window. Started attempts are not the failure-ratio denominator.

Failures before a destination is selected still count in demand/outstanding-attempt accounting, but not in a fictitious instance's failures. `completed_succeeded` and `completed_failed` cover every terminal attempt. `unrouted_failed` is a diagnostic subset of `completed_failed`, not an additional completion. `outcomes[]` contains only known destinations.

The destination identity must represent the instance actually chosen after routing. A service VIP, DNS name, or user IP does not establish it. The observation provider must correlate the chosen route and attempt. Without that correlation, do not manufacture a new destination failure ratio; retain unavailable/unobserved status.

Opaque traffic cannot supply missing request counters automatically. A destination without valid processing counts cannot receive a new capacity estimate. Optional queue correction is different from a missing mandatory capacity input.

### Source totals when route attribution is incomplete

Use `open_end = open_start + attempts_started - completed_succeeded - completed_failed`. Do not substitute the sum of `outcomes[]` when its route coverage is incomplete. Require `sum(outcome.succeeded) <= completed_succeeded` and `sum(outcome.failed) + unrouted_failed <= completed_failed`.

With complete path coverage, both inequalities become equalities. The differences otherwise represent completed attempts without known route attribution. They do not become failures of a fictitious destination. `unrouted_failed` covers attempts that failed before selection; failed attempts with a selected but unobserved destination remain in the total and its unattributed difference.

Mark `path_outcomes` unavailable/invalid when the provider cannot establish complete outcome-to-route attribution. The cluster must not construct a fresh per-destination failure ratio from a biased partial breakdown. This does not erase valid source demand or whole-source completion counts.

For fully valid duration coverage, source `duration_count` equals `completed_succeeded + completed_failed`; divide the source sum by this count for the whole-source mean. A zero count produces no new mean. Duration validity is independent of whether those completions have destination attribution. The base cost still uses ping, not this response-duration mean.

## Probe input

The new `nodes/<worker>/net/halo/paths` message contains the shared envelope and `probes`. Each probe record carries destination `host_id`, a path-specific `source_key` when needed, probe type, valid sample count, RTT sum in seconds, last successful observation time, and validity.

Calculate the mean as sum divided by valid count, not an unweighted mean of unequal sample means. Instances sharing a host may share a probe result when the path is the same. Different network paths require different keys.

Proposed NetManager settings cover enablement, probe interval/type/timeout, and maximum observation age. Ping period remains independent of the request-report window. Failed probes do not contribute zero RTT to the successful-probe average.

## Root summary and decision contracts

| Proposed message | Contents |
|---|---|
| `POST /api/net/halo/capacity` | Cluster/service identity, `local_plan_ref`, version envelope, `overflow_rps`, and `instances[]` |
| Summary instance | Instance/host identity, deployment revision, readiness, capacity validity, and `spare_rps` |
| `POST /api/net/halo/decision` | Service, root epoch/sequence, `basis_reports`, validity deadline, `mode`, cluster and conditional-instance shares |
| `mode` | `no_overflow`, `normal`, `temporary_overload`, or `no_receiver` |
| Decision cluster | Cluster identity and `cluster_weight`; each instance has full identity and `conditional_weight` |

`spare_rps` is $S$ after local reservation and the safety margin. The root computes $A$ by summation; nominal host capacity and raw CPU are unnecessary. Publish $\pi$ and $v$ in the same decision, shared by all overflow sources.

`basis_reports` identifies the consumed summary versions. Versioning does not create instantaneous synchronization or a distributed transactional reservation. A decision that still lists the overflowing source cluster as a receiver, or refers to changed destinations, is incompatible; local deletion/renormalization is not allowed.

The summary HTTP response acknowledges acceptance, not delivery of a new decision to every interested cluster. Retry unsuccessful sends with the same message identity; do not add their counts twice.

## Final edge-policy contract

Add proposed `policy: "halo"` and `halo` fields to the RR entry of `service_ip_list[]`. Keep RR address type and IP allocation semantics; policy identifies the selector.

Read the policy attached to the address actually requested. A HALO policy on an RR VIP does not turn an instance-specific address or another policy's address into RR.

| Policy field | Meaning |
|---|---|
| `schema_version` | Wire-contract version; `1` for the examples below |
| `service_key`, `producer_id`, `producer_epoch`, `sequence` | Source manager's final-policy identity/version |
| `valid_until`, `local_plan_ref`, `root_decision_ref` | Validity and calculation references; root reference may be null for local-only policy |
| `rows[]` | All cluster rows or only that worker's rows; worker-specific delivery is smaller |
| Row: `source_key`, `state`, `destinations[]` | Independent WRR key, `ready`/`unavailable` state, and its destinations |
| Destination | `cluster_id`, `instance_number`, `host_id`, `deployment_revision`, and `weight` |

Weights are finite, nonnegative fractions. Each active row sums to one within an explicit tolerance. Go can use `float64` weights directly; integer percentages are not required. If integer execution is later needed, recheck zeros, sums, and rate limits after quantization.

Copy the policy through the complete path: cluster document -> `format_instance_response` -> `mqtt.Sip` -> `responseParser/toServiceIP` -> `TableEntryCache.ServiceIP` -> selector. A private struct alone does not deliver policy data over the network.

Map full destination identities to actual route entries; array position is not an identity. With no positive destination or no valid row, return unavailable. Random selection or selection of the first candidate is not a valid HALO fallback.

## Installation, concurrency, and events

1. Valid observations, readiness, deployment, or allocation changes mark the affected service for calculation. Coalesce reports into the next snapshot without adding duplicate windows.
2. Solve against fixed inputs, a fixed source order, and per-service reservations. Do not let two cycles mutate the same service plan concurrently.
3. If inputs change during a solve, do not publish its obsolete output as the latest decision. Schedule the next cycle without blocking MQTT reception.
4. Send the completed local summary upward and publish any usable local-only policy without waiting for the root. A root decision updates integration only.
5. Table responses must contain compatible policy/destination snapshots. Reject old or malformed policy and positive weights for missing destinations before `ReplaceJobEntries`; silently skipping those destinations is insufficient.
6. Install policy and version atomically. Reset row scores for a new policy version, but do not reset them again for a duplicate installation of that version.
7. Preserve `Revalidate` and established-flow caching. A weight change must not choose a new replica for the next packet of an existing connection.
8. After policy expiry, refresh or use a valid temporary policy. With no eligible destination, record routing failure rather than converting an invalid index to a default destination.

Replay goroutines can also call `resolveRoute`. Protect policy installation and per-row WRR scores against concurrent access. Solver locks and HTTP operations stay off the packet path; selection changes only the small state of its own row.

When `RemoveServiceEntries` removes a job, clean up selector/probe state too. Port-keyed source identities or retained deleted-service state would grow memory unnecessarily. Derive deterministic WRR ties from destination identity, not unpredictable response order.

An unseen source must not trigger division by zero demand. It needs a valid initial or prior policy; otherwise return explicit unavailable. Record baseline/probe warm-up separately from measured algorithm operation.

Activate HALO service policy only after valid observations or startup calibration exist. Do not present an unvalidated bootstrap distribution as part of the thesis solver. Until a valid row exists, unavailable is explicit.

The current `convertToInstanceIp` requires a registered source namespace. An external user does not automatically have one. The ingress gateway must enter selection through a registered source, or a separate request-layer integration; adding weights alone does not create a working ingress path.

## Configuration and deployment

Algorithm settings include $\varepsilon$, $P_s$, $\kappa_s$, solver tolerance, source order, maximum measurement age, and policy validity. Request windows and probe periods are independent. The thesis default window is `5s`; do not silently change the companion project's legacy resource cycle.

Manager classes retain the existing Dockerfile command. Build/deploy both manager images from this checkout; official `latest` does not imply HALO support. Go builds follow [go.mod](../node-net-manager/go.mod), which specifies `go 1.24.0`.

Install this checkout's NetManager binary. Image selection, root port, and NodeEngine publication belong to the [core low-level plan](https://github.com/ECTLab/oakestra-load-balancing-project/blob/lb_develop/load-balancing-docs/skeleton-implementation-low-level.md). Placement scheduling and runtime allocation code do not belong in this repository.

## Component call contracts

These method names are proposed interfaces, not existing code. Inputs are immutable snapshots. The numerical solver may be supplied by the implementer, but its result must satisfy the equations and optimality checks in [algorithm.md](algorithm.md).

| Component call | Input | Output and side effect boundary |
|---|---|---|
| Cluster `on_report` | Message kind, authenticated/registered producer identity, decoded window, receive time | Validate and replace that producer's latest window; mark affected services dirty. Never add a retransmitted delta twice. |
| Cluster `compute_local` | Service, eligible local instances, complete fresh source/path/container snapshot, fixed source order, settings | `LocalPlan`: source demand, `eta`, local rates/weights, per-instance planned and spare rates, overflow, input references, and a new `local_plan_ref`. No network calls. |
| Cluster `on_root_decision` | Complete root decision and receive time | Retain only an accepted version, then schedule composition. Do not solve local rows again merely because the root replied. |
| Cluster `build_policy` | A local plan, optional compatible root decision, current time | Complete final policy or explicit unavailable rows. Perform the local-first gate and all normal/temporary branches before publication. |
| Root `compute_shares` | Latest complete valid summaries for one service, current time | Complete `RootDecision` with mode, common cluster/instance shares, and exact summary references. No raw telemetry or local-cost solve. |
| Edge `Install` | Complete policy and matching route snapshot | Validate once and atomically replace row state. A duplicate version is idempotent; a new installed version resets that row's WRR scores. |
| Edge `Pick` | Service/VIP, source key, current candidates, address family, current time | Destination identity/entry plus explicit success flag. No solver, HTTP, probe, or synchronous table query. |

`LocalPlan` is private cluster state, not another wire message. Keep its rates as full-precision values. Build each service plan from zero reservations, solve sources sequentially, and retain the plan's complete input references. Do not expose half-computed rows to the publisher.

The shared contract identifies telemetry by message kind plus producer identity, epoch, and sequence. NodeEngine telemetry and NetManager probes are separate streams even when both use the same worker ID. They must not overwrite each other's sequence state.

## Deterministic processing and failure rules

| Condition | Required action |
|---|---|
| Known source idle in a valid window | Require an explicit record with zero starts; an omitted record is not evidence of zero demand. |
| Mandatory source/container input missing or stale | Use a still-valid compatible snapshot if available; otherwise do not construct a normal plan from invented zero values. |
| Queue unavailable | Omit only the residual correction and preserve its unavailable flag. |
| Failure ratio has no new completed cohort | Apply the configured unobserved/previous-valid rule; do not divide by zero. |
| Source has no positive local rate | Skip its local solve; never divide by `ell=0`. |
| Solver result violates feasibility or certificate tolerance | Do not publish it. Retain a still-valid complete policy or use the defined eligible temporary/unavailable behavior. |
| No external overflow | Root mode is `no_overflow`; the empty external-share list is intentional. |
| Positive overflow and no receiver | Root mode is `no_receiver`; composition applies local fallback only if eligible local hosts exist. |
| New report expires without another arrival | Treat expiry as an input-change event and recompute affected services. A deadline timer must not wait indefinitely for the next message. |
| Installed destination disappears | Invalidate the affected decision, report/recompute through the owning manager, and do not silently renormalize foreign shares. |

Use an explicit stable source ordering, such as ordinal order of the already canonical `source_key`; record it with the configuration. Use full destination identity for deterministic destination ordering and ties. These order choices are implementation settings; the thesis requires a fixed order but does not prescribe a string format.

Specify separate tolerances for rate feasibility, row sums, and optimality residuals in experiment configuration. Do not treat one tolerance as a new load-balancing parameter. Comparisons, root branch selection, and any rounding must not silently authorize a material excess above normal capacity.

## Version-1 wire validation

The following examples and the field tables above define schema version `1`. Counts and sequences are nonnegative integers; booleans are not counts. Rates, durations, and weights are finite JSON numbers. CPU shares and measured window duration must be positive where marked valid. Reject NaN and Infinity rather than letting a language-specific JSON extension carry them.

Use these per-measurement validity values: `valid`, `unavailable`, `invalid`, and `unsupported`. Source validity keys include `requests`, `path_outcomes`, and `durations`; destination keys include `cpu`, `processing`, `queue`, and `readiness`. An unavailable group may contain null fields with a `missing_reason` entry. Never evaluate a formula using a null or invalid input.

`source_key` must uniquely and consistently identify the same logical origin within the owning cluster. `host_id` is a worker identity. Every instance belongs to the declared service and cluster; validate that binding against the known deployment inventory. Do not reinterpret array position or host IP as an instance ID.

For HTTP summary/decision endpoints, acknowledge a new accepted message with `202` and `{"status":"accepted"}`. An identical duplicate or an older recognized version can return `200` with `duplicate` or `ignored_stale`. Return `400` for malformed schema, `409` for the same message identity with different content or an unrecognized epoch transition, and `503` while the receiver is not initialized.

Message sequence orders only its own active producer epoch. Activation of a replacement epoch must be tied to the existing producer-registration/reconnect lifecycle and must retire the old epoch; do not accept an arbitrary different epoch as newer. Preserve or re-establish active-producer identity before accepting reports after manager restart. This is a transport adapter requirement, not a convexity theorem.

HTTP retries reuse exactly the same message identity and body. MQTT QoS1 retransmissions are idempotent. Replacing the body, input references, or validity deadline requires a new sequence. Return from receive callbacks after enqueueing; delivery of an acknowledgement does not mean all other managers already installed the decision.

### Complete capacity-summary example

This is cluster `b`'s report in the thesis example, with one destination of spare capacity `30`. Cluster `a` separately reports overflow `60`; cluster `c` separately reports spare total `48`. The root computes aggregates itself. Identifiers and timestamps illustrate the wire format.

```json
{
  "schema_version": 1,
  "producer_id": "cluster-b",
  "producer_epoch": "cluster-b-boot-1",
  "sequence": 10,
  "window_start": "2026-11-25T09:00:00Z",
  "window_end": "2026-11-25T09:00:05Z",
  "duration_seconds": 5,
  "cluster_id": "cluster-b",
  "service_key": "campus.default.parking.default",
  "local_plan_ref": "cluster-b-plan-7",
  "overflow_rps": 0,
  "instances": [
    {
      "instance_number": 3,
      "host_id": "worker-b1",
      "deployment_revision": "deployment-b1-1",
      "ready": true,
      "capacity_valid": true,
      "spare_rps": 30
    }
  ]
}
```

### Complete root-decision example

This decision combines the three separate summaries. Both cluster shares and conditional instance shares are supplied in one version.

```json
{
  "schema_version": 1,
  "producer_id": "root-network-manager",
  "producer_epoch": "root-boot-1",
  "sequence": 42,
  "service_key": "campus.default.parking.default",
  "valid_until": "2026-11-25T09:00:20Z",
  "mode": "normal",
  "basis_reports": [
    {
      "cluster_id": "cluster-a",
      "producer_epoch": "cluster-a-boot-1",
      "sequence": 10,
      "local_plan_ref": "cluster-a-plan-7"
    },
    {
      "cluster_id": "cluster-b",
      "producer_epoch": "cluster-b-boot-1",
      "sequence": 10,
      "local_plan_ref": "cluster-b-plan-7"
    },
    {
      "cluster_id": "cluster-c",
      "producer_epoch": "cluster-c-boot-1",
      "sequence": 10,
      "local_plan_ref": "cluster-c-plan-7"
    }
  ],
  "clusters": [
    {
      "cluster_id": "cluster-b",
      "cluster_weight": 0.38461538461538447,
      "instances": [
        {
          "instance_number": 3,
          "host_id": "worker-b1",
          "deployment_revision": "deployment-b1-1",
          "conditional_weight": 1.0
        }
      ]
    },
    {
      "cluster_id": "cluster-c",
      "cluster_weight": 0.6153846153846152,
      "instances": [
        {
          "instance_number": 4,
          "host_id": "worker-c1",
          "deployment_revision": "deployment-c1-1",
          "conditional_weight": 0.6457510335432812
        },
        {
          "instance_number": 5,
          "host_id": "worker-c2",
          "deployment_revision": "deployment-c2-1",
          "conditional_weight": 0.3542489664567192
        }
      ]
    }
  ]
}
```

For `no_overflow` or `no_receiver`, `clusters` is empty and the mode determines its meaning. In temporary overload, the same fields carry the temporary shares from the corresponding equations; do not interpret them as a normal-capacity guarantee.

### Complete final-policy example

This is the `halo` object attached to the source cluster's RR entry. It contains only source `A1`'s row here; other source rows are separate. Full precision is retained.

```json
{
  "schema_version": 1,
  "service_key": "campus.default.parking.default",
  "producer_id": "cluster-a",
  "producer_epoch": "cluster-a-boot-1",
  "sequence": 11,
  "valid_until": "2026-11-25T09:00:20Z",
  "local_plan_ref": "cluster-a-plan-7",
  "root_decision_ref": {
    "producer_id": "root-network-manager",
    "producer_epoch": "root-boot-1",
    "sequence": 42
  },
  "rows": [
    {
      "source_key": "worker-a1",
      "state": "ready",
      "destinations": [
        {
          "cluster_id": "cluster-a",
          "instance_number": 1,
          "host_id": "worker-a1",
          "deployment_revision": "deployment-a1-1",
          "weight": 0.44530116643408263
        },
        {
          "cluster_id": "cluster-a",
          "instance_number": 2,
          "host_id": "worker-a2",
          "deployment_revision": "deployment-a2-1",
          "weight": 0.26058118650709383
        },
        {
          "cluster_id": "cluster-b",
          "instance_number": 3,
          "host_id": "worker-b1",
          "deployment_revision": "deployment-b1-1",
          "weight": 0.1131221719457013
        },
        {
          "cluster_id": "cluster-c",
          "instance_number": 4,
          "host_id": "worker-c1",
          "deployment_revision": "deployment-c1-1",
          "weight": 0.11687801512095582
        },
        {
          "cluster_id": "cluster-c",
          "instance_number": 5,
          "host_id": "worker-c2",
          "deployment_revision": "deployment-c2-1",
          "weight": 0.06411745999216634
        }
      ]
    }
  ]
}
```

A `ready` row must have at least one eligible positive destination and a unit sum within tolerance. An explicit `unavailable` row has an empty `destinations` list and makes `Pick` fail; it is not a malformed zero-sum ready row. A missing source row also fails closed.

Validate identities against the matching route snapshot before installation. In this example, the local total is `12/17`, the foreign total is `5/17`, and the complete row sums to one. Publish another row for a different source rather than reusing this row merely because the service is the same.

## Required implementation acceptance checks

| Area | Expected result |
|---|---|
| Capacity | Matching CPU/completion windows; zero/reset handling; allocation changes; all senders counted; explicit missing data |
| Queue/failure | Total arrival rate; waiting separate from in-service; completed-outcome denominator; timeout/retry semantics |
| Incomplete attribution | Whole-source completions reconcile even with partial `outcomes`; invalid path coverage does not create a fresh failure ratio. |
| Local solve | Correct derivatives and boundary conditions, rate sum, shared limits, source-order effects, full-precision thesis replay |
| Normal root | Multiple overflow sources; combined foreign rate per instance within $S$; overflowing clusters excluded as receivers |
| Temporary root | $O>V$, $V=0$ with receivers, co-located instances, and no receiver |
| Integration | $D=0$, $D=K$, $K=0$; root only for overflow; matching share versions; incompatible decisions rejected |
| Policy transport | Every copy step, string cluster IDs, same-numbered instances across clusters, partial responses, removed destinations |
| WRR | Independent rows, zero never selected, deterministic ties, new-version reset, duplicate-version preservation |
| Datapath | Existing flows retained, new flows use new weights, non-HALO behavior preserved |
| Events | Reordered/duplicate reports, restart, stale data, root failure, and MQTT interruption |
| Ingress | Direct entry into each cluster actually reaches selection; static port mapping is not reported as WRR |
| Execution unit | Flow shares distinguished from request shares under keep-alive and multiplexing |

Existing [routeRefresh](../node-net-manager/proxy/routeRefresh_test.go), [flowCacheFastPath](../node-net-manager/proxy/flowCacheFastPath_test.go), [resolver](../node-net-manager/resolver/resolve_test.go), and [table](../node-net-manager/TableEntryCache/Table_test.go) tests are regression points. Future HALO class tests are also required; these documents do not claim they have run.

Latency reduction requires separate empirical evaluation. Row convexity, fixed-plan capacity compliance, and user-visible latency are distinct claims.

## Exact LaTeX references

Section names below are English translations of the bundled headings. Labels are exact identifiers; source-line links identify the corresponding section in this snapshot. A parent section label is used where a subsection has no separate label. Wire formats, class paths, and startup adapters are repository-specific engineering choices.

| Subject in this document | Exact bundled section | Source labels |
|---|---|---|
| Input counters and path observations | [Demand, capacity, and observed load](latex-reference/system-model.tex#L33) (system-model.tex:33) | `eq:source-demand` |
| Input counters and path observations | [Path, failure, and queue observations](latex-reference/system-model.tex#L53) (system-model.tex:53) | `eq:ping-mean`, `eq:failure-observation` |
| CPU input contract | [Linear capacity estimation from CPU consumption](latex-reference/method-cluster.tex#L8) (method-cluster.tex:8) | `eq:container-utilization`, `eq:cpu-linear-capacity` |
| Destination and queue input contract | [Request counts from all sources](latex-reference/method-cluster.tex#L33) (method-cluster.tex:33) | `eq:all-source-observation` |
| Destination and queue input contract | [Fixed path cost and container queue observation](latex-reference/method-cluster.tex#L92) (method-cluster.tex:92) | `eq:queue-measurement`, `eq:queue-residual` |
| Solver acceptance conditions | [Lagrange solution and equation system](latex-reference/method-cluster.tex#L224) (method-cluster.tex:224) | `eq:optimality-conditions`, `eq:final-weights` |
| Capacity-summary contract | [Reporting spare capacity of each instance](latex-reference/method-root.tex#L6) (method-root.tex:6) | `tab:root-message`, `eq:root-available` |
| Root decision normal/temporary modes | [Shares of receiving clusters](latex-reference/method-root.tex#L36) (method-root.tex:36) | `eq:receiver-set`, `eq:root-normal-weights` |
| Root decision normal/temporary modes | [Insufficient receiver capacity](latex-reference/method-root.tex#L80) (method-root.tex:80) | `eq:root-temporary-instance` |
| Compatible policy composition | [Constructing the final table for each source](latex-reference/method-integration.tex#L43) (method-integration.tex:43) | `eq:integrated-final`, `eq:final-normalization` |
| WRR and versioned installation | [WRR and event-driven updates](latex-reference/method-integration.tex#L96) (method-integration.tex:96) | `eq:wrr` |
