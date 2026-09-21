"""Prepara i dati di tutti i plessi e genera index.html (la pagina interattiva) a partire da template.html."""
import json, re, collections as C
from pathlib import Path
WEB = Path(__file__).parent
src = (WEB.parent / "build.py").read_text()
exec(src[:src.index("non_match = []")].replace("Path(__file__).parent", "WEB.parent"))  # riusa mappature regioni/province/comuni e letture CSV

MINUSCOLE = {"di", "del", "della", "delle", "dello", "dei", "degli", "da", "dal", "dalla", "e", "ed", "in", "a", "al",
             "alla", "alle", "ai", "agli", "con", "per", "su", "sul", "sulla", "tra", "fra", "lo", "la", "le", "il", "gli"}
ROMANI = re.compile(r"^(?=[IVXLC]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")

def bello(s):
    out = []
    for i, w in enumerate(s.split()):
        core = w.strip('"().,-')
        if ROMANI.match(core.upper()) and core.upper() == core and len(core) > 0 and core not in ("C", "L", "D", "V"):
            out.append(w); continue
        if re.fullmatch(r"([A-Z]\.){2,}[A-Z]?\.?", w):  # sigle tipo I.C. / S.M.S.
            out.append(w); continue
        t = w.lower()
        if i > 0 and t in MINUSCOLE:
            out.append(t); continue
        t = re.sub(r"(^|[\"'(\-./])([a-zàèéìòù])", lambda m: m.group(1) + m.group(2).upper(), t)
        out.append(t)
    return " ".join(out)

reg_l, prov_l, com_l = [], [], []
reg_i, prov_i, com_i = {}, {}, {}
per_scuola = C.OrderedDict()
for r in righe:
    k = (r["CODICESCUOLA"], ORDINI[r["ORDINESCUOLA"]])
    d = per_scuola.setdefault(k, {})
    d[int(r["ANNOCORSO"])] = [int(r["ALUNNI"]), int(r["ALUNNICITTADINANZANONITALIANAPAESIUE"]),
                              int(r["ALUNNICITTADINANZANONITALIANAPAESINONUE"])]

scuole = []
for (cod, ordine), anni in per_scuola.items():
    an = ana[cod]
    reg = REG[REG_ALIAS.get(norm(an["REGIONE"]), norm(an["REGIONE"]))][0]
    pv = PROV[norm(an["PROVINCIA"])]
    com = comune(an["DESCRIZIONECOMUNE"], pv[1])[0]
    if reg not in reg_i: reg_i[reg] = len(reg_l); reg_l.append(reg)
    pk = (reg, pv[0])
    if pk not in prov_i: prov_i[pk] = len(prov_l); prov_l.append([pv[0], reg_i[reg]])
    ck = (pk, com)
    if ck not in com_i: com_i[ck] = len(com_l); com_l.append([com, prov_i[pk]])
    n = 5 if ordine == "Primaria" else 3
    scuole.append([com_i[ck], bello(an["DENOMINAZIONESCUOLA"]), 0 if ordine == "Primaria" else 1,
                   bello(an["INDIRIZZOSCUOLA"]), cod, [anni.get(y, [0, 0, 0]) for y in range(1, n + 1)]])

for s in scuole:
    s[1] = s[1].replace("F.Lli", "F.lli"); s[3] = s[3].replace("F.Lli", "F.lli")
data = {"r": reg_l, "p": prov_l, "c": com_l, "s": scuole}

# scuola mostrata all'apertura: primaria di Prato (provincia con la quota più alta) con più anni oltre soglia
prato = next(i for i, p in enumerate(prov_l) if p[0] == "Prato")
def chiave(s):
    a = sum(y[0] for y in s[5]); st = sum(y[1] + y[2] for y in s[5])
    return (sum(1 for y in s[5] if y[0] and (y[1] + y[2]) / y[0] > .3), -abs(st / a - .5), a)
start = max((s for s in scuole if com_l[s[0]][1] == prato and s[2] == 0), key=chiave)[4]

html = (WEB / "template.html").read_text()
html = html.replace("__DATA__", json.dumps(data, ensure_ascii=False, separators=(",", ":"))).replace("__START__", start)
# intestazione HTML completa per GitHub Pages (il modello contiene solo il corpo della pagina)
testa = '<!doctype html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n'
(WEB.parent / "index.html").write_text(testa + html)
print(f"index.html: {len(scuole)} plessi, {len(com_l)} comuni, scuola iniziale {start}")
