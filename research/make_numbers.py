"""
Generate paper/numbers.tex (LaTeX macros) and paper/figures/*.csv from the
result files. Every number in the paper comes from here; missing results render
as a bold ?? so they cannot pass unnoticed.

    python3 research/make_numbers.py
"""
import glob, json, math, os, re
import numpy as np

R = os.path.join(os.path.dirname(os.path.abspath(__file__)), "results")
P = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paper")
M = {}                                               # macro name -> latex text
MISSING = r"\textbf{??}"


def pct(x, d=1): return f"{100 * x:.{d}f}\\%"
def load(p):
    try: return json.load(open(p))
    except Exception: return None


def auc(neg, pos):
    """Mann-Whitney AUC: P(score_attack > score_benign), ties half."""
    neg, pos = np.asarray(neg, float), np.asarray(pos, float)
    if not len(neg) or not len(pos): return float("nan")
    allv = np.concatenate([neg, pos]); r = allv.argsort().argsort().astype(float) + 1
    # average ranks for ties
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, weights=r); r = (sums / cnt)[inv]
    return (r[len(neg):].sum() - len(pos) * (len(pos) + 1) / 2) / (len(neg) * len(pos))


def summarise(res):
    """Pooled window-level metrics for one model result file."""
    b = res["benign"]; a = res["attack"]; thr = res["threshold"]
    def fpr(group):
        vs = [v for v in b.values() if v["group"] == group]
        return sum(v["fpr"] * v["n"] for v in vs) / sum(v["n"] for v in vs)
    out = {"fpr_in": fpr("in_dist"), "fpr_out": fpr("held_out")}
    tot = sum(v["n"] for v in a.values()); out["tpr"] = sum(v["tpr"] * v["n"] for v in a.values()) / tot
    cls = {}
    for v in a.values():
        k = f"{v['botnet']}/{v['attack']}"; c = cls.setdefault(k, [0.0, 0])
        c[0] += v["tpr"] * v["n"]; c[1] += v["n"]
    out["cls"] = {k: h / n for k, (h, n) in cls.items()}
    atk = np.concatenate([v["scores"] for v in a.values()])
    out["auc_in"] = auc(np.concatenate([v["scores"] for v in b.values() if v["group"] == "in_dist"]), atk)
    out["auc_out"] = auc(np.concatenate([v["scores"] for v in b.values() if v["group"] == "held_out"]), atk)
    out["n_attack"] = tot
    out["fpr_dev"] = {d: v["fpr"] for d, v in b.items()}
    return out


def ms(vals, d=2, as_pct=True):
    vals = np.asarray(vals, float)
    f = 100 if as_pct else 1; unit = "\\%" if as_pct else ""
    if len(vals) == 1: return f"{f*vals[0]:.{d}f}{unit}"
    return f"{f*vals.mean():.{d}f}{unit}\\,$\\pm$\\,{f*vals.std(ddof=1):.{d}f}{unit}"


# ---- deployed ---------------------------------------------------------------
dep = load(f"{R}/res_deployed.json")
if dep:
    s = summarise(dep); M["NdeplThr"] = f"{dep['threshold']:.5f}"
    M["NdeplFPRout"] = pct(s["fpr_out"], 2); M["NdeplTPR"] = pct(s["tpr"], 1)
    M["NdeplMissedShare"] = pct(1 - s["tpr"], 1)
    M["NdeplTcp"] = pct(s["cls"]["gafgyt/tcp"], 2); M["NdeplUdp"] = pct(s["cls"]["gafgyt/udp"], 2)
    M["NdeplAUCout"] = f"{s['auc_out']:.3f}"
    M["NdeplPhilipsFPR"] = pct(s["fpr_dev"]["Philips_B120N10_Baby_Monitor"], 2)
    M["NdeplEnnioFPR"] = pct(s["fpr_dev"]["Ennio_Doorbell"], 2)
    M["NattackWindows"] = f"{s['n_attack']:,}".replace(",", "{,}")
    bash = [v for v in dep["attack"].values() if v["botnet"] == "gafgyt" and v["attack"] in ("tcp", "udp")]
    M["NblindShare"] = pct(sum(v["n"] for v in bash) / s["n_attack"], 1)
    DEP = s
