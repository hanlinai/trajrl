# TrajRL Incentive Mechanism

Date: 2026-11-09. Status: final draft for team review. Sandboxes are live; other capabilities are prototype or planned where stated. This document contains the mechanism, collateral, penalty, exit, bonus-eligibility and trust-boundary rules needed to review the design. Historical observations and experiments are dated below. Proposed parameters and unresolved launch decisions are identified explicitly; they are not deployed rules.

## In one paragraph

Self-improving AI is limited less by models than by the loop around them: a place to run untrusted agents, compute to train and evaluate on, a judge the optimizer cannot reach, and a record anyone can check. SN11 is a Bittensor subnet that supplies that loop as public infrastructure. It has one front door, **Eleven**, an agent that hosts the subnet. A person or an agent tells Eleven what it needs. Miners supply it. Eleven verifies the resource before handing it over and keeps checking it while it is in use. **Eleven also decides how the subnet's emission is paid**: every tempo it prices each kind of resource against several markets and SN11's own demand, and computes each miner's share inside limits that code enforces. Every resource is confidential, so operators cannot read or change what runs inside. Every input and decision is signed and published. People hold the keys and can stop Eleven at any time. Confidential sandboxes are live today; confidential CPU and GPU machines are next.

## For miners and validators, in five lines

- **Miners earn** for verified supply from the catalog: standing sandbox capacity, or orders for confidential machines. Unverified supply earns nothing.
- **Payout is capped** at the market value of verified supply. Emission above that is recycled, not spread over whatever exists.
- **Eleven sets prices and shares** each tempo; validator code checks every allocation against published rails and falls back to a published baseline if any check fails.
- **Collateral** backs admitted capacity; debts follow the coldkey; orderly exit is protected by an exit reservation.
- **Every rule, price and decision is published**, with the inputs that produced it.

## 1. Why: self-improving AI needs a loop it can trust

Here, recursive self-improvement means an agent uses the results of its work to improve the code, tools, models and workflows it will use next. Every such system runs the same cycle:

```text
Execute a task → find a problem → propose a change
       ↑                                  ↓
Keep a verified improvement ← evaluate ← run an experiment
```

The cycle needs three things, and SN11 supplies them as layers:

| Layer | What the cycle needs | SN11 | Status |
|---|---|---|---|
| **Run** | Isolated places to execute tasks and candidate changes, and the compute they need, at scale | The resource network: confidential sandboxes, CPU and GPU machines | Sandboxes live; machines planned |
| **Judge** | Evaluation the agent cannot read or rewrite | Sealed judges whose hidden tests run where the optimizer cannot reach them | Prototype |
| **Prove** | Evidence that connects a claimed improvement to the versions, runs and results behind it | Signed, hash-chained records anyone can recompute | Prototype |

Leave out Judge or Prove and the cycle optimizes the measurement instead of the goal. The field keeps finding this. Recent self-improvement work on terminal agents found that rewarding partial success sent half of the reward to failed attempts, and that a branch tuned to one benchmark regressed on another; its authors conclude that checkpoints need protected validation. Work that optimizes agent environments found its research agent falling back on proxies such as answer length when no grader was available, which hurt held-out results.

We learned the same lesson by running a subnet. A Bittensor subnet is already an improvement loop with money attached: a scoring function and a crowd paid to optimize it. Over two seasons, the cracks the miners found were in the judge, not in the solvers:

- An empty submission scored 13.5% of the maximum.
- The gap between the top entries was smaller than the variation between validators.
- Near-copies appeared within hours.

When a task was specified precisely, even cheap models solved it. The hard part was always faithful feedback.

### What a loop consumes

Take a coding agent that keeps failing at dependency setup. It writes an environment-checking tool, runs the current and candidate versions on the same tasks several times, checks the result on held-out tasks, and keeps the tool only if it helps without regressions. That one cycle needs a dozen sandboxes in parallel. A larger cycle also needs GPU machines to fine-tune, serve or evaluate a model, CPU machines for builds and simulations, and confidential machines whose operators cannot read the hidden tests, the data or the evaluator.

The demand arrives in bursts and the mix changes between runs. A subnet that sells one fixed product serves one step of the loop. SN11 is designed to supply the whole mix and to add new kinds of resource as loops need them.

## 2. The design: an agent-centred resource network

```text
  person or agent ──request──▶  Eleven  ──order──▶  public order book  ◀──offers── miners
                                  │                                                │
                                  │◀────────────── resource delivered ─────────────┘
                                  │
                         verify (attestation + probes)
                                  │
         user ◀──access + proof───┘        validators ──weights──▶ chain
```

### One front door: Eleven

Users reach SN11 in two ways, both answered by Eleven:

- **API.** A typed request: resource class, specification, quantity, duration, budget, and requirements such as region. Agents call it directly.
- **Conversation.** A person or an agent describes what it needs ("eight sandboxes with Python and Claude Code, and one 80 GB GPU for six hours to evaluate checkpoints"). Eleven turns it into a typed request, shows it with the price, and submits it after confirmation.

Either way the user gets back resources, access details and proof of what they run on. Users pay in USD or credits from one prepaid balance with a hard stop. They never handle Bittensor keys or miner collateral.

