"""Lettura dei dati MIM e abbinamento ai codici Istat, condivisi da build.py e web/prep_web.py.

Il modulo carica gli alunni per cittadinanza e anno di corso delle scuole primarie e
secondarie di primo grado statali, li unisce all'anagrafica delle scuole e attribuisce
a ogni plesso regione, provincia e comune con i relativi codici Istat.
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ISTAT_DIR = BASE_DIR / "istat"
ALUNNI_CSV = BASE_DIR / "ALUITASTRACITSTA20242520250831.csv"
ANAGRAFICA_CSV = BASE_DIR / "SCUANAGRAFESTAT20242520250831.csv"

SOGLIA_PERCENTUALE = 30.0

ORDINI_SCUOLA = {
    "SCUOLA PRIMARIA": "Primaria",
    "SCUOLA SECONDARIA I GRADO": "Secondaria di primo grado",
}
ANNI_PER_ORDINE = {"Primaria": 5, "Secondaria di primo grado": 3}

# Il MIM usa ancora l'assetto sardo precedente al 2025: si usano i codici Istat allora in vigore.
PROVINCE_AGGIUNTIVE = {
    "sassari": ("Sassari", "090"),
    "nuoro": ("Nuoro", "091"),
    "cagliari": ("Cagliari", "292"),
    "oristano": ("Oristano", "095"),
    "sud sardegna": ("Sud Sardegna", "111"),
    "reggio emilia": ("Reggio nell'Emilia", "035"),
    "forli cesena": ("Forlì-Cesena", "040"),
}
ALIAS_REGIONI = {"friuli venezia g.": "friuli venezia giulia"}

# Prefissi dei codici comunali Istat attuali che ricadono in ciascuna vecchia provincia sarda.
PREFISSI_SARDEGNA = {
    "090": {"112", "113"},
    "091": {"114", "116"},
    "292": {"118"},
    "095": {"115"},
    "111": {"114", "116", "117", "118", "119"},
}
# Comuni fusi o rinominati di recente, con il nome usato dall'anagrafica MIM.
ALIAS_COMUNI = {
    "castegnero": "castegnero nanto",
    "nanto": "castegnero nanto",
    "montemagno": "montemagno monferrato",
    "murisengo": "murisengo monferrato",
    "popoli": "popoli terme",
    "puegnago sul garda": "puegnago del garda",
    "san dorligo della valle dolina": "san dorligo della valle",
}


def normalizza(testo: str) -> str:
    """Minuscole, senza accenti, apostrofi e trattini: la chiave per confrontare i nomi."""
    ascii_text = unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode()
    ascii_text = ascii_text.lower().replace("'", " ").replace("-", " ").replace("’", " ")
    return re.sub(r"\s+", " ", ascii_text).strip()


def _leggi_elenco_istat(nome_file: str) -> list[tuple[str, str]]:
    """Restituisce le coppie (denominazione, codice) di un file del cartella istat/."""
    with open(ISTAT_DIR / nome_file, encoding="utf-8", newline="") as handle:
        return [(row["denominazione"], row["codice_istat"]) for row in csv.DictReader(handle)]


class GeoLookup:
    """Abbina i nomi geografici dell'anagrafica MIM alle denominazioni e ai codici Istat."""

    def __init__(self) -> None:
        self.regioni = {normalizza(n): (n, c) for n, c in _leggi_elenco_istat("regioni_istat.csv")}
        self.province = {normalizza(n): (n, c) for n, c in _leggi_elenco_istat("province_istat.csv")}
        self.province.update(PROVINCE_AGGIUNTIVE)
        self.comuni: dict[str, list[tuple[str, str]]] = defaultdict(list)
        for nome, codice in _leggi_elenco_istat("comuni_istat.csv"):
            self.comuni[normalizza(nome)].append((nome, codice))

    def regione(self, nome_mim: str) -> tuple[str, str]:
        chiave = normalizza(nome_mim)
        return self.regioni[ALIAS_REGIONI.get(chiave, chiave)]

    def provincia(self, nome_mim: str) -> tuple[str, str]:
        return self.province[normalizza(nome_mim)]

    @staticmethod
    def _prefissi_comunali(codice_provincia: str) -> set[str]:
        """Prime tre cifre dei codici comunali della provincia (città metropolitane: 2xx → 0xx)."""
        if codice_provincia in PREFISSI_SARDEGNA:
            return PREFISSI_SARDEGNA[codice_provincia]
        if codice_provincia.startswith("2"):
            return {"0" + codice_provincia[1:]}
        return {codice_provincia}

    def comune(self, nome_mim: str, codice_provincia: str) -> tuple[str, str]:
        """Denominazione e codice Istat del comune; codice vuoto se l'abbinamento non riesce."""
        chiave = normalizza(nome_mim)
        chiave = ALIAS_COMUNI.get(chiave, chiave)
        prefissi = self._prefissi_comunali(codice_provincia)
        candidati = [c for c in self.comuni.get(chiave, []) if c[1][:3] in prefissi]
        if not candidati and len(chiave) >= 25:
            # L'anagrafica MIM tronca i nomi lunghi a 30 caratteri.
            candidati = [
                c
                for nome, lista in self.comuni.items()
                if nome.startswith(chiave)
                for c in lista
                if c[1][:3] in prefissi
            ]
        if len(candidati) == 1:
            return candidati[0]
        return nome_mim.title(), ""