M["NprovRows"] = "322{,}064"

# ---- retrained models + baselines ------------------------------------------
fam = {}
for name in ("lstm", "dense", "iforest"):
    runs = [load(p) for p in sorted(glob.glob(f"{R}/colab/{name}_seed*.json"))]
    runs = [r for r in runs if r]
    if runs: fam[name] = [summarise(r) for r in runs]
tag = {"lstm": "lstm", "dense": "dense", "iforest": "iso"}
for name, ss in fam.items():
    t = tag[name]; M[f"N{t}Seeds"] = str(len(ss))
    for key, mac in (("fpr_in", "FPRin"), ("fpr_out", "FPRout"), ("tpr", "TPR")):
        M[f"N{t}{mac}"] = ms([x[key] for x in ss], 2)
    M[f"N{t}AUCin"] = ms([x["auc_in"] for x in ss], 3, as_pct=False)
    M[f"N{t}AUCout"] = ms([x["auc_out"] for x in ss], 3, as_pct=False)
    for c in ("gafgyt/tcp", "gafgyt/udp"):
        M[f"N{t}{'Tcp' if c.endswith('tcp') else 'Udp'}"] = ms([x["cls"][c] for x in ss], 2)
def blind_cost(res):
    """FPR on in-distribution benign at the threshold that would catch half of
    the BASHLITE tcp/udp windows (their median score) — what detecting them costs."""
    blind = np.concatenate([v["scores"] for v in res["attack"].values()
                            if v["botnet"] == "gafgyt" and v["attack"] in ("tcp", "udp")])
    other = np.concatenate([v["scores"] for v in res["attack"].values()
                            if not (v["botnet"] == "gafgyt" and v["attack"] in ("tcp", "udp"))])
    ben_in = np.concatenate([v["scores"] for v in res["benign"].values() if v["group"] == "in_dist"])
    ben_all = np.concatenate([v["scores"] for v in res["benign"].values()])
    thr = np.median(blind)
    return {"cost_fpr_in": float((ben_in > thr).mean()), "cost_fpr_all": float((ben_all > thr).mean()),
            "auc_blind": auc(ben_all, blind), "auc_other": auc(ben_all, other)}
if "lstm" in fam:
    bc = [blind_cost(load(p)) for p in sorted(glob.glob(f"{R}/colab/lstm_seed*.json"))]
    M["NblindCostFPRin"] = ms([b["cost_fpr_in"] for b in bc], 1)
    M["NblindCostFPRall"] = ms([b["cost_fpr_all"] for b in bc], 1)
    M["NblindAUC"] = ms([b["auc_blind"] for b in bc], 3, as_pct=False)
    M["NotherAUC"] = ms([b["auc_other"] for b in bc], 3, as_pct=False)
    for k, v in bc[0].items(): print(f"  seed0 {k}: {v:.4f}")
if "lstm" in fam:
    ss = fam["lstm"]
    M["NlstmFPRratio"] = f"{np.mean([x['fpr_out'] for x in ss]) / np.mean([x['fpr_in'] for x in ss]):.1f}"

# per-attack table + figure data
CLASSES = ["mirai/scan", "mirai/ack", "mirai/syn", "mirai/udp", "mirai/udpplain",
           "gafgyt/scan", "gafgyt/junk", "gafgyt/combo", "gafgyt/tcp", "gafgyt/udp"]
LABEL = {c: ("M" if c.startswith("mirai") else "B") + "-" + c.split("/")[1].replace("udpplain", "udpplain") for c in CLASSES}
os.makedirs(f"{P}/figures", exist_ok=True)
with open(f"{P}/figures/per_attack.csv", "w") as f:
    f.write("cls,label,deployed,lstm,lstmsd,dense,iforest\n")
    for i, c in enumerate(CLASSES):
        dv = DEP["cls"][c] * 100 if dep else float("nan")
        mean = lambda n: np.mean([x["cls"][c] for x in fam[n]]) * 100 if n in fam else float("nan")
        sd = np.std([x["cls"][c] for x in fam["lstm"]], ddof=1) * 100 if "lstm" in fam and len(fam["lstm"]) > 1 else 0
        f.write(f"{i},{LABEL[c]},{dv:.3f},{mean('lstm'):.3f},{sd:.3f},{mean('dense'):.3f},{mean('iforest'):.3f}\n")

