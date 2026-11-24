# HALO algorithm: networking-project responsibilities

This document specifies the cluster network manager, root network manager, and edge selector. The [high-level plan](skeleton-implementation-high-level.md) maps their execution, and the [low-level plan](skeleton-implementation-low-level.md) maps existing code and proposed contracts. This version uses only the base cost method.

## Sources and calculation order

| Local-only thesis source | Covered details |
|---|---|
| [local system-model.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/system-model.tex>) | Data boundaries, identities, observations, and counters |
| [local method-cluster.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/method-cluster.tex>) | Linear capacity, queue correction, cost, convexity, Lagrange conditions, and parameter effects |
| [local method-root.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/method-root.tex>) | Spare capacity, cluster/instance shares, and insufficient capacity |
| [local method-integration.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/method-integration.tex>) | Local-first gate, integration, temporary behavior, and WRR |
| [local method-example.tex](<../../../../Dissertation/HALO/latex/قالب پایان نامه امیرکبیر/Latex template 2018/method-example.tex>) | Six-source, five-destination worked example |

The calculation and execution sequence is:

```text
Valid window -> container capacities -> local gate
             -> local rows in fixed source order -> spare capacities
             -> root external shares -> final source rows -> edge WRR
```

## System model and symbols

Each edge belongs to one cluster. Users may enter any cluster directly. Data travels directly from the source edge to the chosen instance; neither manager is a mandatory request relay. A cluster manager may run on an edge server. Control resources must be excluded before assigning container CPU shares.

| Symbol | Meaning and unit |
|---|---|
| $a,b$ | Source and destination clusters |
| $e,s,i,h(i)$ | Source, service, destination instance, and instance's physical host |
| $\mathcal E_a$ | Sources in cluster $a$; if callers need separate policies, $e$ denotes edge plus calling instance |
| $\mathcal A_{as}$ | Authorized, healthy, ready instances with valid, positive, finite capacity estimates |
| $\mathcal H_{as}$ | Distinct physical hosts of those instances |
| $\Delta$ | Configurable observation window; default `5s` |
| $D_{es},D_{as}$ | Source demand and total locally originated cluster demand, requests/s |
| $g_{si},T^{CPU}_{si},N^{proc}_{si}$ | Allocated cores, window CPU consumption in core-seconds, and completed processing count |
| $\mu_{si},U_{si}$ | Estimated capacity and margin-adjusted limit, requests/s |
| $r_{esi},w_{esi},W_{esbi}$ | Local assigned rate, conditional local weight, and final weight |

The root receives instance identities and capacity summaries. Raw CPU, queues, and source-path observations remain within the owning cluster. Resource data is not exchanged directly between cluster managers. Cluster plus instance identifies a destination; an instance number alone is insufficient as a general HALO key.

The local feasibility argument assumes a common eligible destination set for sources in a cluster. If access restrictions produce different sets, this version's argument no longer suffices. Independently deleting destinations and renormalizing weights does not replace a new constrained solution.

## Demand and observation semantics

Each source attempt is counted once in $A^{src}_{es}$. A retry is a new attempt, while the original application-request identity remains distinguishable:

$$D_{es}=A^{src}_{es}/\Delta,\qquad D_{as}=\sum_{e\in\mathcal E_a}D_{es}.$$

Arrival of that attempt at its destination does not create another source demand. A call to another service creates demand for that service. Destination processing counts include local and foreign senders:

$$N^{proc}_{si}=\sum_qN^{proc}_{qsi},\quad N^{in}_{si}=\sum_qN^{in}_{qsi},\quad \lambda^{obs}_{si}=N^{in}_{si}/\Delta.$$

Do not add sender totals to an already complete destination counter. Completed successful and unsuccessful processing belongs in $N^{proc}$; rejection before execution does not. Arrival, service start, and processing completion are different events.

| Observation | Definition |
|---|---|
| Attempt duration | Monotonic time at the source, from attempt start to success, error, or timeout; unfinished attempts are excluded from completed-duration averages |
| Ping RTT | $\bar d^{net}_{ei}=\sum_gd_{ei,g}/n_{ei}$ over valid probes; its interval is independent of $\Delta$ |
| Failure ratio | $\hat f_{esi}=F_{esi}/(C_{esi}+F_{esi})$ over outcomes completed in that window on that path |
| Open-attempt accounting | $O(t_{k+1})=O(t_k)+A_k-C_k-F_k$ |
| Queue | Waiting requests separately from requests in service; enqueue-to-start duration measured at the destination |

