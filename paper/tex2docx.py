"""Build an editable Word version of the paper (main.docx) from the LaTeX source.

The LaTeX source stays the master copy: numbers come from numbers.tex,
citation and cross-reference numbers from main.aux / main.bbl, so compile the
PDF first. Figures are rendered from the same TikZ/pgfplots sources to PNG.

    cd paper && latexmk
    python3 tex2docx.py           # -> main.docx

Only the LaTeX constructs this paper uses are handled.
"""
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = Path(__file__).resolve().parent
FONT = "Times New Roman"

# ---------------------------------------------------------------- source ---

def strip_comments(s):
    return re.sub(r"(?<!\\)%.*", "", s)


def read_tex(path):
    s = strip_comments(path.read_text())

    def inc(m):
        name = m.group(1)
        if name.startswith("figures/") or name == "numbers":
            return m.group(0)
        return read_tex(HERE / (name + ".tex"))
    return re.sub(r"\\input\{([^}]+)\}", inc, s)


def brace(s, i):
    """s[i] == '{' -> (content, index after closing brace)."""
    assert s[i] == "{", s[i:i + 40]
    depth, j = 0, i
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    raise ValueError("unbalanced braces")


def load_macros():
    s = strip_comments((HERE / "numbers.tex").read_text())
    macros, i = {}, 0
    while (m := re.compile(r"\\newcommand\{\\([A-Za-z]+)\}").search(s, i)):
        body, i = brace(s, m.end())
        macros[m.group(1)] = body
    return macros


def expand(s, macros):
    for _ in range(5):
        s2 = re.sub(r"\\([A-Za-z]+)(\{\})?",
                    lambda m: macros.get(m.group(1), m.group(0)), s)
        if s2 == s:
            return s
        s = s2
    return s


def load_refs():
    aux = (HERE / "main.aux").read_text()
    labels = {}
    for m in re.finditer(r"\\newlabel\{([^}]+)\}\{\{(.*?)\}\{", aux):
        labels[m.group(1)] = re.sub(r"\\mbox\s*\{(.*)\}", r"\1", m.group(2))
    bbl = (HERE / "main.bbl").read_text()
    body = bbl.split("\\BIBdecl", 1)[1].split("\\end{thebibliography}")[0]
    items = re.split(r"\\bibitem\{([^}]+)\}", body)[1:]
    keys = items[0::2]
    texts = [re.sub(r"\s+", " ", t).strip() for t in items[1::2]]
    return labels, {k: n + 1 for n, k in enumerate(keys)}, list(zip(keys, texts))


# ---------------------------------------------------------------- inline ---

SYM = {"&": "&", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}",
       ",": "\u2009", " ": " ", ";": " ", "/": ""}
WORD = {"S": "§", "ldots": "…", "le": "≤", "ge": "≥", "geq": "≥", "leq": "≤",
        "times": "×", "pm": "±", "lambda": "λ", "in": "∈", "dagger": "†",
        "quad": "\u2003", "textbackslash": "\\", "IEEEauthorrefmark": ""}
DROP = {"noindent", "centering", "footnotesize", "scriptsize", "small",
        "relax", "newblock", "BIBentryALTinterwordspacing", "toprule",
        "midrule", "bottomrule", "BIBentrySTDinterwordspacing", "maketitle"}
STYLED = {"emph": "i", "textit": "i", "textbf": "b", "textsc": "sc",
          "textsuperscript": "sup", "text": None, "url": None, "mbox": None}


class Ctx:
    labels, cites = {}, {}
    footnotes = []


def skip_ws(s, i):
    while i < len(s) and s[i] in " \t\n":
        i += 1
    return i


def arg(s, i):
    i = skip_ws(s, i)
    if i < len(s) and s[i] == "{":
        return brace(s, i)
    if s[i] == "\\":
        m = re.match(r"\\([A-Za-z]+|.)", s[i:])
        return m.group(0), i + m.end()
    return s[i], i + 1


