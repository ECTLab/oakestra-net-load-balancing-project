# HALO implementation guide for the networking project

These four documents specify HALO for this repository: cluster and root network-manager calculations, weight-table delivery, and edge WRR. They are an implementation plan. The proposed HALO classes, messages, and integration points have not been implemented.

## Baseline and scope

| Item | Baseline |
|---|---|
| Repository | `oakestra-net-load-balancing-project` |
| Inspected commit | `0f79dd9caf1b6bb944f985edd6d1911add0c37bc` |
| Review date | `2026-11-24` |
| Local method | Base cost function; no histogram blending or percentile objective |
| Root method | Normalize spare capacity after local reservation; common shares for all overflow sources |

The algorithm source is the proposed-method chapter in [local chapter3.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/chapter3.tex>). It includes the system model and four method files. Older checkouts outside `New Fork` do not define the integration points for this guide.

## Reading order

Cross-project links use the two repositories' `lb_develop` branches so they also work on GitHub. Thesis links are local-only references into the sibling `Dissertation` workspace; the LaTeX files are not included in either repository. GitHub readers can use the equations and example reproduced in [algorithm.md](algorithm.md), but need that separate workspace to open the thesis sources.

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

This delivery changes only the four existing Markdown documents. It adds no documentation files, executable implementation, simulation results, or guaranteed latency-reduction claim. Future implementation acceptance checks are listed in the [low-level plan](skeleton-implementation-low-level.md).