rows = []
for c in CLASSES:
    cells = [f"{DEP['cls'][c]*100:.1f}" if dep else MISSING]
    for n in ("lstm", "dense", "iforest"):
        cells.append(f"{np.mean([x['cls'][c] for x in fam[n]])*100:.1f}" if n in fam else MISSING)
    bot, atk = c.split("/")
    rows.append(f"{'Mirai' if bot=='mirai' else 'BASHLITE'} & {atk} & " + " & ".join(cells) + r" \\")
M["TperAttackRows"] = "\n".join(rows)

# ---- latency -----------------------------------------------------------------
lat = load(f"{R}/latency_stages.json")
if lat:
    fmt = lambda k: f"{lat[k]['median_ms']:.3f}"
    M["NlatExtract"] = fmt("1_feature_extraction_per_packet"); M["NlatInfer"] = fmt("2_anomaly_inference_per_window")
    M["NlatBus"] = fmt("5_redis_bus_hop"); M["NlatPolicy"] = fmt("4_response_policy")
    per_pkt = lat["1_feature_extraction_per_packet"]["median_ms"] + lat["2_anomaly_inference_per_window"]["median_ms"]
    M["NlatDetectPkt"] = f"{per_pkt:.3f}"; M["NdetectPPS"] = f"{1000/per_pkt:,.0f}".replace(",", "{,}")
otx = load(f"{R}/otx_latency.json"); probe = load(f"{R}/intel_probe.json")
if otx:
    full = [x for x in otx["full"] if x] + ([probe["otx_s"]] if probe and probe.get("otx_status") == "ok" else [])
    gen = [x for x in otx["general"] if x]
    M["NotxFullMed"] = f"{np.median(full):.1f}"; M["NotxFullMax"] = f"{max(full):.0f}"; M["NotxFullMin"] = f"{min(full):.1f}"
    M["NotxFullN"] = str(len(full)); M["NotxGenMed"] = f"{np.median(gen):.2f}"; M["NotxGenN"] = str(len(gen))
    M["NotxSpeedup"] = f"{np.median(full)/np.median(gen):.0f}"
if probe: M["NabuseS"] = f"{probe['abuseipdb_s']:.2f}"

# ---- extractor parity --------------------------------------------------------
par = load(f"{R}/parity.json")
if par:
    M["NparPackets"] = f"{par['packets']:,}".replace(",", "{,}")
    names = [("MI_dir == H", "Mih"), ("HH_weight <= H_wt", "Hw"), ("radius >= std^2", "Rad"),
             ("magnitude >= |mean|", "Mag"), ("|pcc| <= 1 (all)", "Pcc")]
    for key, t in names:
        M[f"NparNew{t}"] = pct(par["new"][key], 2); M[f"NparOld{t}"] = pct(par["old"][key], 2)
    M["NparNewPccN"] = f"{par['new']['pcc_distinct']:,}".replace(",", "{,}"); M["NparOldPccN"] = str(par["old"]["pcc_distinct"])

wu = load(f"{R}/llm_warmup.json")
if wu: M["NllmCold"] = f"{wu['cold_start_s']:.1f}"
enf = load(f"{R}/enforce_latency.json")
if enf:
    M["NenfBlock"] = f"{enf['block']['median_ms']:.1f}"; M["NenfUnblock"] = f"{enf['unblock']['median_ms']:.1f}"
    M["NenfBlockP"] = f"{enf['block']['p95_ms']:.1f}"

