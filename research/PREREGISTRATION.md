# Pre-registration: LLM ATT&CK classification experiment

**Committed to git before the LLM was run on any evaluation sample.** The commit
timestamp is the evidence that the ground truth, the metrics and the prompt
variants below were fixed before outputs were seen, and were not adjusted
afterwards. Any deviation found necessary later is to be recorded in a dated
"Deviations" section at the bottom, not by editing the sections above.

## Question

Given the anomaly event SENTINEL's classifier actually receives, how often does
the local LLM (`gemma4:e2b` via Ollama) name a MITRE ATT&CK technique consistent
with the attack that produced the traffic?

## Ground truth

Attack classes and their definitions are quoted verbatim from the dataset
authors (Meidan et al., IEEE Pervasive Computing 17(3), 2018, §"Experimental
setup"). The mapping to ATT&CK is ours, made from those definitions alone.

| Botnet | Class | Definition (Meidan et al., verbatim) | Category |
|---|---|---|---|
| BASHLITE | scan | "Scanning the network for vulnerable devices" | DISCOVERY |
| BASHLITE | junk | "Sending spam data" | DOS |
| BASHLITE | udp | "UDP flooding" | DOS |
| BASHLITE | tcp | "TCP flooding" | DOS |
| BASHLITE | combo | "Sending spam data and opening a connection to a specified IP address and port" | DOS |
| Mirai | scan | "Automatic scanning for vulnerable devices" | DISCOVERY |
| Mirai | ack | "Ack flooding" | DOS |
| Mirai | syn | "Syn flooding" | DOS |
| Mirai | udp | "UDP flooding" | DOS |
| Mirai | udpplain | "UDP flooding with fewer options, optimized for higher PPS" | DOS |

Accepted technique IDs per category. The classifier's system prompt asks for
"MITRE ATT&CK for ICS/IoT", so equivalent techniques from BOTH the Enterprise
and the ICS matrices are accepted — penalising the model for choosing the matrix
its own prompt names would measure the prompt, not the model. A sub-technique
counts if its parent is accepted (e.g. T1498.001 via T1498).

| Category | Enterprise | ICS |
|---|---|---|
| DISCOVERY | T1046 Network Service Discovery · T1595 Active Scanning (incl. .001 Scanning IP Blocks, .002 Vulnerability Scanning) · T1018 Remote System Discovery | T0846 Remote System Discovery · T0840 Network Connection Enumeration · T0888 Remote System Information Discovery |
| DOS | T1498 Network Denial of Service (incl. .001 Direct Network Flood) · T1499 Endpoint Denial of Service (incl. .001 OS Exhaustion Flood, .002 Service Exhaustion Flood) | T0814 Denial of Service |

Accepted tactic names, for the coarser tactic-level metric (case-insensitive,
substring match): DISCOVERY → {discovery, reconnaissance}; DOS → {impact,
inhibit response function}.

## Samples

* 20 attack windows per class × 10 classes = **200 windows**, drawn with a fixed
  seed (0) uniformly from every device that has that attack class, from both the
  in-distribution and the held-out devices.
* Each window's anomaly score comes from the reproducible LSTM autoencoder
  (seed 0), so the prompt carries the score the pipeline would really produce.

## Prompt variants (the only manipulated variable)

1. **AS-BUILT** — `sentinel/agents/classifier/gemma_client.py` unchanged. It
   receives device, vendor, IPs, protocol, anomaly score, alert level, CVEs and
   IP reputation, but *not* any traffic statistics.
2. **EVIDENCE** — identical, plus a five-line traffic summary computed from the
   window's own Kitsune features (definitions from the N-BaIoT dataset
   documentation), each labelled in plain English:
   * packets/rate from this host — `MI_dir_L0.1_weight`
   * mean packet size (bytes) — `MI_dir_L0.1_mean`
   * approx. active destination hosts — `H_L0.1_weight / HH_L0.1_weight`
   * approx. active sockets (host:port pairs) — `H_L0.1_weight / HpHp_L0.1_weight`
   * channel jitter mean — `HH_jit_L0.1_mean`
   Values are taken from the LAST row of the window (the most recent packet).

Held constant across both variants, to avoid leaking the label:
* `protocol` = "unknown". N-BaIoT provides no per-packet protocol, and deriving
  it from the attack name (e.g. "udp") would hand the model the answer.
* IPs are RFC 5737 documentation addresses; `vendor` is the N-BaIoT device name.
* Threat-intelligence enrichment is disabled ("Not checked"): the lookups are
  external network calls that would add latency noise and send addresses to
  third parties, and these addresses have no reputation to find.
* Model `gemma4:e2b`, Ollama `format: json`, default sampling, one call per window.

## Metrics

1. **Technique accuracy** — predicted `technique_id` in the accepted set for the
   window's category.
2. **Tactic accuracy** — predicted `tactic` matches the category's accepted names.
3. **Valid-JSON rate** — response parses as JSON *and* has all six schema keys.
   A malformed response counts as wrong for (1) and (2) — that is how the
   deployed pipeline treats it (it drops the event).
4. **Latency** — wall-clock per call, reported as median and p95.

Reported per variant, per category and per class, with Wilson 95% intervals.

## Clarifications (added before any LLM output was seen)

Implementation details the sections above left open, fixed now — before a single
evaluation sample has been sent to the model — rather than chosen after seeing
results:

1. **Multiple technique IDs.** If `technique_id` contains more than one ATT&CK
   ID, the FIRST one is graded as the model's primary answer. Grading "any of
   them" would reward a model for hedging with a list.
2. **Flagged subset.** Samples are drawn uniformly per class regardless of
   whether the LSTM would flag them, as specified. Because the deployed
   pipeline only forwards FLAGGED windows to the classifier, results are ALSO
   reported on the flagged subset (score > the LSTM's threshold). The
   unconditional numbers remain the primary result.
3. **Evidence placement.** The EVIDENCE block is inserted immediately before
   the prompt's `TASK:` line, after the as-built anomaly fields, so the as-built
   text is otherwise byte-identical between variants.
4. **Order.** The 400 (sample, variant) calls run in one order shuffled with
   seed 0, interleaving the variants so that any drift in the model's speed or
   behaviour over the run cannot systematically favour one variant. One
   warm-up call loads the model weights and is not scored.

## Exploratory analyses (declared before any LLM output was seen)

Not part of the confirmatory questions above, and to be reported as
EXPLORATORY in any write-up:

1. **Would-block rate.** SENTINEL's response policy (`sentinel/config/policy.yaml`)
   blocks the indicator with no human confirmation when the LLM's `severity` is
   >= 6. The fraction of attack samples receiving severity >= 6 therefore
   estimates how often the pipeline, end to end, would have enforced a block.
   Reported per variant and per category.
2. **Severity and action distributions**, per variant.

## Deviations

*(none yet)*