def inline(s, st=frozenset(), math=False):
    out = []
    i = 0

    def put(t, style=st):
        out.append((t, style))

    while i < len(s):
        c = s[i]
        if c == "\\":
            m = re.match(r"\\([A-Za-z]+)\*?|\\(.)", s[i:], re.S)
            name, sym = m.group(1), m.group(2)
            i += m.end()
            if sym is not None:
                if sym == "\\":
                    put("\n")
                else:
                    put(SYM.get(sym, sym))
                continue
            if name in WORD:
                rel = math and name in ("in", "le", "ge", "geq", "leq", "times", "pm")
                put(f" {WORD[name]} " if rel else WORD[name])
            elif name in DROP:
                pass
            elif name in STYLED:
                a, i = arg(s, i)
                add = STYLED[name]
                out += inline(a, st | {add} if add else st, math and name != "text")
            elif name in ("cite",):
                a, i = arg(s, i)
                nums = sorted(Ctx.cites[k.strip()] for k in a.split(","))
                put(", ".join(f"[{n}]" for n in nums))
            elif name == "ref":
                a, i = arg(s, i)
                put(Ctx.labels[a])
            elif name == "label":
                _, i = arg(s, i)
            elif name == "footnote":
                a, i = arg(s, i)
                Ctx.footnotes.append(a)
                put(str(len(Ctx.footnotes)), st | {"sup"})
            elif name == "bibinfo":
                _, i = arg(s, i)
                a, i = arg(s, i)
                out += inline(a, st)
            elif name in ("setlength",):
                _, i = arg(s, i)
                _, i = arg(s, i)
            elif name == "multicolumn":
                _, i = arg(s, i)
                _, i = arg(s, i)
                a, i = arg(s, i)
                out += inline(a, st)
            elif name in ("BIBforeignlanguage",):
                _, i = arg(s, i)
            else:
                raise ValueError(f"unhandled command \\{name} near: {s[max(0, i - 40):i + 20]!r}")
        elif c == "{":
            a, i = brace(s, i)
            out += inline(a, st, math)
        elif c == "$":
            j = s.index("$", i + 1)
            out += inline(s[i + 1:j], st, True)
            i = j + 1
        elif math and c in "_^":
            a, i = arg(s, i + 1)
            out += inline(a, st | {"sub" if c == "_" else "sup"}, True)
        elif c == "~":
            put("\u00a0")
            i += 1
        elif s.startswith("---", i):
            put("—")
            i += 3
        elif s.startswith("--", i):
            put("–")
            i += 2
        elif s.startswith("``", i):
            put("“")
            i += 2
        elif s.startswith("''", i):
            put("”")
            i += 2
        elif c == "`":
            put("‘")
            i += 1
        elif c == "'":
            put("’")
            i += 1
        elif math and c in "=<>":
            put(f" {c} ")
            i += 1
        elif math and c == ",":
            put(", ")
            i += 1
        elif c in " \t\n":
            if not math:
                put(" ")
            i = skip_ws(s, i)
        else:
            j = i
            while j < len(s) and s[j] not in "\\{}$~-`' \t\n_^=<>,":
                j += 1
            j = max(j, i + 1)
            put(s[i:j])
            i = j
    # merge runs
    merged = []
    for t, sty in out:
        if merged and merged[-1][1] == sty and t != "\n" and merged[-1][0] != "\n":
            merged[-1] = (merged[-1][0] + t, sty)
        else:
            merged.append((t, sty))
    return [(re.sub(r"\u00a0 +", "\u00a0", re.sub(r" {2,}", " ", t)), sty)
            for t, sty in merged]


def add_runs(p, runs, size=None, bold=False, italic=False, strip=True):
    if strip and runs:
        runs = [(runs[0][0].lstrip(), runs[0][1])] + runs[1:]
        runs = runs[:-1] + [(runs[-1][0].rstrip(), runs[-1][1])]
    after_break = False
    for t, sty in runs:
        if t == "\n":
            p.add_run().add_break()
            after_break = True
            continue
        if after_break:
            t, after_break = t.lstrip(), False
        if not t:
            continue
        r = p.add_run(t)
        r.italic = italic or "i" in sty or None
        r.bold = bold or "b" in sty or None
        if "sc" in sty:
            r.font.small_caps = True
        if "sup" in sty:
            r.font.superscript = True
        if "sub" in sty:
            r.font.subscript = True
        if size:
            r.font.size = Pt(size)
    return p


