"""Genera index.html, la pagina interattiva, a partire da web/template.html e dai dati MIM.

La pagina contiene tutti i plessi statali di primaria e secondaria di primo grado, in un
JSON compatto incorporato nel modello al posto del segnaposto __DATA__.
"""

from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(WEB_DIR.parent))

from common import BASE_DIR, SOGLIA_PERCENTUALE, Plesso, carica_plessi  # noqa: E402

# (modello, pagina generata): la seconda versione usa i colori e i font di mappine
PAGINE = [
    (WEB_DIR / "template.html", BASE_DIR / "index.html"),
    (WEB_DIR / "template_mappine.html", BASE_DIR / "mappine" / "index.html"),
]
LOGO = WEB_DIR / "logo-mappine.webp"  # incorporato nella pagina come data URI
PROVINCIA_INIZIALE = "Prato"  # la provincia con la quota più alta: la pagina si apre lì

# Il modello contiene solo il corpo della pagina; per GitHub Pages serve l'intestazione completa.
INTESTAZIONE_HTML = (
    '<!doctype html>\n<html lang="it">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
)

PAROLE_MINUSCOLE = {
    "di", "del", "della", "delle", "dello", "dei", "degli", "da", "dal", "dalla", "e", "ed", "in",
    "a", "al", "alla", "alle", "ai", "agli", "con", "per", "su", "sul", "sulla", "tra", "fra",
    "lo", "la", "le", "il", "gli",
}
NUMERO_ROMANO = re.compile(r"^(?=[IVXLC]+$)M*(C[MD]|D?C{0,3})(X[CL]|L?X{0,3})(I[XV]|V?I{0,3})$")
SIGLA = re.compile(r"([A-Z]\.){2,}[A-Z]?\.?")
INIZIO_PAROLA = re.compile(r"(^|[\"'(\-./])([a-zàèéìòù])")


def maiuscole_minuscole(testo: str) -> str:
    """Converte un nome dal tutto maiuscolo MIM a maiuscole e minuscole all'italiana.

    Lascia invariati numeri romani (XXIII) e sigle puntate (I.C.), mette in minuscolo
    articoli e preposizioni non iniziali.
    """
    parole = []
    for posizione, parola in enumerate(testo.split()):
        nucleo = parola.strip('"().,-')
        if nucleo not in {"C", "L", "D", "V"} and NUMERO_ROMANO.match(nucleo) and nucleo.isupper():
            parole.append(parola)
        elif SIGLA.fullmatch(parola):
            parole.append(parola)
        elif posizione > 0 and parola.lower() in PAROLE_MINUSCOLE:
            parole.append(parola.lower())
        else:
            parole.append(INIZIO_PAROLA.sub(lambda m: m.group(1) + m.group(2).upper(), parola.lower()))
    return " ".join(parole).replace("F.Lli", "F.lli")


def dati_compatti(plessi: list[Plesso]) -> dict:
    """Regioni, province, comuni e plessi come liste indicizzate, per contenere il peso della pagina.

    Ogni plesso è [indice comune, nome, ordine (0 primaria, 1 secondaria), indirizzo, codice,
    [[alunni, stranieri UE, stranieri extra-UE] per ogni anno di corso]].
    """
    regioni: list[str] = []
    province: list[list] = []
    comuni: list[list] = []
    indice_regione: dict[str, int] = {}
    indice_provincia: dict[tuple, int] = {}
    indice_comune: dict[tuple, int] = {}
    scuole = []

    for plesso in plessi:
        if plesso.regione not in indice_regione:
            indice_regione[plesso.regione] = len(regioni)
            regioni.append(plesso.regione)
        chiave_provincia = (plesso.regione, plesso.provincia)
        if chiave_provincia not in indice_provincia:
            indice_provincia[chiave_provincia] = len(province)
            province.append([plesso.provincia, indice_regione[plesso.regione]])
        chiave_comune = (chiave_provincia, plesso.comune)
        if chiave_comune not in indice_comune:
            indice_comune[chiave_comune] = len(comuni)
            comuni.append([plesso.comune, indice_provincia[chiave_provincia]])

        numero_anni = 5 if plesso.ordine == "Primaria" else 3
        anni = []
        for anno in range(1, numero_anni + 1):
            dati = plesso.anni.get(anno)
            anni.append([dati.alunni, dati.stranieri_ue, dati.stranieri_non_ue] if dati else [0, 0, 0])
        scuole.append([
            indice_comune[chiave_comune],
            maiuscole_minuscole(plesso.denominazione),
            0 if plesso.ordine == "Primaria" else 1,
            maiuscole_minuscole(plesso.indirizzo),
            plesso.codice,
            anni,
        ])
    return {"r": regioni, "p": province, "c": comuni, "s": scuole}


def plesso_iniziale(plessi: list[Plesso]) -> str:
    """Primaria della provincia iniziale con più anni oltre soglia (a parità: quota vicina al 50%)."""
    def punteggio(plesso: Plesso) -> tuple:
        quota = plesso.percentuale_stranieri(includi_ue=True) or 0
        return (len(plesso.anni_oltre_soglia(includi_ue=True)), -abs(quota - 50), plesso.alunni())

    candidati = [p for p in plessi if p.provincia == PROVINCIA_INIZIALE and p.ordine == "Primaria"]
    return max(candidati, key=punteggio).codice


def main() -> None:
    plessi = carica_plessi()
    dati = dati_compatti(plessi)
    iniziale = plesso_iniziale(plessi)
    dati_json = json.dumps(dati, ensure_ascii=False, separators=(",", ":"))
    logo = "data:image/webp;base64," + base64.b64encode(LOGO.read_bytes()).decode()
    for modello_file, output in PAGINE:
        modello = modello_file.read_text(encoding="utf-8")
        for segnaposto in ("__DATA__", "__START__", "__SOGLIA__"):
            if segnaposto not in modello:
                raise ValueError(f"Segnaposto {segnaposto} mancante in {modello_file.name}")
        pagina = (
            modello.replace("__DATA__", dati_json)
            .replace("__START__", iniziale)
            .replace("__SOGLIA__", f"{SOGLIA_PERCENTUALE:g}")
            .replace("__LOGO__", logo)
        )
        output.parent.mkdir(exist_ok=True)
        output.write_text(INTESTAZIONE_HTML + pagina, encoding="utf-8")
        print(f"{output.relative_to(BASE_DIR)}: {len(dati['s'])} plessi, {len(dati['c'])} comuni, pagina iniziale {iniziale}")


if __name__ == "__main__":
    main()
