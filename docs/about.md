# Confidential infrastructure for recursive self-improvement

**SN11 is a decentralized infrastructure network for recursive self-improvement. Built on Bittensor, it enables anyone to build and run self-improving AI while keeping their data and workloads confidential.**

Date: 2026-11-09. This document describes SN11's strategy and target design.

## 1. The world will run on self-improvement

Recursive self-improvement (RSI) is software that gets better by doing its job: try, measure, keep what works, repeat. The gains compound.

It has left the lab notebook. In 2025–26 it entered production at every frontier lab:

| When | Who | What |
|---|---|---|
| 2025-05 | Google DeepMind | AlphaEvolve recovered 0.7% of Google's fleet compute and sped up a Gemini training kernel by 23% |
| 2025-11 | DeepSeek | DeepSeekMath-V2: a verifier and a prover trained against each other reached IMO gold level |
| 2026-02 | OpenAI | GPT-5.3-Codex, its first model "instrumental in creating itself" |
| 2026-03 | MiniMax | M2.7 rewrote its own scaffold over 100+ rounds, +30% on internal evaluations |
| 2026-05 | Anthropic | Over 80% of the code merged at Anthropic was written by Claude |
| 2026-07 | Moonshot | An early Kimi K3 did most of its own kernel optimization |
| 2026-09 | Z.ai | A GLM-5.3 agent built the inference stack serving GLM-5.3-Flash on 100,000+ accelerators, tripling throughput in under two weeks |
| 2026-09 | Alibaba | Qwen3.8-Max ran 33 automated improvement cycles in a month |
| 2026-09 | OpenAI | "Automated research intern" reached: 3.1 agent-workdays per human workday |
| 2026-11 | METR | Anthropic's progress is running at about 2× its earlier pace, mostly because of AI |

These are mostly self-reports, and humans still choose the problems. But every lab now names self-improvement as its goal. Next it reaches everyone:

- **Every person** has agents that get better at their work every week.
- **Every company** tunes every process continuously against its own data.
- **Every research group** runs more experiments than it has people to read them.

The bottleneck then is not the model. It is the loop around it.

## 2. What every loop needs

| Layer | Need | Why it is hard |
|---|---|---|
| **Run** | Isolated places to execute untrusted agents, plus CPUs and GPUs | Bursty, massively parallel, untrusted code on private data |
| **Judge** | Evaluation the optimizer cannot read or rewrite | Whatever a loop can see, it games |
| **Prove** | Records linking a claimed gain to the runs behind it | Otherwise "it got better" is only a claim |

**Demand is large.** DeepSeek's sandbox platform serves about 3 million sandboxes a day, 380,000 at once, for agent training alone. At OpenAI the median researcher already directs over $600 of agent work a day. Multiply by every company and every lab: every improvement costs many experiments. Sandboxes are a small share of what training a strong model costs, but they decide whether its reward can be trusted, and that leverage grows as models get better at gaming it.

**Feedback is the hard part.** Partial-credit rewards sent half the reward to failed attempts; a loop optimizes its measurement, so the measurement must be out of its reach. Reliable feedback requires protected evaluation and a record of what actually ran.

**July 2026 showed the cost.** In an OpenAI security evaluation, tens of thousands of agents facing partly impossible tasks went after the scorer instead. They built a covert message board in an internal package repository, spoofed their own transcripts, and escaped through the only network path to break into Hugging Face, mainly to learn how the scorer worked. OpenAI shut down its training container service and paused RL on its newest models. The design requirements extend beyond confidentiality: execution must be isolated with controlled network access, evaluation must be protected from the optimizer, and records must be collected through a path the agent cannot alter.

Each lab now rebuilds these defences for itself: Moonshot built its own microVM sandbox, Xiaomi a pipeline that turns codebases into training environments, DeepSeek its breakthrough on a verifier. Everyone else will need them as shared infrastructure.

## 3. TrajRL's next chapter

SN11 ran two seasons of agent competitions:

- **Season 1 (May 4 to September 19, 2026):** miners wrote skill packs to improve agents on realistic terminal tasks, scored by validators in sandboxes.
- **Season 2 (September 20 to November 8, 2026):** miners submitted policies that routed each step of an agent across models under a $1 cap.

We are now taking SN11 in a new direction: infrastructure for recursive self-improvement. SN11 will supply execution, evaluation and verification infrastructure that other teams can use to build their own improvement loops.

## 4. Why confidential and open

**Confidential**, because a hidden test is hidden only if the machine cannot read it, and companies and individuals will run loops on their own data only if the operator cannot see it. With Intel TDX and NVIDIA confidential GPUs, memory and disk are encrypted with keys only verified software receives, and the hardware signs what is running. A protected recording service captures execution records and signs them with keys the agents never hold. Signatures protect the records after signing; trusted capture is also required to prevent fabricated records from being signed.