With no completed outcomes, do not manufacture a new failure ratio. Retain the last valid value and its age, or a configured initial value marked unobserved. Missing ping is not zero: a valid initial probe or still-valid prior observation is required. The API response does not need an internal processing-time field.

## Linear capacity of each container

CPU usage and completed processing must refer to the same window and container configuration:

$$\bar c_{si}=T^{CPU}_{si}/\Delta,\quad u_{si}=\bar c_{si}/g_{si},\quad y_{si}=N^{proc}_{si}/\Delta.$$

$$\gamma_{si}=N^{proc}_{si}/T^{CPU}_{si},\qquad \mu_{si}=\gamma_{si}g_{si}=y_{si}/u_{si},\qquad U_{si}=(1-\varepsilon)\mu_{si},\quad 0<\varepsilon<1.$$

If a reported percentage is relative to the container's allocation, $u=p/100$. A host-normalized CPU percentage has a different meaning. Capacity belongs to the destination service container. Sender CPU and background loads from other services do not enter this model.

Do not divide when processing data is invalid or $T^{CPU}=0$. Use a valid previous estimate for the same configuration or a startup measurement; otherwise exclude the instance from normal capacity. A new allocation, deployment, or counter epoch must not silently reuse an incompatible estimate.

This estimate assumes a reasonably stable request mix, CPU-dependent processing, and a reliably supplied CPU share. It is not a guaranteed maximum. Observed old load is not subtracted from $\mu$: the solve constructs a replacement plan.

## Local-first admission gate

$$K_{as}=\sum_{i\in\mathcal A_{as}}U_{si},\qquad
\eta_{as}=\begin{cases}1&D_{as}=0\ \text{or}\ D_{as}\le K_{as},\\K_{as}/D_{as}&D_{as}>K_{as}.\end{cases}$$

$$\ell_{es}=\eta_{as}D_{es},\quad z_{es}=(1-\eta_{as})D_{es},\quad \rho_{as}=\sum_ez_{es}=\max(0,D_{as}-K_{as}).$$

Equality with the local limit does not activate external routing. With positive demand and no local instance, $\eta=0$. Incoming foreign traffic is not added to $D_{as}$. All sources share $\eta$, but each source's local destination weights are calculated separately.

## Fixed path cost and queue correction

$$d^{fix}_{esi}=\bar d^{net}_{ei}+P_s\hat f_{esi}+\delta^Q_{si},\qquad P_s\ge0.$$

All time values are seconds. $P_s$ is the configurable failure penalty. Where queue instrumentation exists, use the cohort of service starts:

$$\bar W^Q_{si}=\frac{\sum_j(t_j^{start}-t_j^{enqueue})}{n^{start}_{si}},\quad n^{start}_{si}>0.$$

$$\lambda^{ref}_{si}=\min(\lambda^{obs}_{si},U_{si}),\quad W^{Q,ref}_{si}=\frac{\lambda^{ref}_{si}}{\mu_{si}(\mu_{si}-\lambda^{ref}_{si})},\quad \delta^Q_{si}=\max(0,\bar W^Q_{si}-W^{Q,ref}_{si}).$$

The $M/M/1$ reference is approximate for a multithreaded container. The residual $\delta^Q$ stays fixed during the solve. Without instrumentation or a valid start cohort, omit this correction and preserve an unavailable flag. This is not a measured zero queue. Request duration minus ping is not an exact queue measurement.

## Local optimization and shared destination limits

Initialize $R^{plan}_{si}=0$ separately for every service. Process its sources in a fixed, recorded order:

$$R^{max}_{esi}=\max(0,U_{si}-R^{plan}_{si}),\quad \mathcal I_{es}=\{i:R^{max}_{esi}>0\}.$$

For $\ell_{es}>0$, require $\sum_iw_{esi}=1$, $w_{esi}\ge0$, and $r_{esi}=\ell_{es}w_{esi}$. The rate domain is $0\le r_{esi}\le R^{max}_{esi}<\mu_{si}$. The denominator is therefore at least $\varepsilon\mu_{si}>0$. Skip zero-rate rows.

With a shared destination set and the local admission gate, every row remains feasible:

$$\sum_iR^{max}_{esi}=K_{as}-\sum_{q\prec e}\ell_{qs}\ge\ell_{es}.$$

The base route cost and weighted objective are exactly:

$$C^{route}_{esi}(r)=\frac{\kappa_sr}{\mu_{si}-r}+d^{fix}_{esi}r,\quad\kappa_s>0,\qquad \min_{\mathbf w}\sum_iw_{esi}C^{route}_{esi}(\ell_{es}w_{esi}).$$

