# Reference verification log

Every citation in `paper/refs.bib` was checked against its publisher or an
authoritative registry on **2026-09-25**. Metadata (authors, venue, volume,
pages, DOI) was copied from that source, not from memory or from the earlier
literature review. Add nothing to `refs.bib` without doing the same.

## Verified

| Key | Checked against | Notes |
|---|---|---|
| meidan2018nbaiot | Crossref DOI 10.1109/MPRV.2018.03367731; dataset README | Author order per Crossref. Attack definitions quoted from the paper text. |
| mirsky2018kitsune | Crossref DOI 10.14722/ndss.2018.23204 | |
| kitsunepy | GitHub repo + LICENSE (MIT) | Vendored as `sentinel/agents/anomaly/afterimage.py` with notice. |
| neto2023ciciot | Crossref DOI 10.3390/s23135941 | |
| antonakakis2017mirai | usenix.org paper page | pp. 1093–1110, 19 authors. |
| huang2020iotinspector | Crossref DOI 10.1145/3397333 | **Old review said "IMC 2020" — wrong; it is Proc. ACM IMWUT 4(2).** |
| lear2019mud | Crossref DOI 10.17487/RFC8520 | |
| hochreiter1997lstm | Crossref DOI 10.1162/neco.1997.9.8.1735 | |
| liu2008iforest | Crossref DOI 10.1109/ICDM.2008.17 | |
| wilson1927 | Crossref DOI 10.1080/01621459.1927.10502953 | For confidence intervals. |
| sommer2010closedworld | Crossref DOI 10.1109/SP.2010.25 | |
| arp2022dosdonts | usenix.org paper page | pp. 3971–3988. |
| engelen2021cicids | Crossref DOI 10.1109/SPW53761.2021.00009 | |
| guan2023honeyiot | Crossref DOI 10.1145/3558482.3590195 | |
| heiding2020honeypot | Crossref DOI 10.5220/0008954704240431 | **Prior work on honeypot-driven blocking for IoT — the old review's "Gap 5" claimed this loop was novel. It is not.** |
| hadi2024ikern | Crossref DOI 10.3390/technologies12080122 | |
| zhang2024ebpf | Crossref DOI 10.1109/DSN58291.2024.00048 | Peer-reviewed; replaces weaker eBPF citations. |
| tolay2025ebpf | arxiv.org/abs/2508.00851 | Preprint (submitted to IEEE IoT-J). Cited as preprint. |
| xu2025llmsec | Crossref DOI 10.1145/3769676 | Published in ACM TOSEM 2025. |
| roy2025agenticcyber | arxiv.org/abs/2512.06396 | Preprint, single author, **Dec 2025** (old review said 2024). Uses cloud Gemini. |
| roy2023sok | arxiv.org/abs/2304.07411 | Preprint. |
| alsada2023attack | arxiv.org/abs/2308.14016 | Preprint. **Reviews "more than fifty" works — old review said 417.** |
| gemma4 | ai.google.dev/gemma/docs/core | Official model docs. `ollama show`: 5.1B params, Q4_K_M, temp 1.0. |
| software entries | project homepages | Cowrie, OpenCanary, Ollama, LangGraph, ONNX Runtime, nftables, OTX, AbuseIPDB, ATT&CK. |

## Rejected from the earlier literature review (`project-req/RESEARCH_PAPERS.md`)

| Old entry | Why it is not cited |
|---|---|
| Paper 15, "Edge IDS on Raspberry Pi 5" (IAEME) | IAEME is widely listed as a predatory publisher. Kitsune (NDSS 2018) is a peer-reviewed Pi-class edge-IDS reference instead. |
| Paper 19, "ATT&CK Applications" (ResearchGate) | ResearchGate is a hosting site, not a venue; appears to duplicate Paper 12. |
| Papers with "Authors: Various" (2, 4, 6, 7, 10, 11, 16, 20) | Not verified this session. Each must be traced to a real author list and venue before it can be cited. |
| "UNSW Cowrie Dataset" | Could not be verified to exist (already flagged in EVALUATION_PLAN.md). Never cite. |
| Claims of the form "SENTINEL is the first…" / "no published paper does X" | Unverifiable novelty claims. Removed; the paper states contributions positively instead. |

## Claims in the old review contradicted by the code

These are not citation errors but they came from the same document, which
described the design (`extracted_content.txt`) rather than the built system:
per-device models (there is one global model); an Isolation-Forest cold-start
path (absent); a transparent L2 bridge (not implemented); an LLM-driven response
planner (the responder is a deterministic policy graph); QLoRA-fine-tuned Gemma
(stock `gemma4:e2b`); "no data leaves the device" (remote IPs go to OTX and
AbuseIPDB); "runs on Raspberry Pi 5" (never tested on one).