# ---- LLM ---------------------------------------------------------------------
def wilson(k, n, z=1.96):
    if n == 0: return (float("nan"),) * 3
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0, c - h), min(1, c + h)
def wfmt(k, n): p, lo, hi = wilson(k, n); return f"{100*p:.1f}\\% [{100*lo:.1f}, {100*hi:.1f}]"
llm = load(f"{R}/llm_results.json")
if llm:
    res = llm["results"]; samp = {s["id"]: s for s in load(f"{R}/colab/llm_samples.json")["samples"]}
    M["NllmN"] = str(len(res))
    for v, t in (("AS_BUILT", "Asb"), ("EVIDENCE", "Evi")):
        rs = [r for r in res if r["variant"] == v]; n = len(rs)
        M[f"Nllm{t}N"] = str(n)
        M[f"Nllm{t}Tech"] = wfmt(sum(r["technique_ok"] for r in rs), n)
        M[f"Nllm{t}Tac"] = wfmt(sum(r["tactic_ok"] for r in rs), n)
        M[f"Nllm{t}Json"] = pct(np.mean([r["valid_json"] for r in rs]), 1)
        for cat, ct in (("DISCOVERY", "Disc"), ("DOS", "Dos")):
            cr = [r for r in rs if r["category"] == cat]
            M[f"Nllm{t}Tech{ct}"] = wfmt(sum(r["technique_ok"] for r in cr), len(cr))
        fl = [r for r in rs if samp[r["id"]]["flagged"]]
        M[f"Nllm{t}TechFlag"] = wfmt(sum(r["technique_ok"] for r in fl), len(fl)); M["NllmFlagN"] = str(len(fl))
        sev = []
        for r in rs:
            try: sev.append(float(json.loads(r["raw"]).get("severity")))
            except Exception: sev.append(float("nan"))
        sev = np.asarray(sev)
        M[f"Nllm{t}Block"] = wfmt(int(np.nansum(sev >= 6)), n)
        from collections import Counter
        top = Counter(r["technique"] for r in rs if r["technique"]).most_common(3)
        M[f"Nllm{t}TopTech"] = ", ".join(f"{k} ({c})" for k, c in top)
    # Latency from LOCAL calls only (PREREGISTRATION.md, Deviations): the cloud
    # GPU's timing does not represent the appliance.
    allr = res
    M["NllmCtwoShare"] = pct(np.mean(["command and control" in (r["tactic"] or "").lower() for r in allr]), 1)
    M["NllmImpactN"] = str(sum("impact" in (r["tactic"] or "").lower() for r in allr))
    sev_all = []
    for r in allr:
        try: sev_all.append(float(json.loads(r["raw"]).get("severity")))
        except Exception: pass
    M["NllmSevNineShare"] = pct(np.mean(np.asarray(sev_all) >= 9), 1)
    lat_llm = np.asarray([r["latency_s"] for r in res if r.get("host", "local") == "local"])
    M["NllmLatN"] = str(len(lat_llm))
    for h, t in (("local", "Loc"), ("colab-t4", "Cloud")):             # per-host accuracy check
        hr = [r for r in res if r.get("host", "local") == h]
        M[f"Nllm{t}N"] = str(len(hr)); M[f"Nllm{t}Tech"] = wfmt(sum(r["technique_ok"] for r in hr), len(hr))
    M["NllmLatMed"] = f"{np.median(lat_llm):.1f}"; M["NllmLatP"] = f"{np.percentile(lat_llm, 95):.1f}"

# ---- write -------------------------------------------------------------------
USED = set(re.findall(r"\\(N[A-Za-z]+|T[A-Za-z]+)\b", "".join(open(f).read() for f in glob.glob(f"{P}/sections/*.tex"))))
with open(f"{P}/numbers.tex", "w") as f:
    f.write("% GENERATED by research/make_numbers.py from research/results — do not edit.\n")
    for k in sorted(USED | set(M)):
        f.write(f"\\newcommand{{\\{k}}}{{{M.get(k, MISSING)}}}\n")
missing = sorted(k for k in USED if k not in M)
print(f"wrote {len(M)} macros; used-but-missing ({len(missing)}): {missing}")