Status: today users enter through the sandbox dashboard, CLI and API at [sandbox.trajrl.com](https://sandbox.trajrl.com/). The Eleven front door is planned, starting with sandboxes.

### A bounded catalog

SN11 does not supply whatever a request names. It supplies resources from a **catalog**, and each class states what is supplied, in which standard specifications, and exactly how it is verified:

| Class | What the user gets | How SN11 verifies it | Status |
|---|---|---|---|
| **Confidential sandbox** | An isolated workspace in an Intel TDX VM: runtime image, filesystem, shell, optional agent (Claude Code, Codex, Hermes, Pi) | TDX attestation of the measured runtime, liveness and isolation probes | **Live** |
| **Confidential CPU machine** | A whole TDX VM of a standard size | TDX attestation, benchmark against the declared size | Planned |
| **Confidential GPU machine** | A TDX VM with a declared number of GPUs in confidential-computing mode (for example H100, H200, B200) | TDX attestation, NVIDIA attestation of each GPU, benchmark against the declared model | Planned |
| **Sealed judge** | A TDX machine that runs hidden tests and returns a signed score | TDX attestation; seed committed before the run and revealed after | Prototype |

The catalog is the boundary of the subnet:

- **Every class is confidential.** SN11 has no non-confidential tier. Hardware that cannot attest that its operator is locked out, such as a GPU without confidential-computing mode, is not admitted.
- **SN11 pays only for what it can verify.** A class is added only when its verification method is written down and tested against fake supply.
- **SN11 pays only for catalog specifications.** A specification earns at its catalog price. A new specification is admitted only with a verification method and either a second independent supplier or demand the platform originated. The simulated niche-specification attack described below showed why: a sole supplier can fill its capacity with its own orders, leaving no peer for a human or agent to compare it against.

Adding a class or specification works like any other change: Eleven proposes it with the verification method, adversarial tests and a starting price; people approve it; the decision is published.

**Units.** Each class is metered in one unit of capacity. For sandboxes the unit is the host CVM, weighted by its committed size (the reference `tdx.c3-4` counts 1, `tdx.c3-8` counts 2). Sandboxes inside a CVM share it; they do not multiply its reward time or its collateral.

### Standing capacity and orders

- **Standing capacity.** For resources users expect in seconds, such as sandboxes, miners keep admitted capacity ready. Ready capacity earns before any user arrives, so a burst of agents never waits.
- **Orders.** For resources that are expensive to keep idle, such as GPU machines, Eleven posts an order to a public order book: class, specification, quantity, start time, duration and the reward on offer. Miners with admitted capacity offer to fill it, and the platform assigns the order among qualified offers. A miner cannot choose which orders it fills. Contribution starts when the delivered resource passes verification, and the order settles at its posted price.

Each class declares its mode, and can move from orders to standing capacity as demand becomes predictable.

### Verify, hand over, keep checking

Nothing reaches a user until it passes its class's verification. Validators keep probing it while it is in use. A resource that fails verification earns nothing for that interval; one that fails while a user depends on it is penalized. Each delivery carries its verification record, so the user can check the proof instead of trusting Eleven or the miner.

## 3. Eleven decides the emission

Most subnets pay miners with a fixed formula that people retune every few months. A formula cannot keep pace with a network whose resources, prices and demand change every week, and miners learn to optimize the formula instead of the service. On SN11, **Eleven computes the miner emission distribution every tempo**, the way a market maker sets prices, and code bounds what it can do.

### What Eleven reads

- **Verified service records.** Which resources passed verification, for how long, and under which orders or occupancy. Validators produce these records; Eleven reads them and cannot change them.
- **Market prices from several sources.** TAO from seven exchanges; SN11's alpha price from the chain; rental prices for comparable machines from RunPod, Vast.ai, AWS, Azure and GCP in the first version. Public prices for confidential machines are thin: Azure is the only on-demand confidential H100 found so far, priced the same as its plain H100. So a confidential class is anchored to the median of the plain-machine sources times a measured confidential premium, currently 1.0, and the thinness of that anchor is published with the price.
- **SN11's own market.** Requests, what users paid, how fast orders filled, which went unfilled, miners' offers, and requests the catalog could not serve.
- **The account graph.** For each user account: when it appeared, which providers it used, what it paid against list price, and any on-chain funding link to a miner coldkey. This is evidence for review; it does not identify every related account.
- **Quality.** Start latency, failures during use, probe results, user reports.

Anything a miner or user writes, including account names and notes, is data. It is never an instruction.

### What Eleven decides

1. **A price for each class.** The emission value of one unit-hour. It starts from the market reference and moves with SN11's own supply and demand: unfilled orders and slow fills raise it, idle surplus lowers it.
2. **Each miner's share.** Verified units times the class price, adjusted for quality and penalties. Total payout is at most the value of verified supply; the rest of the tempo's emission is recycled.
3. **Where to steer supply.** Bounties for scarce classes or regions, lower prices for oversupplied ones, and withheld payment for supply it judges self-dealing or collusive, with the evidence attached.

Each tempo, Eleven makes **three independent decisions and takes the median** of each price and each miner factor. Each decision keeps separate memory. Simulations below found lower variance on some attack sets; the median did not prevent shared blind spots.

### What Eleven publishes

Before the weights take effect, Eleven publishes an allocation statement: the weight vector, a line item per miner, each class price with its sources, the reason for every adjustment, and the hash of every input it read. In production, prices will be fetched from inside Eleven's TDX machine, and each source, time and response hash recorded in its signed trace. Anyone can check what Eleven saw and how it reached each number.

### The rails

Published validator code checks every statement before any weights are submitted:

| Rail | Rule |
|---|---|
| Verified supply only | A hotkey with no verified service in the period receives zero weight. |
| Catalog only | Units count only for catalog classes and specifications, at the catalog price. |
| Price band | Each class price stays within a fixed band around the median of the market sources, and moves at most a fixed amount per tempo. |
| Concentration | No coldkey receives more than a fixed share of emission. |
| No self-payment | Keys controlled by the team or by Eleven receive nothing beyond published amounts. |
| Payout cap | Total payout is at most the sum of price × verified units; the remaining emission is recycled. |
| Integrity | The statement is signed by Eleven's attested key, references the period's service records, and its weights sum to one. |

If a statement fails any rail, or Eleven produces none, validators use the **baseline** for that tempo: verified units × the last approved class prices × the occupancy factor, under the payout cap. The baseline may include fraud rules Eleven distilled from its own decisions, but only after people review and publish them. The baseline is computed and published every tempo beside Eleven's allocation, so every departure from it is visible.

**Users cannot choose their provider.** The platform assigns every sandbox and every order, and occupancy with no platform assignment behind it earns nothing. Assignment alone does not rule out collusion; the occupancy bonus has its own eligibility rules (see [How providers earn](#how-providers-earn)).

**Who sets the rails.** People do. The rails, band widths, concentration cap and list of price sources are part of the constitution and change only by human review. Within them, Eleven decides alone, and is judged on outcomes published every tempo: how fast requests were filled, how its prices compared with the market, uptime during use, and how much emission bought how much verified supply.

### What the experiments show

Simulations run on November 8–9, 2026 compared agent decisions with deterministic policies. Each run covered 30 tempos. Fraud paid means emission paid for fake, duplicated, self-dealt or failed supply. The setup:

- a simulated SN11 economy on real market prices and the real emission budget;
- honest miners that grow or shrink with their margin;
- four sets of adversaries. The third and fourth sets were sealed, by committed hash, before anything was tuned against them.

The third set included a three-miner wash ring, GPUs that failed half their jobs, discounted self-orders mixed with real orders, hotkey rotation and two inflated price sources. The fourth added a sole supplier manufacturing demand for a niche GPU specification, a miner dropping occupied users, duplicated supply, account-name prompt injection and a GPU price source crashing to a quarter of its value. In the catalog rerun, niche units were treated as ordinary catalog supply and all orders were assigned across compatible idle capacity. The scripted attacker kept buying even when competitors received its orders.

| Emission paid for fraud (USD per 30 tempos) | Sealed set 3 | Sealed set 4 | Set 4, catalog rail |
|---|---:|---:|---:|
| Fixed formula, all emission paid out | $1,389 | $1,883 | $983 |
| Best deterministic code (price controller and fraud rules) | $744 | $1,158 | $189 |
| Rules Eleven distilled from its own decisions | $762 | $1,299 | $236 |
| Eleven, one decision per tempo | $451 (4 runs, $215–843) | $1,042 (3 runs, $295–1,501) | $310 |
| **Eleven, median of three per tempo** | **$162** (2 runs, $32–291) | $1,162 (3 runs, $916–1,303) | **$210** |

These are simulations with few runs per cell. Set 4 and its catalog rerun used three seeds per policy; set 3 used two ensemble runs and four single-decision runs. All Eleven runs together cost about $33 in model calls. The catalog-rerun ensemble paid $1.69 per market dollar served, versus $2.34 for the best code; that metric includes payment for supply beyond the fraud column. The simulator used fixed GPU miners and therefore did not establish how real GPU suppliers would respond to underpricing. These results motivate the design but do not prove production reliability. Shadow mode on SN11's own records is still required.

What we learned, and built into the design:

- **Live judgment generalizes better than fixed rules.** Rules written from known attacks caught those and missed new ones, including the rules Eleven distilled from itself. On set 3, which nobody had written rules for, the median of three Eleven decisions paid fraud a fifth of what the best code paid, and its worst run beat the code's average. Distilled rules stay as a reviewed fallback, not as the decision.
- **The median fixes variance, not blindness.** One decision per tempo occasionally did worse than code. Three decisions with a median removed those runs on attacks Eleven could see. On set 4, a niche-specification monopoly fooled every policy, the ensemble included. The catalog rule, not better judgment, closed it: fraud paid fell by over 80%, after which the ensemble and the best code were close on fraud, the ensemble paid the least per dollar of service, and only Eleven ignored a crashed price source that pulled the code's GPU price about 40% under market. Rails handle what judgment cannot see.
- **Paying out all emission is the largest waste.** Spreading each tempo's full emission over whatever supply exists paid about three times the market value users received. Hence the payout cap.
- **Eleven found a mechanism fix.** It flagged GPU occupancy with no platform order behind it. Hence platform-only assignment.
- **The account graph catches collusion that leaves a trail.** Cross-dealing between two miners was caught once Eleven could see funding links. It did not help against colluders who pay by card.
- **Manipulation did not move it in these tests.** A fake $60 H100 quote, an 8× corrupted source, notes and account names claiming special status were named and ignored, and the price band clipped what remained. The ensemble wrongly discounted no honest miners in the earlier tests, but did so in 0.7% of miner-tempos in the catalog rerun. Fraud controls therefore need false-positive monitoring as well as attack tests.
- **Reasoning effort is load-bearing.** At low effort Eleven missed every new trick. At high effort the median of three costs about $0.08 per tempo, under $2 a day.

The budget is real money. At 1 alpha per block, miners receive about 2,950 alpha a day, roughly $4,400 at November 2026 prices. At the reference prices that pays for about 27 confidential H100s or 3,700 confidential vCPUs running continuously. Every dollar Eleven declines to pay for fraud or oversupply is recycled into the subnet.

## 4. Why confidential computing is at the centre

A hidden test needs protection from the host operator and the optimizing agent. Intel TDX protects a CVM from its host; measured software and access controls must separately keep an evaluator out of the agent's reach. The same protection applies to a user's code, data and credentials. Every catalog resource must have an appropriate confidential-computing verification method, including planned GPU classes.

### What verification establishes

For the sandbox design, verification checks a fresh nonce-bound TDX quote, current accepted firmware, the pinned guest image and application definition, the running sandbox roster and image digests, and the trace-signing key's binding to that CVM. The measured guest has no operator login path. An attested key service releases disk keys and secrets only to accepted measurements and firmware. Changing the code must change the measured identity and fail the old key-release policy.

The meter inside the CVM signs a hash chain of inference calls. That proves the recorded trace has not been edited after signing; it does not by itself prove continuous compute availability, correct evaluation or a complete record of all execution. Availability, performance and trusted capture need separate service evidence and probes.

### Trust boundaries and current limits

- The miner can stop or delete the CVM or cut its network. Confidentiality does not guarantee uptime. TDX also depends on accepted firmware and does not cover every physical CPU attack.
- Dashboard and API traffic passes through the platform, which can see relayed messages, opened files and terminal commands. The platform cannot read unrelayed CVM memory or disk through an operator login. Confidential execution does not make the dashboard end-to-end private.
- Inference leaves the CVM over TLS. Model providers see prompts and responses. Default Engy inference passes through the platform's billing relay; calls using a user's own provider key go directly from the CVM to that provider. The platform handles that key during setup and must not retain it; the in-CVM meter holds it during use.
- Agents can access the internet. Confidential computing does not prevent an agent from sending data out. Restricted egress for evaluation workloads is a separate requirement.
- Sandboxes sharing a CVM are containers isolated by the guest kernel and separate volumes. They share one account's CVM and do not have separate hardware trust boundaries.
- The November 2026 single-app beta used a platform gateway that could see request contents, lacked encrypted volume backups for migration between miners, and used a single-CVM key service. These limits concern that product path; they must not be treated as guarantees of private ingress, durable failover or a replicated key service. A replacement machine with fresh disks is insufficient evidence that a user's data and service have been restored.

The platform also controls initial admission, assignment and some evidence collection. Platform signatures identify who issued a record; independent checks are needed to establish whether it is true. Attestation alone does not remove those dependencies.

## 5. Who runs TrajRL: Eleven

SN11 is the first improvement loop running on its own infrastructure. Day-to-day work on the subnet, including this mechanism, is done by **Eleven, the steward of SN11**, under a constitution people wrote: a mission (Run, Judge, Prove), principles in priority order with users first, and hard rules. Eleven has three jobs:

- **Host the network.** Answer requests, write orders, check deliveries against the catalog's verification methods, and report what users asked for that the catalog cannot supply.
- **Run the economy.** Price each class and compute the miner emission distribution every tempo, within the rails.
- **Improve the network.** Read the subnet's public data, run experiments in SN11's own sandboxes, and propose changes to the catalog, the mechanism and the code, each with evidence: a baseline, adversarial tests, a noise floor and held-out results.

| Eleven does | Eleven proposes, people decide | Only people |
|---|---|---|
| Answer requests, price classes, post orders and bounties, run verification, compute and publish the emission distribution, withhold payment from supply it judges fraudulent | New classes and specifications, collateral amounts, penalty parameters, distilled fallback rules, code changes | Hold keys, set the rails and price sources, amend the constitution, deploy to production, pause Eleven |

People hold every key, including the subnet owner key; Eleven never touches them. Once its allocation is live, validator software submits it automatically when it passes the rails, without a person approving each tempo. Any other on-chain operation is filed as a proposal and carried out by the team. Every decision, by the agent or a person, is published. Every model call Eleven makes is recorded in a hash-chained trace, signed inside a TDX machine whose key appears in a fresh attestation quote, so anyone can check that the record of what Eleven saw and said has not been edited.

**Prior art.** In March 2026, Arbos, an agent given a goal file by a Bittensor co-founder, built and ran SN97 for about two months before it passed to a human team. It showed an agent can build a subnet. SN11 aims to be the subnet an agent governs **in a way anyone can verify**: a public constitution instead of a goal file, an economy run within rails that code enforces, signed traces instead of trust, and people holding the keys so the arrangement can last.

### Early results, including what did not work

- **Building to a precise spec is solved.** Eleven implemented each component of this mechanism from its specification and passed every hidden test.
- **Judgment is where the variation is.** In blind reviews of the mechanism scored against a rubric sealed in advance, Eleven found real flaws the human review had missed, such as a reward formula that paid a registered key 101 units out of 100. It also missed the flaw the human reviewer ranked first.
- **A lesson that looked good did not generalize.** A review method that lifted scores on one document gave no clear gain on a held-out document, so it was not adopted. Overfitting to a single success is the failure this loop exists to catch, and it caught it in our own work.
- **A defence that looked good had a blind spot.** The median of three decisions beat code on one sealed set and was fooled with everyone else on the next. The fix went into the rails.

## 6. How a user uses TrajRL

1. Ask Eleven, through the API or a conversation, for what you need. It returns a typed request with the price.
2. Confirm. Standing capacity, such as sandboxes, is assigned in seconds; ordered resources are filled from the order book.
3. Receive access details and the verification record. Run agents, train, evaluate, test.
4. Release it when finished. Billing stops at release and never exceeds your prepaid balance.

Today step 1 is the sandbox dashboard, CLI and API. Inference inside sandboxes defaults to Engy, whose responses can carry signed receipts; any supported provider can be configured instead, and inference is funded by the user, a partner or the platform, never by miners.

## 7. The incentive mechanism

| Participant | Role |
|---|---|
| Users (people or agents) | Ask for resources and use them |
| Eleven | Hosts the network, verifies deliveries, prices resources, computes the emission distribution, proposes improvements |
| Miners (providers) | Supply catalog resources: standing capacity, or orders from the order book |
| Platform | Admits capacity, assigns users and orders, coordinates recovery and orderly retirement |
| Validators | Verify resources, availability, collateral and service records; check Eleven's allocation against the rails; submit its weights, or the baseline if a rail fails |

### How providers earn

You provide resources from the catalog. Once a resource is admitted and verified as available, or delivered against an order and verified, it earns contribution for its class, specification and verified time. Contribution is paid in subnet emission, the alpha tokens Bittensor distributes, at the class price. Each tempo pays out at most the value of all contribution. If that value is below the tempo's emission, the remainder is recycled; if it is above, everyone is scaled down in proportion.

Eleven's starting point, and the fallback when a rail fails, is the baseline:

```text
contribution = Σ over verified intervals of (class price × units × time × occupancy factor) − penalties
```

| Resource condition | Contribution |
|---|---|
| Standing capacity, idle and ready | Base |
| Standing capacity, occupied by eligible user activity | Base plus up to 20% |
| Delivered against an order and verified | The order's posted price |
| Offline or failing verification | Nothing for that interval |

**The occupancy bonus pays for real use.** Free, promotional and paying users qualify under the same rules. The proposed initial profile requires:

- A verified identity deduplicated across accounts and API keys. Anonymous or unverifiable use earns no bonus.
- At most two reference-CVM-hours per identity per UTC day, across all hosts and hotkeys. A coefficient-2 CVM consumes the allowance twice as fast. Concurrent containers do not create more allowance or multiply occupied host time.
- A platform-recorded task or exec action initiated by the user within five minutes of the eligible interval. Miner heartbeats, periodic commands and CPU load alone are insufficient. A proposed 15-minute idle-recycling timeout requires notice and data-preservation rules before activation.
- Exclusion of accounts verifiably controlled by the serving miner. IP similarity alone does not prove common control. Incomplete linkage checks do not establish bonus eligibility.
- A network-wide bonus budget of 10% of base contribution. For standing capacity, let `Base` be the sum of class price × verified units × available hours, and `Eligible` the same sum using eligible occupied hours. Set `b_eff = 0` when `Eligible = 0`; otherwise set `b_eff = min(0.20, 0.10 × Base / Eligible)`. Each eligible interval earns its base plus `b_eff` times that interval's base. Ordered resources settle at their posted price without a second standing-capacity bonus.

The 20% interval target and 10% network budget are distinct limits. Base contribution remains unchanged when the bonus budget binds. Persist allowance counters and interval evidence across retries, token rotation and restarts. Publish verification identifiers and hashes, not user content or raw identity credentials. Synthetic probes, operator tests and exit-only standby earn no bonus.

Identity verification and activity checks bound abuse but do not prove Sybil resistance. Until eligibility, allowance replay, privacy handling and abuse trials pass review, eligible occupied time is zero. Raw occupancy never raises admitted capacity.

Model choice, inference provider, token consumption and user revenue do not enter the formula. SN11 pays for verified supply, not for resale.

### Why each rule fits an improvement loop

| Rule | Why |
|---|---|
| Ready capacity earns before users arrive | Loops are bursty. Parallel exploration, repeated runs and multi-seed evaluation arrive in batches; without ready capacity there is no claim in seconds. |
| Expensive resources come by order | Idle GPUs are costly. Orders let SN11 offer them without paying for capacity nobody uses. |
| Every class needs a written verification method | A loop is only as trustworthy as its inputs. SN11 pays only for what it can check. |
| Only catalog specifications earn | A sole supplier of an odd specification can manufacture its own demand. |
| Payout is capped at the value of verified supply | Spreading all emission over whatever exists pays several times market value and rewards oversupply. |
| The platform assigns every user and order | A provider that cannot pick its customers cannot easily sell to itself. |
| The bonus needs eligible activity | Occupancy is cheap to fake; activity tied to a verified identity is not. |
| An agent prices supply every tempo | Demand for each kind of compute shifts faster than people can retune a formula. Prices anchored to several markets and moved by SN11's own fills steer supply to where loops need it. |
| Any model, harness or payer earns the same | Infrastructure should not choose tools for the user. |
| Debts follow the coldkey | Teams will run week-long experiments. Reliability must be accountable; a new hotkey does not reset it. |
| Native tempo, recomputable finalization | The Prove principle: anyone can recompute the result. |

### Collateral

Each class and specification has a published fixed alpha collateral requirement per unit:

```text
Required collateral = Σ over classes and specifications of (admitted units × collateral per unit)
```

For example, at 10 alpha per reference CVM, three admitted reference CVMs require 30 alpha. The amount is illustrative. Confidential GPU machines carry higher requirements. The collateral calibration below explains why a 20-alpha candidate failed a proposed seven-day stress target.

To expand, apply for capacity, fund the locked amount and raise the minimum collateral floor. New resources earn after verification. Admission is limited by demand and budgets; adding machines on your own earns nothing. Switching users, restarting a container or adding agents in the same CVM needs no new deposit.

A minimum collateral floor preserves the required amount; normal rewards do not release collateral that must stay locked. Only the balance above the current floor can be released, gradually. If collateral is underfunded, on-chain rewards may fill the shortfall; fund new capacity before activation.

Collateral is checked per hotkey. Let `R` be the current requirement for active commitments plus remaining approved exit obligations, without counting a commitment twice. Unactivated expansion reservations add to `R_target`, but earn nothing and do not change existing commitments' current requirement. The same funds cannot cover multiple commitments, and funds on a sibling hotkey cannot substitute for coverage.

For locked alpha `L`, miner-set minimum floor `F`, the collateral entry's release ratio `k`, and actual emission `E` that triggers release:

```text
release = min(max(0, L − F), k × E)
```

Normal operation requires confirmed `L ≥ R` and `F ≥ R`. Read `k` from the actual collateral entry; a new operator setting does not automatically change existing entries. A proposed `k = 1` policy for new entries still needs runtime verification and operator approval.

The owning coldkey signs collateral additions and floor reductions. Platform approval is an application rule, not a chain permission preventing the miner from lowering its floor. If confirmed funds or floor fall below the requirement without an approved exit, stop new assignments and affected contribution from confirmed noncompliance onward. Protect existing users and resume scoring only after coverage and verification recover. Old weights and other emission sources may still release funds during enforcement delays.

### Admission, assignment and resource states

Each commitment has a persistent resource ID, specification version, owner and underlying resource binding. The reference `tdx.c3-4` is 4 vCPU and 16 GB with coefficient 1; `tdx.c3-8` is 8 vCPU and 32 GB with coefficient 2. Multiple containers share their host's capacity. Splitting a host must not increase contribution, reduce collateral or create overlapping resource commitments.

| State | Contribution and obligations |
|---|---|
| Requested or provisioning | No contribution until admission, collateral and verification pass. |
| Ready | Verified admitted capacity earns base contribution. |
| Serving | Base plus any eligible bonus; an order follows its posted terms. |
| Faulted | No contribution for unavailable intervals; confirmed user-impacting miner faults add penalties. |
| Suspended | No new assignments; eligible existing service may continue. Idle suspended capacity leaves ordinary scoring admission. |
| Draining or awaiting release | Approved real exit capacity earns base only while obligations and release remain. |
| Retired | No supply contribution; shutdown clearance and completed withdrawal remain separate statuses. |

Initial scheduling is centralized. Before each control period, the operator signs a capacity ceiling, cost basis, ready-capacity floor and exit reserve. Trusted seven-day peak usage and a versioned headroom factor can inform readiness estimates, but new supply still needs a signed budget and independent-demand decision. Raw starts, occupancy and promotional bursts cannot automatically expand admission.

Existing user obligations and approved exit reservations take priority. New applications use only the residual budget. A falling budget stops new admission and requires publishing the shortfall; it does not cancel an honest miner's approved exit reservation. Equivalent applications are ordered by verified reliability, sufficient funded collateral, reservation time and resource ID. New entrants use a published probation class.

Reserve capacity first, fund the total reservation requirement and floor, then verify confirmed collateral and actual resources before activation. Activation updates reservations and effective commitments atomically so concurrent requests cannot reuse funds or capacity. Cancellations release registry reservations but do not instantly refund locked alpha. Upgrades require funding and verification; downgrades need cleared user obligations and an approved reduction. Specification changes have effective versions and published migration rules.

Among compatible admitted hosts with room, assignment is weighted by free capacity coefficient and published reliability. Fix the candidate set before drawing randomness; commit the seed before assignment and reveal it afterward. Record the candidate digest, policy version and outcome for replay. Users cannot choose their miner. These are design requirements; the existing oldest-ready or least-busy scheduler does not prove unbiased random assignment.

### Penalties

If you are responsible for an interruption while a user depends on a resource, or fail to deliver an order you took:

- you earn nothing for the interruption;
- an additional deduction applies, by class, specification, duration and penalty multiplier;
- repeated failures raise the multiplier up to a cap and may pause new assignments and orders.

Penalties offset contribution, and any uncovered balance carries forward:

```text
net     = max(0, gross − current penalties − opening balance)
closing = max(0, opening balance + current penalties − gross)
```

Aggregate all of a coldkey's contribution and penalties before applying these equations. Do not clip each hotkey's negative result first. A positive opening balance can be cleared in the same period: gross 5, no new penalties and opening balance 3 leave net 2 and closing balance zero. A positive closing balance implies zero net contribution.

Deductions do not debit collateral principal directly. All hotkeys under one coldkey share one contribution and penalty account. Adding hotkeys, removing machines or going offline does not erase the balance, and an official coldkey swap carries it over. Preserve service-time ownership so a reused UID does not inherit an unrelated miner's debt. A wholly new coldkey without verifiable lineage cannot automatically be recognized as the same operator.

The earlier sandbox baseline measured contribution and debt in weighted CVM-hours. This multi-class design prices supply. Contribution, penalties and carried debt must use one published unit and versioned conversion policy; a price change must not silently rewrite old debt. That conversion remains a launch decision. A penalty balance is a contribution deduction, not automatically an alpha or USD debt.

Once zero miner-incentive weights take effect, that release path stops only if no other emission reaches the hotkey. Earlier weights, activation delays and validator dividends can still unlock collateral. Local zero contribution is not an instantaneous principal freeze. Assess abandonment risk using funds still actually locked and evadable obligations, not the original deposit.

### Fault evidence, escalation and corrections

An incident starts at evidence-supported service unavailability. A missed heartbeat triggers investigation; without earlier evidence, use the first confirmed failure. Recovery must restore the agreed environment, necessary data and service. An empty replacement container is insufficient. The incident ends at valid restoration or user release; release does not erase earlier faults. Platform-caused recovery delay and shared provider or validator failures are not automatically miner faults. Idle downtime stops contribution without inventing a user incident.

Count one underlying incident once for escalation. Deduct overlapping downtime on the same resource once, using the highest applicable multiplier. Split a continuing outage at tempo boundaries without counting a new incident. Proposed parameters are a base multiplier of 2, doubling per attributable incident in a trailing 24-hour window up to 8, with new assignments paused after the third incident. These require calibration. The multiplier is capped; total deductions can exceed the period's gross contribution.

Re-admission needs repair, verification, performance checks and an observation period. Qualified service must provide a route to offset debt. Ordinary admission still depends on demand; approved exit capacity retains its reservation.

Identify each deduction by incident, resource, accounting identity and source tempo. Persist offsets so retries do not apply them twice. Uncertain attribution stays disputed. Late evidence belongs to its source period. Correct finalized records through versioned adjustments and replay subsequent balances; publish compensation rules before launch where rewards have already been distributed. Historical chain payouts cannot be assumed reversible.

### Tempo

A tempo is the subnet's native accounting cycle. Service is recorded during a tempo, and its contribution and penalties are finalized when the next one starts. Weights are submitted after finalization; on-chain activation can lag, so this is not payment at the boundary block.

Use confirmed native epoch boundaries for the deployed runtime. A fixed minute count, local block division or predicted countdown does not establish a boundary. Windows include their starting boundary and exclude the next. Measure eligible service in timestamped seconds, split at boundary timestamps and specification changes, and convert to hours. Mid-period admission earns only actual eligible time. Recover missed periods separately. Record the source period, finalization version, submission block and actual activation block.

### Submission targets and unavailable results

Map service hotkeys to registered targets only with verifiable ownership lineage. Allocate a coldkey's net contribution across sources in proportion to all source gross contribution, including unmappable sources in the denominator. Unmappable shares remain unallocated. For example, gross 100 on an unmappable key and 1 on a live key, with net 101, allocates 1 to the live key and leaves 100 unallocated. It must not credit 101 to the live key.

For a nonzero valid allocation, normalize allocated targets using the deployed runtime's integer total. Floor exact shares, then distribute remaining integer units by descending fractional remainder, breaking ties by UID. Independent decimal rounding can violate totals. These local weights are targets, not guaranteed alpha payouts; consensus and activation affect actual distributions.

Zero contribution, no mappable targets, conflicting boundaries or missing evidence produce an exception, not equal shares or assumed successful service. Define and verify the chain action for each exception before launch. Skipping a submission may leave old weights active. Ordinary normalized weights alone do not establish the payout cap or recycle unused emission. The chain recycling path, treatment of unallocated value and interaction with concentration limits remain launch gates. The last approved prices used for fallback must also satisfy the current rails; handling incompatible rails requires an approved exception policy.

### Retiring machines and withdrawing collateral

1. Request retirement. The platform stops assigning new users and orders to those resources.
2. Finish existing service or confirm migration. Once cleared, shutting down incurs no penalty.
3. Under the approved plan, lower the hotkey's minimum collateral floor with your coldkey. The subnet owner does not do this for you.
4. Eligible collateral unlocks gradually as emission arrives, and you can withdraw what has unlocked.

**Exit is protected.** When your capacity is first admitted, the platform reserves base-only admission for the capacity you will need while exiting, until penalties are settled and the agreed release completes. New admissions cannot take that reservation, and it is not revoked just because demand falls.

**Shutdown clearance is not withdrawal.** If you stop all supply and receive no emission, the unreleased balance stays locked. There is no guaranteed full refund by a fixed date, and no guarantee of recovering the original TAO or USD value. Partial retirement reduces only the approved requirement; collateral is locked and released per hotkey while contribution and penalties are combined per coldkey.

Keep the approved real exit capacity admitted as base-only standby until penalties are offset and the agreed release finishes, even at zero external occupancy. Lower each hotkey's requirement under a decreasing exit reserve; full exit can lower its floor to zero while accepted exit supply continues. Emission on a sibling hotkey does not unlock collateral on the retiring one. Offline or fabricated supply earns nothing, and a chain halt or loss of emission cannot be repaired with fictitious contribution.

### Exit sizing and the rejected collateral candidate

Before accepting funds, disclose each entry's actual release ratio, all locked amounts to be released, its registered payout path, approved retained capacity and a conservative exit estimate:

```text
repayment_days = opening_penalty_units / verified_base_contribution_units_per_day
release_days = alpha_to_release / (k × conservative_alpha_per_day_on_this_hotkey)
exit_runway_days = repayment_days + release_days + finalization_and_activation_delay_days
```

Do not assume reward emission while contribution is offsetting debt. Include ordinary and exit-reserved supply in the payout denominator, other miners' bonus dilution and an emission stress haircut. Include registration bonds and voluntary excess deposits in `alpha_to_release`. If the conservative rate is zero, there is no finite release estimate. A failed or canceled pre-service reservation needs a qualified release path; otherwise stop admission before requesting a new lock.

At finalized block 9,458,199 on November 8, 2026, 01:41:58 UTC, runtime 488 storage observations implied a miner budget of 2,952.016480 alpha/day. A 360-block interval averaged 12 seconds per block. This was an RPC rate observation, not an independently verified storage proof, realized daily payout or future guarantee. The public product's prototype hotkeys were reported unregistered, so the observation did not establish their actual earnings or collateral-entry terms.

The planning scenario used 700 reference-CVM coefficient units including exit reserves, a 50% emission haircut, maximum 1.10 bonus dilution, `k = 1`, no debt and one day for finalization and activation:

```text
nominal alpha per reference-CVM-day = 2952.016480 / 700 = 4.217166
stressed alpha per reference-CVM-day = 4.217166 × 0.5 / 1.10 = 1.916894
exit days for a 20-alpha bond = 1 + 20 / 1.916894 = 11.433546
maximum bond for a 7-day target = (7 − 1) × 1.916894 = 11.501363 alpha
```

The 20-alpha candidate fails that proposed seven-day target. The 700-unit ceiling, stress assumptions and seven-day target were planning inputs, not approved production terms or an SLA. Halving `k` doubles the release portion. Actual bonds require signed calibration against the deployed payout path, the supply-value cap and conservative per-hotkey emission. A normalized-share estimate alone cannot prove a viable exit under the newer payout cap.

### Records required for independent verification

Use one chain identity, subnet ID, rule version and confirmed boundary set across the registry, finalizer and validators. The ledger must retain:

| Record | Required contents |
|---|---|
| Rule and identity | Effective block, specification and collateral versions, fault parameters, coldkey root, hotkey lineage and service-time ownership. |
| Resource and interval | Persistent resource ID, underlying capacity binding, admission state, timestamps, availability, assignment and verification evidence. |
| Collateral and exit | Queried block and hash, actual locked amount, floor, release ratio, registry requirement, exit reservation, obligations and shutdown clearance. |
| Fault and settlement | Incident evidence, responsibility, source period, multiplier, disputes, opening balance, gross contribution, deductions, net result and closing balance. |
| Allocation and submission | Input digest, prices and conversion policy, baseline and agent allocation, target mapping snapshot, signatures, transaction and activation status. |

Intervals cannot overlap for one resource; eligible occupied time cannot exceed available time. Resources and collateral cannot be counted twice. Validators recompute from the same finalized inputs. Boundary or input-digest disagreement pauses finalization and requires replay. Persist balances in period order so recovery and retries preserve prior settlements.

The November 2026 evidence path still had gaps: CVM ledger lines were platform-signed with no node signature; inference receipts did not prove compute availability; the fixed no-agent Python shopper probe was recognizable. Fresh nonce-bound attestation, roster and service checks, recovery events and recorded probe coverage are needed. Root anchoring and independent validation remained implementation work. No probes is not proof of perfect quality, and a platform signature is not a dual-signed compute receipt.

## 8. Risks we are designing against

| Risk | Defence |
|---|---|
| Fake supply: a machine claims a GPU, TDX or confidential mode it lacks | Class verification at admission and continuously after; nothing earned without it; collateral at stake |
| Self-dealing: a miner buys from itself | Platform assignment of every user and order; catalog-only specifications; bonus eligibility tied to verified identities and capped network-wide; Eleven reads the account graph |
| A sole supplier manufactures demand for a niche specification | Catalog rail; a new specification needs a second supplier or platform-originated demand |
| Eleven misprices or misallocates | Code-enforced rails; baseline published beside every allocation; outcomes scored publicly; people can pause Eleven, and validators then use the baseline |
| Eleven's decisions vary between runs | Median of three independent decisions per tempo; payout cap and rails bound any single mistake |
| A price source is manipulated or wrong | Several sources and a median band; every fetched response hashed into the signed trace. Confidential-machine prices rest on thin public data, and that is published with each price |
| Miners try to persuade or manipulate Eleven | Everything miners or users write is data, never instruction; every input is in the published trace, so attempts are visible |
| A class proves unverifiable in practice | Classes are added one at a time with adversarial tests, and can be suspended by the same review |

## 9. What the product shows

- **Users:** each resource's class, specification, verification record, status and cost.
- **Providers:** per resource, the class, specification, admission status, contribution, occupancy, orders taken and retirement status; per account, period contribution, deductions, outstanding penalties and settlements.
- **Funds:** required collateral, locked collateral, the minimum floor, headroom eligible for release, and amounts already unlocked, with "safe to shut down" clearly separate from "withdrawal complete."
- **Public record:** every request class Eleven could not serve, every order, every allocation statement beside its baseline, every proposal and every decision.

## 10. Launch gates and open parameters

Before Eleven's weights go live:

1. **Shadow mode.** Eleven publishes its allocation beside the baseline, computed from real SN11 records, for several weeks.
2. **The catalog rail implemented in the platform and validator code.** The simulation described above tests the policy, not its production enforcement.
3. **Open mechanism review items resolved:** emission recycling against chain weight normalization, enforcement of the exit reservation and of debts, occupancy-bonus eligibility in production, consistency between the price band and the payout cap, and order quote versus settlement terms.

Published before launch, proposed by Eleven with evidence and decided by people: final specifications, the rails (band width, maximum move per tempo, concentration cap), the price sources, collateral amounts, penalty caps, order-book rules and exit parameters. Example amounts in this document are not rules in force.

The launch review must also fix finality thresholds, evidence deadlines, dispute adjudication and compensation rules; the contribution/debt unit and migration policy; zero-result and incompatible-rail handling; admission and assignment evidence; actual collateral-entry release terms; and the maximum delay before penalties affect every relevant release path. Publish responsible owners and approval records for these decisions.

Verify the whole settlement path before accepting collateral-backed supply. Required cases include duplicate resource claims, concurrent expansion, restart-safe allowances and debt, key swaps and reused UIDs, cross-period faults, reversed penalties, early floor reductions, emission from old weights or validator dividends, partial retirement and full exit with zero user demand. Stress the release plan under lower emission and lower alpha value. Neither local model checks nor attestation establish the economic safety of the deployed system.

At the November 2026 design snapshot, existing scoring paths used verified ledger amounts and strike counts, or capacity time with probe discounts. They did not implement the full trusted bonus, persistent coldkey debt or collateral lifecycle described here. Native-period tracking, idle-capacity records, fault attribution, reservation enforcement, replayable finalization and chain submission require integration. Passing prototype component tests or changing one scoring function does not establish deployment of this mechanism.

## 11. What comes next

1. **Eleven's front door:** the request API and conversation, starting with sandboxes.
2. **Eleven's allocation in shadow mode**, then live within the rails.
3. **Machine classes:** confidential CPU machines, then confidential GPU machines, each with its verification method and order book.
4. **Sealed judges and hidden benchmarks** open to miners and builders.
5. **Proof of improvement on chain:** every change to SN11, and every improvement claimed on it, with evidence anyone can recompute.

The subnet is designed to be hosted, priced and improved in public by an agent, under a constitution people wrote. Every step it takes can be checked, including the ones that fail.