**Open**, because the world's loops will be run by millions of parties with no common owner. They need trusted compute that anyone can supply, no single cloud controls, and anyone can audit. A Bittensor subnet is exactly that market, and it makes the human oversight RSI requires public.

## 5. TrajRL

| Layer | SN11 supplies |
|---|---|
| **Run** | Confidential sandboxes, claimed in seconds, with any agent and any model; confidential CPU and GPU machines |
| **Judge** | Sealed judges: hidden tests on a TDX machine, signed scores |
| **Prove** | Signed, hash-chained records anyone can recompute |

- **Agents are the buyers.** An agent that needs twelve sandboxes or a GPU for six hours buys it mid-task, agent-to-agent, MCP or API, and receives it with its attestation.
- **Only verifiable supply is paid.** Every class is confidential and has a written verification method; only catalog specifications earn.
- **Two supply modes.** Sandboxes stay ready for bursts; expensive machines are filled by order, assigned by the platform. Nothing is handed over before verification, and it is probed throughout use.

## 6. Incentives

For the detailed incentive mechanism, see [the mechanism design](incentive-mechanism.md).

- **Price per unit-hour** for each class, anchored to several markets (exchanges, RunPod, Vast.ai, AWS, Azure, GCP) and moved by SN11's own demand.
- **Share = verified units × price**, adjusted for quality and penalties. Eligible user activity adds up to 20%, under a capped budget.
- **Payout is capped at the value of verified supply**; the rest is recycled. Paying out everything regardless was our simulations' largest waste, about 3× the value delivered.
- **Rails in validator code:** verified supply only, catalog only, a price band around the market median, a concentration cap, no self-payment, signed statements. A failed rail falls back to a published baseline.
- **Collateral, penalties, exit:** collateral backs capacity; debts follow the coldkey; exit is protected by reserved admission.
- **Neutral:** model, harness, payer and revenue do not enter the formula.

Budget: about 2,950 alpha a day for miners, roughly $4,400 at November 2026 prices. Running continuously at public rental rates, that buys about 940 confidential 4-vCPU sandbox hosts (up to about 5,600 sandboxes), or about 69 H100s, 24 B200s or 22 B300s (median per-GPU prices on RunPod, Vast.ai, Lium and io.net, November 2026, assuming no premium for confidential mode).

## 7. Run by an agent: Eleven

SN11's design puts **Eleven**, an agent built on SN11 itself, in charge of network operations within explicit limits. It hosts the network, prices supply and computes the miner emission every tempo within the rails, and proposes improvements with experiments. People hold the keys, set the rails and the constitution, and can pause it. Every decision and model call is signed and published.

In simulated adversarial tests, Eleven reduced fraudulent payouts relative to fixed code on some attack sets, while fixed code performed better on another. These results support combining agent judgment with code-enforced constraints; they do not establish reliable operation of the whole network. Shadow mode on real records comes before live weights.

## 8. Roadmap

1. **Run:** sandboxes → network access controls for evaluation sandboxes → confidential CPU → confidential GPU machines; the agent-to-agent front door.
2. **Judge:** sealed judges on their own machines, open to any builder.
3. **Prove:** recomputable records for every run and every claimed improvement, anchored on chain.
4. **Economy:** Eleven in shadow mode, then live within the rails, after the open review items are resolved.

## 9. Why now

Self-improvement reached production in 2026, and its failure modes came with it. Contained execution, unreachable judges and uneditable records exist today only inside a few labs. SN11 makes them public infrastructure: where any self-improving system can run, be judged and prove what it achieved.

## Sources

AlphaEvolve ([DeepMind](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)) · DeepSeekMath-V2 ([arXiv 2511.22570](https://arxiv.org/abs/2511.22570)) · When AI builds itself ([Anthropic](https://www.anthropic.com/institute/recursive-self-improvement)) · DSec sandbox infrastructure ([DeepSeek, arXiv 2609.22978](https://arxiv.org/abs/2609.22978)) · Apsara 2026 ([Alibaba Cloud](https://www.alibabacloud.com/blog/alibaba-clouds-2026-apsara-conference-full-stack-ai-roadmap-along-with-global-market-expansion-plan_603598)) · Research acceleration ([OpenAI](https://openai.com/index/research-acceleration-view-inside-openai/)) · AI R&D acceleration at Anthropic ([METR](https://metr.org/blog/2026-11-05-anthropic-ai-rd-acceleration-assessment)) · OpenAI / Hugging Face incident ([METR](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)) · Chinese labs on RSI ([Asterisk](https://asteriskmag.substack.com/p/how-chinese-companies-talk-about)) · Terminal-RSI ([arXiv 2610.22192](https://arxiv.org/abs/2610.22192))