@dataclass
class AnnoDiCorso:
    """Alunni di uno stesso anno di corso di un plesso (tutte le sezioni insieme)."""

    anno: int
    alunni: int
    stranieri_ue: int
    stranieri_non_ue: int

    def stranieri(self, includi_ue: bool) -> int:
        return self.stranieri_non_ue + (self.stranieri_ue if includi_ue else 0)

    def percentuale_stranieri(self, includi_ue: bool) -> float | None:
        if not self.alunni:
            return None
        return self.stranieri(includi_ue) / self.alunni * 100


@dataclass
class Plesso:
    """Un plesso scolastico di un dato ordine, con la sua collocazione e i dati per anno di corso."""

    codice: str
    ordine: str
    denominazione: str
    indirizzo: str
    cap: str
    codice_istituto: str
    denominazione_istituto: str
    comune: str
    codice_comune: str
    provincia: str
    codice_provincia: str
    regione: str
    codice_regione: str
    anni: dict[int, AnnoDiCorso] = field(default_factory=dict)

    def alunni(self) -> int:
        return sum(a.alunni for a in self.anni.values())

    def stranieri(self, includi_ue: bool) -> int:
        return sum(a.stranieri(includi_ue) for a in self.anni.values())

    def percentuale_stranieri(self, includi_ue: bool) -> float | None:
        totale = self.alunni()
        return self.stranieri(includi_ue) / totale * 100 if totale else None

    def anni_oltre_soglia(self, includi_ue: bool) -> list[int]:
        """Anni di corso con più del 30% di stranieri (esclusi quelli senza alunni)."""
        return sorted(
            a.anno
            for a in self.anni.values()
            if (p := a.percentuale_stranieri(includi_ue)) is not None and p > SOGLIA_PERCENTUALE
        )

    def totale_oltre_soglia(self, includi_ue: bool) -> bool:
        percentuale = self.percentuale_stranieri(includi_ue)
        return percentuale is not None and percentuale > SOGLIA_PERCENTUALE


def carica_plessi() -> list[Plesso]:
    """Legge i CSV MIM e restituisce i plessi di primaria e secondaria di primo grado.

    L'ordine è quello di prima comparsa nel file degli alunni. Solleva KeyError se un
    codice scuola manca dall'anagrafica o se una regione/provincia non è riconosciuta.
    """
    with open(ANAGRAFICA_CSV, encoding="utf-8-sig", newline="") as handle:
        anagrafica = {row["CODICESCUOLA"]: row for row in csv.DictReader(handle)}

    geo = GeoLookup()
    plessi: dict[tuple[str, str], Plesso] = {}
    with open(ALUNNI_CSV, encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ordine = ORDINI_SCUOLA.get(row["ORDINESCUOLA"])
            if ordine is None:
                continue
            chiave = (row["CODICESCUOLA"], ordine)
            if chiave not in plessi:
                plessi[chiave] = _crea_plesso(row["CODICESCUOLA"], ordine, anagrafica, geo)
            anno = int(row["ANNOCORSO"])
            plessi[chiave].anni[anno] = AnnoDiCorso(
                anno=anno,
                alunni=int(row["ALUNNI"]),
                stranieri_ue=int(row["ALUNNICITTADINANZANONITALIANAPAESIUE"]),
                stranieri_non_ue=int(row["ALUNNICITTADINANZANONITALIANAPAESINONUE"]),
            )
    return list(plessi.values())


def _crea_plesso(codice: str, ordine: str, anagrafica: dict[str, dict], geo: GeoLookup) -> Plesso:
    scheda = anagrafica[codice]
    regione, codice_regione = geo.regione(scheda["REGIONE"])
    provincia, codice_provincia = geo.provincia(scheda["PROVINCIA"])
    comune, codice_comune = geo.comune(scheda["DESCRIZIONECOMUNE"], codice_provincia)
    return Plesso(
        codice=codice,
        ordine=ordine,
        denominazione=scheda["DENOMINAZIONESCUOLA"],
        indirizzo=scheda["INDIRIZZOSCUOLA"],
        cap=scheda["CAPSCUOLA"],
        codice_istituto=scheda["CODICEISTITUTORIFERIMENTO"],
        denominazione_istituto=scheda["DENOMINAZIONEISTITUTORIFERIMENTO"],
        comune=comune,
        codice_comune=codice_comune,
        provincia=provincia,
        codice_provincia=codice_provincia,
        regione=regione,
        codice_regione=codice_regione,
    )