# ---------------------------------------------------------------- layout ---

def roman(n):
    vals = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
    out = ""
    for v, r in vals:
        while n >= v:
            out, n = out + r, n - v
    return out


def set_cols(section, n, space=0.25):
    sp = section._sectPr
    for c in sp.findall(qn("w:cols")):
        sp.remove(c)
    cols = OxmlElement("w:cols")
    cols.set(qn("w:num"), str(n))
    cols.set(qn("w:space"), str(int(space * 1440)))
    later = [qn("w:" + t) for t in ("formProt", "vAlign", "noEndnote", "titlePg",
                                     "textDirection", "bidi", "rtlGutter", "docGrid")]
    for k, child in enumerate(sp):
        if child.tag in later:
            sp.insert(k, cols)
            return
    sp.append(cols)


def fmt(p, align=WD_ALIGN_PARAGRAPH.JUSTIFY, before=0, after=0, indent=None,
        keep=False):
    pf = p.paragraph_format
    p.alignment = align
    pf.space_before, pf.space_after = Pt(before), Pt(after)
    if indent is not None:
        pf.first_line_indent = Inches(indent)
    if keep:
        pf.keep_with_next = True
    return p


def cell_border(cell, **edges):
    tcPr = cell._tc.get_or_add_tcPr()
    b = tcPr.find(qn("w:tcBorders"))
    if b is None:
        b = OxmlElement("w:tcBorders")
        tcPr.append(b)
    for edge, sz in edges.items():
        e = OxmlElement(f"w:{edge}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), str(sz))
        e.set(qn("w:color"), "000000")
        b.append(e)


def render_figure(name, outdir):
    tex = outdir / f"{name}.tex"
    tex.write_text(rf"""\documentclass[border=4pt]{{standalone}}
\usepackage{{mathptmx}}
\usepackage{{amsmath,amssymb,xcolor,tikz,pgfplots}}
\usetikzlibrary{{arrows.meta,positioning,fit,calc,shapes.geometric}}
\pgfplotsset{{compat=1.17}}
\input{{{HERE}/numbers}}
\begin{{document}}
\setlength{{\columnwidth}}{{252pt}}\setlength{{\linewidth}}{{252pt}}
\resizebox{{252pt}}{{!}}{{\input{{{HERE}/figures/{name}}}}}
\end{{document}}
""")
    subprocess.run(["pdflatex", "-interaction=nonstopmode",
                    f"-output-directory={outdir}", str(tex)], cwd=HERE,
                   check=True, capture_output=True)
    png = outdir / f"{name}.png"
    subprocess.run(["gs", "-q", "-dNOPAUSE", "-dBATCH", "-sDEVICE=png16m",
                    "-r600", "-dTextAlphaBits=4", "-dGraphicsAlphaBits=4",
                    f"-sOutputFile={png}", str(outdir / f"{name}.pdf")],
                   check=True)
    return png


# ------------------------------------------------------------------ build ---

def main():
    macros = load_macros()
    Ctx.labels, Ctx.cites, bib = load_refs()
    src = expand(read_tex(HERE / "main.tex"), macros)
    pre, body = src.split("\\begin{document}", 1)
    body = body.split("\\bibliographystyle")[0]
    tmp = Path(tempfile.mkdtemp())

    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(0)
    for hs, size in (("Heading 1", 10), ("Heading 2", 10)):
        h = doc.styles[hs]
        h.font.name, h.font.size, h.font.bold = FONT, Pt(size), False
        h.font.color.rgb = None
        h.element.rPr.rFonts.set(qn("w:asciiTheme"), "") if False else None
        rf = h.element.rPr.rFonts
        for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
            if rf.get(qn(a)) is not None:
                del rf.attrib[qn(a)]
        rf.set(qn("w:ascii"), FONT)
        rf.set(qn("w:hAnsi"), FONT)

    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    sec.top_margin, sec.bottom_margin = Inches(0.75), Inches(1.0)
    sec.left_margin = sec.right_margin = Inches(0.625)
    set_cols(sec, 1)

    # title + authors (single column)
    title, _ = brace(body, body.index("\\title") + len("\\title"))
    add_runs(fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.CENTER, after=12),
             inline(title), size=24)
    auth, _ = brace(pre + body, (pre + body).index("\\author") + 7)
    for part in ("IEEEauthorblockN", "IEEEauthorblockA"):
        a, _ = brace(auth, auth.index("\\" + part) + len(part) + 1)
        p = fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.CENTER, after=4)
        add_runs(p, inline(a), size=11 if part.endswith("N") else 10,
                 italic=part.endswith("A"))
    doc.add_paragraph()

    new = doc.add_section(WD_SECTION.CONTINUOUS)
    set_cols(new, 2)

    body = body[body.index("\\maketitle") + len("\\maketitle"):]
    tok = re.compile(r"\\(section|subsection|paragraph)\{|"
                     r"\\begin\{(abstract|IEEEkeywords|itemize|enumerate|figure|table)\}")
    nsec = nsub = nfig = ntab = 0
    runin = None
    pos = 0

    def paragraphs(text):
        nonlocal runin
        for chunk in re.split(r"\n\s*\n", text):
            if not chunk.strip():
                continue
            runs = inline(chunk)
            if not "".join(t for t, _ in runs).strip():
                continue
            noind = chunk.lstrip().startswith("\\noindent") or runin is None and False
            p = fmt(doc.add_paragraph(), indent=0 if noind else 0.14)
            if runin is not None:
                add_runs(p, inline(runin) + [(". ", frozenset({"i"}))], italic=True)
                runin = None
            add_runs(p, runs)
            for k, note in enumerate(Ctx.footnotes):
                q = fmt(doc.add_paragraph(), indent=0.14, before=2)
                add_runs(q, [(str(k + 1), frozenset({"sup"}))] + inline(note), size=8)
            Ctx.footnotes.clear()

    while (m := tok.search(body, pos)):
        paragraphs(body[pos:m.start()])
        kind, env = m.group(1), m.group(2)
        if kind:
            t, pos = brace(body, m.end() - 1)
            if kind == "section":
                nsec, nsub = nsec + 1, 0
                p = fmt(doc.add_paragraph(style="Heading 1"),
                        WD_ALIGN_PARAGRAPH.CENTER, before=8, after=4, keep=True)
                add_runs(p, [(f"{roman(nsec)}. ", frozenset({"sc"}))] +
                         [(x, s | {"sc"}) for x, s in inline(t)])
            elif kind == "subsection":
                nsub += 1
                p = fmt(doc.add_paragraph(style="Heading 2"),
                        WD_ALIGN_PARAGRAPH.LEFT, before=6, after=3, keep=True)
                add_runs(p, [(f"{chr(64 + nsub)}. ", frozenset())] + inline(t),
                         italic=True)
            else:
                runin = t
            continue
        end = body.index("\\end{%s}" % env, m.end())
        inner = body[m.end():end]
        pos = end + len("\\end{%s}" % env)
        if env == "abstract":
            p = fmt(doc.add_paragraph(), after=4)
            add_runs(p, [("Abstract", frozenset({"i"})), ("—", frozenset())], size=9, bold=True)
            add_runs(p, inline(inner), size=9, bold=True)
        elif env == "IEEEkeywords":
            p = fmt(doc.add_paragraph(), after=6)
            add_runs(p, [("Index Terms", frozenset({"i"})), ("—", frozenset())], size=9, bold=True)
            add_runs(p, inline(inner), size=9, bold=True)
        elif env in ("itemize", "enumerate"):
            for k, item in enumerate(re.split(r"\\item\b", inner)[1:]):
                p = fmt(doc.add_paragraph())
                p.paragraph_format.left_indent = Inches(0.25)
                p.paragraph_format.first_line_indent = Inches(-0.18)
                mark = "•\t" if env == "itemize" else f"{k + 1})\t"
                p.paragraph_format.tab_stops.add_tab_stop(Inches(0.25))
                add_runs(p, [(mark, frozenset())] + inline(item), strip=False)
        elif env == "figure":
            nfig += 1
            name = re.search(r"\\input\{figures/([^}]+)\}", inner).group(1)
            png = render_figure(name, tmp)
            p = fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.CENTER, before=6, keep=True)
            p.add_run().add_picture(str(png), width=Inches(3.4))
            cap, _ = brace(inner, inner.index("\\caption") + 8)
            p = fmt(doc.add_paragraph(), before=2, after=8)
            add_runs(p, [(f"Fig. {nfig}. ", frozenset())] + inline(cap), size=8)
        elif env == "table":
            ntab += 1
            cap, _ = brace(inner, inner.index("\\caption") + 8)
            p = fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.CENTER, before=8, keep=True)
            add_runs(p, [(f"TABLE {roman(ntab)}", frozenset({"sc"}))], size=8)
            p = fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.CENTER, after=4, keep=True)
            add_runs(p, [(x, s | {"sc"}) for x, s in inline(cap)], size=8)
            tab_start = inner.index("\\begin{tabular}")
            spec, i = brace(inner, tab_start + len("\\begin{tabular}"))
            spec = re.sub(r"[^lcr]", "", spec)
            tbody = inner[i:inner.index("\\end{tabular}")]
            # A rule in the chunk before a row's text is a border above that
            # row; rules in a trailing chunk with no text border the last row.
            RULE = r"\\(toprule|midrule|bottomrule)"
            WEIGHT = {"toprule": 8, "midrule": 4, "bottomrule": 8}
            rows, pending = [], []
            for chunk in re.split(r"\\\\", tbody):
                found = re.findall(RULE, chunk)
                text = re.sub(RULE, "", chunk).strip()
                if text:
                    rows.append([text, pending + found, []])
                    pending = []
                elif rows:
                    rows[-1][2] += found
                else:
                    pending += found
            ncol = len(spec)
            table = doc.add_table(rows=len(rows), cols=ncol)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            align = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER,
                     "r": WD_ALIGN_PARAGRAPH.RIGHT}
            for r, (raw, above, below) in enumerate(rows):
                if raw.startswith("\\multicolumn"):
                    cells = [raw]
                    table.rows[r].cells[0].merge(table.rows[r].cells[-1])
                else:
                    cells = [c.strip() for c in re.split(r"(?<!\\)&", raw)]
                for c in range(ncol if len(cells) > 1 else 1):
                    cell = table.rows[r].cells[c]
                    cp = cell.paragraphs[0]
                    fmt(cp, align[spec[c]] if len(cells) > 1 else WD_ALIGN_PARAGRAPH.LEFT)
                    add_runs(cp, inline(cells[c]), size=8 if len(cells) > 1 else 7)
                    edges = {}
                    if above:
                        edges["top"] = max(WEIGHT[x] for x in above)
                    if below:
                        edges["bottom"] = max(WEIGHT[x] for x in below)
                    if edges:
                        cell_border(cell, **edges)
            doc.add_paragraph().paragraph_format.space_after = Pt(4)
    paragraphs(body[pos:])

    # references
    p = fmt(doc.add_paragraph(style="Heading 1"), WD_ALIGN_PARAGRAPH.CENTER,
            before=8, after=4, keep=True)
    add_runs(p, [("References", frozenset({"sc"}))])
    for n, (key, text) in enumerate(bib, 1):
        p = fmt(doc.add_paragraph(), WD_ALIGN_PARAGRAPH.LEFT, after=2)
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.first_line_indent = Inches(-0.3)
        p.paragraph_format.tab_stops.add_tab_stop(Inches(0.3))
        add_runs(p, [(f"[{n}]\t", frozenset())] + inline(text), size=8, strip=False)

    zoom = doc.settings.element.find(qn("w:zoom"))
    if zoom is not None:
        zoom.set(qn("w:percent"), "100")

    out = HERE / "main.docx"
    doc.save(out)
    print("wrote", out)


if __name__ == "__main__":
    sys.exit(main())
