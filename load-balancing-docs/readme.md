# HALO implementation guide for the networking project

These four documents specify HALO for this repository: cluster and root network-manager calculations, weight-table delivery, and edge WRR. They are an implementation plan. The proposed HALO classes, messages, and integration points have not been implemented.

## Baseline and scope

| Item | Baseline |
|---|---|
| Repository | `oakestra-net-load-balancing-project` |
| Inspected commit | `0f79dd9caf1b6bb944f985edd6d1911add0c37bc` |
| Review date | `2026-11-25` |
| Local method | Base cost function; no histogram blending or percentile objective |
| Root method | Normalize spare capacity after local reservation; common shares for all overflow sources |

The algorithm source is the proposed-method chapter in [chapter3.tex](latex-reference/chapter3.tex). It includes the system model and four method files. Older checkouts outside `New Fork` do not define the integration points for this guide.

## Reading order

Cross-project links identify only the shared interface or the other repository's ownership. The latest LaTeX sources, required figures, matching PDF, and integrity manifest are now bundled in [latex-reference](latex-reference/README.txt). Source links stay inside this repository; a separate Dissertation checkout is no longer required. The reference tables use English translations of section headings, exact LaTeX labels, and source-line links.

Reference entry points: [LaTeX master](latex-reference/AUTthesis.tex), [matching PDF](latex-reference/AUTthesis.pdf), and [source-integrity manifest](latex-reference/source-manifest.json).

| Existing document | Purpose |
|---|---|
| [algorithm.md](algorithm.md) | Symbols, observations, local optimization, root shares, integration, overload, and reference example |
| [skeleton-implementation-high-level.md](skeleton-implementation-high-level.md) | Component ownership, message flow, and class startup |
| [skeleton-implementation-low-level.md](skeleton-implementation-low-level.md) | Existing files, proposed files, wire contracts, and acceptance checks |

## What this checkout actually provides

Destination selection in [Datapath.resolveRoute](../node-net-manager/proxy/Datapath.go) currently uses `rand.IntN`. Despite the adjacent comment, this is random selection, not WRR. This checkout has no `balancing` package, `Algorithm` interface, `Register` registry, `report.go` reporter, or `l3-operator`.

Adding the name `halo` alone will not activate the algorithm. A selector and its small `resolveRoute` integration must be added. The cluster and root calculations also require their own Python classes, hosted by the existing service-manager processes.

## Responsibility boundary

```text
Companion core repository:
  NodeEngine -> container/request observations -> cluster network manager
This networking repository:
  NetManager -> path probes -> cluster network manager
  cluster network manager <-> root network manager
  final source rows -> NetManager WRR -> destination instance
```

This repository owns weights, path probing, and network forwarding. The core repository owns container resource measurements, CPU allocation, request-observation integration, and deployment. See the [core guide](https://github.com/ECTLab/oakestra-load-balancing-project/blob/lb_develop/load-balancing-docs/readme.md) and its [telemetry production contract](https://github.com/ECTLab/oakestra-load-balancing-project/blob/lb_develop/load-balancing-docs/skeleton-implementation-low-level.md).

The network cluster manager is not the core `cluster_manager`. The local HALO solver belongs in this repository's `cluster-service-manager`. Likewise, `root-service-manager` is distinct from the core `system_manager`.

## Execution limits that must remain explicit

The current datapath selects a destination for a new flow and preserves an established flow's destination while that route remains in the table. Native WRR integration therefore controls flow shares. It does not necessarily control HTTP request shares under keep-alive or multiplexing.

An experiment equivalent to the request-level model needs an independent selection opportunity for each attempt. One request per connection is the simplest test arrangement. Exact control over shared connections requires request-layer selection. Flow duration, packet count, and connection outcomes do not replace request duration, application failures, or service-queue measurements.

Users may enter any cluster directly. A static host-port mapping, however, does not automatically invoke WRR. The ingress path must lead to HALO selection. This checkout has no ready `ingress.go` or request-layer gateway; ingress integration is an explicit experimental prerequisite.

## Delivery boundary

This revision updates the four existing English guides and adds the requested `latex-reference` snapshot. No HALO runtime implementation or experimental result is added. The same reference copy is supplied to both repositories for citation; each guide still specifies only its own implementation and the shared boundary contracts.

## Self-contained implementation boundary

An implementer can write this repository's cluster/root classes, policy transport, and WRR from these guides without reading the thesis. The low-level plan defines method inputs/outputs, complete message examples, validation, and lifecycle rules; the algorithm document defines every equation and branch. The LaTeX copy provides provenance, not a substitute for missing specification.

A live deployment still requires the external telemetry producer to satisfy the documented contract, an explicitly chosen request/ingress observation integration, and experiment-specific settings. Those integrations are not already present, and no universal request counter is claimed for opaque traffic. The numerical solver is deliberately unrestricted, as in the thesis.

## Exact LaTeX references

Section names below are English translations of the bundled headings. Labels are exact identifiers; source-line links identify the corresponding section in this snapshot. A parent section label is used where a subsection has no separate label. Wire formats, class paths, and startup adapters are repository-specific engineering choices.

| Subject in this document | Exact bundled section | Source labels |
|---|---|---|
| System and data ownership | [System model](latex-reference/system-model.tex#L1) (system-model.tex:1) | `sec:system-model` |
| Local manager scope | [Local weights in the cluster manager](latex-reference/method-cluster.tex#L1) (method-cluster.tex:1) | `sec:cluster-manager` |
| Root manager scope | [Root shares for external clusters and instances](latex-reference/method-root.tex#L1) (method-root.tex:1) | `sec:root` |
| Integration and forwarding | [Combining weights and executing at the edge](latex-reference/method-integration.tex#L1) (method-integration.tex:1) | `sec:integration` |
| Unified reference example | [Unified campus example](latex-reference/method-example.tex#L1) (method-example.tex:1) | `sec:unified-example` |