$C^{route}$ is a cost index, not an individual request's exact response time. Substituting $r=\ell w$ gives the following equivalent rate problem after dropping the constant positive factor $1/\ell_{es}$:

$$\Psi_{esi}(r)=\frac{\kappa_sr^2}{\mu_{si}-r}+d^{fix}_{esi}r^2,\qquad
\min_{\mathbf r}\Phi_{es}=\sum_i\Psi_{esi}(r_{esi}),\quad \sum_ir_{esi}=\ell_{es},\quad0\le r_{esi}\le R^{max}_{esi}.$$

The squared numerator follows from weighting and substitution. The denominator is not replaced by its square, and overload rates are not put into this optimization.

### Convexity and the Lagrange system

For fixed parameters and $d=d^{fix}\ge0$:

$$\Psi'(r)=\frac{\kappa r(2\mu-r)}{(\mu-r)^2}+2dr,\quad
\Psi''(r)=\frac{2\kappa\mu^2}{(\mu-r)^3}+2d>0,\quad
\Psi'''(r)=\frac{6\kappa\mu^2}{(\mu-r)^4}>0.$$

A positive second derivative proves strict convexity; a positive third derivative proves that the second derivative increases strictly. The summed objective is strictly convex and the constraints are linear. A nonempty, closed, bounded feasible set has a unique minimizing rate vector for this row.

The weight-space Lagrangian and its rate-space relation are:

$$\mathcal L(\mathbf w,\lambda)=\sum_i\left[\frac{\kappa_s\ell_{es}w_{esi}^2}{\mu_{si}-\ell_{es}w_{esi}}+d^{fix}_{esi}\ell_{es}w_{esi}^2\right]+\lambda\left(\sum_iw_{esi}-1\right).$$

$$\ell_{es}\mathcal L(\mathbf r/\ell_{es},\lambda)=\Phi_{es}(\mathbf r)+\lambda(\sum_ir_{esi}-\ell_{es}).$$

Writing $M_i(r)=\Psi'_i(r)$, an interior solution satisfies the following $n+1$ equations for the $n$ rates and multiplier:

$$M_1(r_1)=\cdots=M_n(r_n)=-\lambda=\nu,\qquad r_1+\cdots+r_n=\ell_{es}.$$

For boundary solutions, use the constrained optimality conditions:

$$M_i(r_i)\begin{cases}\ge\nu&r_i=0,\\=\nu&0<r_i<R_i^{max},\\\le\nu&r_i=R_i^{max}.\end{cases}$$

The rate constraints also apply. Exclude zero-cap destinations. If demand equals the sum of limits, every rate equals its limit; the multiplier need not be unique. The numerical method is unrestricted. Validate its output against the sum constraint, limits, and these conditions with explicit tolerances.

After a row, set $w^*_{esi}=r^*_{esi}/\ell_{es}$ and $R^{plan}_{si}\gets R^{plan}_{si}+r^*_{esi}$. The next source uses the remaining limit for the same service. Start a different service's reservation from zero; sequential coupling between different services has been removed.

Convexity applies to an individual row with fixed inputs. The overall method is a heuristic with a fixed source order, not a proven joint optimum over all sources or an exact model of their aggregate queue.

### Parameter effects

| Change, with the other relevant inputs and limits fixed | Effect |
|---|---|
| Higher ping, failure with $P_s>0$, or queue residual | The same destination's weight decreases or stays unchanged |
| Higher $\mu$, with an expanded limit and unchanged fixed cost | More assignment becomes possible; that destination's weight does not decrease |
| Higher $R^{max}$ | Matters when the limit is active; a small change to an inactive limit has no effect |
| Higher allocated $g$ with fixed $\gamma$ | Higher linear capacity, provided the allocation is actually supplied |
| Higher $N^{proc}$ with fixed $T^{CPU},g$ | Higher estimated capacity |
| Higher $T^{CPU}$ with fixed $N^{proc},g$ | Lower estimated capacity |
| Higher local rate $\ell$ with fixed limits | Assigned destination rates do not decrease; individual relative weights have no universal direction |
| Higher $\varepsilon$ | Lower normal limits and local admission; individual weight effects depend on active limits |
| Higher $P_s$ | More importance for failures; all path failure ratios affect the resulting weights |
| Higher $\kappa_s$ | More importance for the fractional cost; individual weight directions are not universal |
| Longer $\Delta$ | Changes freshness and noise; adds no independent multiplier to $N^{proc}/T^{CPU}$ |

CPU consumption and processing throughput are not independent. If both increase proportionally, the estimated capacity stays unchanged.

## Root allocation to external clusters and instances

The cluster reports spare capacity after local reservation:

$$S_{bsi}=\max(0,U_{si}-R^{plan}_{si}),\quad A_{bs}=\sum_iS_{bsi},\quad
\mathcal R_s=\{b:\mathcal A_{bs}\ne\varnothing,\rho_{bs}=0\}.$$

$$O_s=\sum_a\rho_{as},\qquad V_s=\sum_{b\in\mathcal R_s}A_{bs}.$$

Do not deduct the safety margin twice. The root replaces the external plan, so previous external allocations are not subtracted from $S$ again. A cluster with local overflow is not a receiver for that service. Root shares are common to all overflow sources; this method uses neither inter-cluster ping nor raw CPU at the root.

When $O_s=0$, no external distribution is needed. For $0<O_s\le V_s$:

$$\pi_{sb}=A_{bs}/V_s,\quad v_{sbi}=S_{bsi}/A_{bs},\quad \pi_{sb}v_{sbi}=S_{bsi}/V_s.$$

Evaluate divisions only for receivers with positive denominators; other shares are zero. A zero-spare instance receives zero in normal operation. Co-located instances retain their individual container identities and capacity shares.

If $O_s>V_s$ and $J_s=|\mathcal R_s|>0$, distribute only the excess above normal capacity equally among receiving clusters:

$$E_s=O_s-V_s,\quad X_{sb}=A_{bs}+E_s/J_s,\quad \pi_{sb}=X_{sb}/O_s.$$

With $H_{bs}=|\mathcal H_{bs}|$, define each instance's share of its host and its conditional receiving weight:

$$\alpha_{bsi}=1/|\{j\in\mathcal A_{bs}:h(j)=h(i)\}|,\qquad
v_{sbi}=\frac{S_{bsi}+(E_s/J_s)\alpha_{bsi}/H_{bs}}{X_{sb}}.$$

Excess is equal across physical hosts within a receiver, then equal across the eligible instances sharing a host. This also works when $V_s=0$ because it does not divide by $A_{bs}$. Normal capacity limits are not guaranteed in this temporary branch; report a need for more capacity.

## Final integration at the source cluster

With sufficient local capacity, $W_{esbi}=w_{esi}$ for $b=a$ and zero for external destinations. With overflow and a valid external decision:

$$W_{esbi}=\begin{cases}\eta_{as}w_{esi}&b=a,\\(1-\eta_{as})\pi_{sb}v_{sbi}&b\ne a.\end{cases}$$

Cluster and instance shares must come from the same root version. The cluster shares and the conditional instance shares in every active receiver sum to one. A source cluster with overflow must have $\pi_{sa}=0$. A cached decision that still treats it as a receiver is incompatible; deleting its share and renormalizing the rest is not allowed.

With $\eta=0$, define the local term as zero without evaluating an uncomputed conditional weight. With $D_{es}=0$, avoid division and retain a still-valid previous table if available. Each active row of a compatible final policy sums to one.

If there is no external receiver, or no valid compatible external decision, use temporary local fallback over eligible local service hosts:

$$r^{temp}_{esi}=r^*_{esi}+\alpha_{asi}z_{es}/H_{as},\qquad W_{esai}=r^{temp}_{esi}/D_{es}.$$

Evaluate this only for $H_{as}>0,D_{es}>0$. With no healthy eligible destination, return unavailable. An unestimated instance is not made a normal receiver through a fabricated weight. Failed instances and edges without the service are not processing destinations.

For a fixed normal plan, total foreign rate at an instance is $O_s\pi_{sb}v_{sbi}\le S_{bsi}$; adding local reservation stays within $U_{si}$. This is not an instantaneous guarantee under changing demand or asynchronous versions. Temporary distribution also does not prove queue stability during overload.

## WRR and event-driven updates

Maintain separate smooth-WRR scores for every source/service row. On selection, increment $q_{bi}$ by $W_{esbi}$, choose the positive-weight destination with the highest score, and subtract the row's total weight from the winner. Use deterministic tie-breaking.

Reset that row's scores on installation of a new policy version. Never select a zero weight. Install complete versioned tables atomically; reject old, incompatible, or partial updates. Removing a destination does not authorize automatic external-share renormalization.

Monitoring is windowed and publication is event-driven. New reports, readiness changes, and root decisions trigger review. Edges do not wait for simultaneous layer computations. Retain an old complete policy only while it remains valid; otherwise use a valid temporary policy or return unavailable.

In the current code, the proposed WRR hook is reached for a new flow or when an old route cannot be revalidated. Existing flows keep their destinations while those routes remain present. Selection after destination removal does not guarantee transparent connection migration. Request-level control under shared connections requires a request-layer integration.

Combining a table and making one simple smooth-WRR choice each cost $O(n)$ for $n$ destinations; optimization cost depends on solver and accuracy.

## Reference example for verification

The thesis example is hypothetical: three clusters representing MCI, Irancell, and Rightel, with two edges each. All six edges originate requests, but `B2` has no target-service instance. These are illustrative inputs, not measurements of real operator networks. Set $\Delta=5$, $\varepsilon=0.1$, $\kappa=1$, and $P=1$.

| Destination | $g$ | $N^{proc}$ | $T^{CPU}$ | $\mu$ | $U$ |
|---|---:|---:|---:|---:|---:|
| A1 | 2 | 450 | 9 | 100 | 90 |
| A2 | 1 | 270 | 4.5 | 60 | 54 |
| B1 | 2 | 285 | 5.7 | 100 | 90 |
| C1 | 2 | 352 | 7.04 | 100 | 90 |
| C2 | 1 | 237 | 3.95 | 60 | 54 |

| Source | Started attempts | $D$ | First/second local ping, `ms` | $\ell$ | $z$ |
|---|---:|---:|---|---:|---:|
| A1 | 612 | 122.4 | `1 / 6` | 86.4 | 36 |
| A2 | 408 | 81.6 | `6 / 1` | 57.6 | 24 |
| B1 | 180 | 36 | `1 / absent` | 36 | 0 |
| B2 | 120 | 24 | `6 / absent` | 24 | 0 |
| C1 | 288 | 57.6 | `1 / 6` | 57.6 | 0 |
| C2 | 192 | 38.4 | `6 / 1` | 38.4 | 0 |

Failures and measured queue residuals are zero. Each cluster solves source 1 before source 2. Convert ping milliseconds to seconds before computing cost. Cluster limits are `(144,90,144)` and demands are `(204,60,96)`.

| Row | Solved local rates | Solution condition |
|---|---|---|
| A1 | `(54.504863,31.895137)` | Interior; `nu=3.940377` |
| A2 | `(35.495137,22.104863)` | Both at remaining limits; for example, `nu=2` is valid |
| B1 | `(36)` | Single destination; `nu=1.513406` |
| B2 | `(24)` | Single destination; `nu=1.019302` |
| C1 | `(36.871360,20.728640)` | Interior; `nu=1.583011` |
| C2 | `(22.132591,16.267409)` | Interior; `nu=0.914849` |

Spare rates in destination order are `(0,0,30,30.996050,17.003950)`. With $O=60,V=78$, the root returns cluster shares `(0,5/13,8/13)` and conditional shares `(0.645751,0.354249)` in the last cluster. The first cluster scales local weights by `12/17` and external shares by `5/17`.

| Source / destination | A1 | A2 | B1 | C1 | C2 |
|---|---:|---:|---:|---:|---:|
| A1 | 0.445301 | 0.260581 | 0.113122 | 0.116878 | 0.064117 |
| A2 | 0.434989 | 0.270893 | 0.113122 | 0.116878 | 0.064117 |
| B1 | 0 | 0 | 1 | 0 | 0 |
| B2 | 0 | 0 | 1 | 0 | 0 |
| C1 | 0 | 0 | 0 | 0.640128 | 0.359872 |
| C2 | 0 | 0 | 0 | 0.576370 | 0.423630 |

Displayed values are rounded. With full precision, destination rates are `(90,54,83.076923,82.847065,50.076011)` and total `360`. Validate row sums and limits with full-precision values; display rounding is not a reason to renormalize the execution policy.

Also verify the thesis variants: entirely local demand `(100,60,96)`; first-cluster demand equal to `144`; global shortage `(330,75,120)`; no receiver `(200,100,170)`; failed `A2`; zero demand; and a path failure increase from `0` to `0.1`.

In global shortage, overflow is `186`, receiver spare capacities are `(15,24)`, and foreign rates become `(88.5,97.5)`. The only host in the second cluster reaches `163.5`; the two hosts in the third reach `(126.75,90.75)`. With no receiver, the first cluster's host rates are `(118,82)`.

With failed `A2` and first-cluster demand `100`, foreign rate is `10`. In the local failure variant, increasing the path failure ratio changes its fixed cost from `0.001` to `0.101` seconds and reduces the `A1` destination weight from `0.639152` to `0.402205`. The complete derivation remains linked in the thesis example.
