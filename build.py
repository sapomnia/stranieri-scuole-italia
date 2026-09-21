"""Genera i due file Excel sulle scuole con classi oltre il 30% di alunni stranieri (a.s. 2024/25).

- Scuole_stranieri_oltre30_nonUE_2024-25.xlsx: stranieri = solo cittadini extra-UE
- Scuole_stranieri_oltre30_UE_e_nonUE_2024-25.xlsx: stranieri = tutti i cittadini non italiani

Ogni file ha tre fogli: Province (quote per provincia, con la riga Italia in fondo),
Scuole (elenco dei plessi oltre soglia) e Note (definizioni, fonti e limiti dei dati).
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.worksheet.worksheet import Worksheet

from common import ANNI_PER_ORDINE, BASE_DIR, SOGLIA_PERCENTUALE, Plesso, carica_plessi

FONT_INTESTAZIONE = Font(name="Arial", size=10, bold=True)
FONT_DATI = Font(name="Arial", size=10)
ALLINEA_SINISTRA = Alignment(horizontal="left")
ALLINEA_DESTRA = Alignment(horizontal="right")
ALLINEA_TESTO_LUNGO = Alignment(horizontal="left", vertical="top", wrap_text=True)

ORDINI = [("Primaria", "Primarie"), ("Secondaria di primo grado", "Secondarie I grado")]


@dataclass(frozen=True)
class Variante:
    """Una delle due definizioni di "straniero" usate per produrre i file."""

    includi_ue: bool
    etichetta: str
    nome_file: str


VARIANTI = [
    Variante(False, "non UE", "Scuole_stranieri_oltre30_nonUE_2024-25.xlsx"),
    Variante(True, "UE e non UE", "Scuole_stranieri_oltre30_UE_e_nonUE_2024-25.xlsx"),
]


def percentuale(parte: int, totale: int) -> float | None:
    return round(parte / totale * 100, 1) if totale else None


# ---------------------------------------------------------------- foglio Province

def righe_province(plessi: list[Plesso], includi_ue: bool) -> tuple[list[str], list[list], list]:
    """Intestazione, righe per provincia e riga di sintesi nazionale."""
    conteggi: dict[tuple, Counter] = defaultdict(Counter)
    for plesso in plessi:
        chiave = (plesso.codice_regione, plesso.provincia, plesso.regione, plesso.codice_provincia)
        conteggio = conteggi[chiave]
        conteggio[plesso.ordine, "plessi"] += 1
        conteggio[plesso.ordine, "anno"] += bool(plesso.anni_oltre_soglia(includi_ue))
        conteggio[plesso.ordine, "totale"] += plesso.totale_oltre_soglia(includi_ue)

    intestazione = ["Regione", "Codice Istat regione", "Provincia", "Codice Istat provincia"]
    for _, etichetta in ORDINI:
        intestazione += [
            f"{etichetta} (n)",
            f"{etichetta} con almeno un anno >30% (n)",
            f"{etichetta} con almeno un anno >30% (%)",
            f"{etichetta} con totale >30% (n)",
            f"{etichetta} con totale >30% (%)",
        ]

    def valori(conteggio: Counter) -> list:
        riga = []
        for ordine, _ in ORDINI:
            totale = conteggio[ordine, "plessi"]
            riga += [
                totale,
                conteggio[ordine, "anno"],
                percentuale(conteggio[ordine, "anno"], totale),
                conteggio[ordine, "totale"],
                percentuale(conteggio[ordine, "totale"], totale),
            ]
        return riga

    righe = []
    for (codice_regione, provincia, regione, codice_provincia), conteggio in sorted(conteggi.items()):
        righe.append([regione, codice_regione, provincia, codice_provincia, *valori(conteggio)])

    nazionale = Counter()
    for conteggio in conteggi.values():
        nazionale.update(conteggio)
    riga_italia = ["Italia", "", "", "", *valori(nazionale)]
    return intestazione, righe, riga_italia


# ---------------------------------------------------------------- foglio Scuole

def righe_scuole(plessi: list[Plesso], variante: Variante) -> tuple[list[str], list[list]]:
    """Intestazione e righe dei plessi con almeno un anno di corso o il totale oltre soglia."""
    intestazione = [
        "Codice scuola", "Denominazione scuola", "Ordine di scuola",
        "Codice istituto di riferimento", "Denominazione istituto di riferimento",
        "Indirizzo", "CAP", "Comune", "Codice Istat comune", "Provincia", "Codice Istat provincia",
        "Regione", "Codice Istat regione", "Alunni (n)",
        f"Alunni stranieri {variante.etichetta} (n)", f"Alunni stranieri {variante.etichetta} (%)",
        "Almeno un anno di corso >30%", "Totale scuola >30%",
        "Anni di corso >30% (n)", "Anni di corso >30%",
        *[f"Stranieri {anno}° anno (%)" for anno in range(1, 6)],
    ]
    righe = []
    for plesso in plessi:
        anni_oltre = plesso.anni_oltre_soglia(variante.includi_ue)
        totale_oltre = plesso.totale_oltre_soglia(variante.includi_ue)
        if not (anni_oltre or totale_oltre):
            continue
        percentuali_anni = []
        for anno in range(1, 6):
            dati = plesso.anni.get(anno)
            valore = dati.percentuale_stranieri(variante.includi_ue) if dati else None
            percentuali_anni.append(round(valore, 1) if valore is not None else None)
        righe.append([
            plesso.codice, plesso.denominazione, plesso.ordine,
            plesso.codice_istituto, plesso.denominazione_istituto,
            plesso.indirizzo, plesso.cap, plesso.comune, plesso.codice_comune,
            plesso.provincia, plesso.codice_provincia, plesso.regione, plesso.codice_regione,
            plesso.alunni(), plesso.stranieri(variante.includi_ue),
            round(plesso.percentuale_stranieri(variante.includi_ue), 1),
            "sì" if anni_oltre else "no", "sì" if totale_oltre else "no",
            len(anni_oltre), ", ".join(map(str, anni_oltre)),
            *percentuali_anni,
        ])
    # Ordine: codice regione, provincia, comune, ordine di scuola, denominazione.
    righe.sort(key=lambda r: (r[12], r[9], r[7], r[2], r[1]))
    return intestazione, righe


# ---------------------------------------------------------------- foglio Note

NOTE_COMUNI = [
    ("Classi e anni di corso",
     "Il Ministero non pubblica i dati per singola sezione (1ª A, 1ª B…) ma per anno di corso: "
     "tutti gli alunni delle prime, delle seconde e così via di uno stesso plesso. Nel file "
     "\"classe\" va quindi letto come \"anno di corso\". È un'approssimazione: una singola "
     "sezione può superare il 30% anche se la media dell'anno di corso è sotto soglia, e viceversa."),
    ("Almeno un anno >30%",
     "Il plesso ha almeno un anno di corso in cui gli stranieri sono più del 30% degli iscritti."),
    ("Totale >30%",
     "Gli stranieri sono più del 30% del totale degli iscritti del plesso. Un plesso con il totale "
     "oltre soglia ha sempre almeno un anno di corso oltre soglia."),
    ("Soglia",
     f"Più del {SOGLIA_PERCENTUALE:.0f}% (strettamente maggiore), come indicato dalla circolare "
     "ministeriale n. 2 dell'8 gennaio 2010."),
    ("Plessi piccoli",
     "Non è applicata alcuna soglia minima di alunni: nei plessi molto piccoli bastano pochi "
     "alunni stranieri per superare il 30%. La colonna Alunni (n) permette di filtrarli."),
    ("Unità di conteggio",
     "Il plesso di un dato ordine (codice scuola). Le percentuali del foglio Province sono "
     "calcolate sul numero di plessi dello stesso ordine presenti nella provincia. La riga Italia, "
     "in fondo, è esclusa dal filtro per non finire in mezzo alle province quando si ordina."),
    ("Copertura",
     "Solo scuole statali. Valle d'Aosta e province autonome di Trento e Bolzano non sono presenti "
     "nei dati del Ministero, che non gestisce direttamente le loro scuole."),
    ("Sardegna",
     "Il Ministero usa ancora le province sarde precedenti alla riforma del 2025 (compresa Sud "
     "Sardegna): sono mantenute con i codici Istat allora in vigore. I codici dei comuni sono "
     "quelli attuali."),
    ("Percentuali",
     "Scritte come numeri da 0 a 100 (38.7 = 38,7%), con l'unità indicata nell'intestazione."),
    ("Fonti",
     "Ministero dell'Istruzione e del Merito, Portale unico dei dati della scuola: studenti per "
     "cittadinanza (ALUITASTRACITSTA20242520250831) e anagrafica scuole statali "
     "(SCUANAGRAFESTAT20242520250831), licenza IODL 2.0. Istat, codici delle unità territoriali."),
]


def righe_note(variante: Variante) -> list[tuple[str, str]]:
    """Voci del foglio Note: contenuto e definizione della variante, poi le note comuni."""
    if variante.includi_ue:
        chi = "tutti gli alunni con cittadinanza non italiana, UE ed extra-UE"
    else:
        chi = "i soli cittadini extra-UE"
    return [
        ("Contenuto",
         "Scuole primarie e secondarie di primo grado statali con classi oltre il 30% di alunni "
         "stranieri, anno scolastico 2024/25."),
        ("Definizione di straniero",
         f"In questo file sono considerati stranieri {chi}. Un file gemello usa l'altra definizione."),
        *NOTE_COMUNI,
    ]


# ---------------------------------------------------------------- scrittura

def formato_numerico(valori: list[Any]) -> str:
    """0 per colonne di interi, 0.0 se basta un decimale, 0.00 altrimenti."""
    numeri = [v for v in valori if isinstance(v, (int, float))]
    if all(float(v).is_integer() for v in numeri):
        return "0"
    if all(round(v, 1) == v for v in numeri):
        return "0.0"
    return "0.00"


def scrivi_tabella(foglio: Worksheet, intestazione: list[str], righe: list[list],
                   colonne_testo: set[str], riga_finale: list | None = None) -> None:
    """Scrive una tabella con intestazione bloccata e filtro; la riga finale resta fuori dal filtro."""
    tutte = righe + ([riga_finale] if riga_finale else [])
    for indice_colonna, titolo in enumerate(intestazione, start=1):
        colonna = [riga[indice_colonna - 1] for riga in tutte]
        numerica = titolo not in colonne_testo and any(isinstance(v, (int, float)) for v in colonna)
        formato = formato_numerico(colonna) if numerica else "@"
        allineamento = ALLINEA_DESTRA if numerica else ALLINEA_SINISTRA

        cella = foglio.cell(row=1, column=indice_colonna, value=titolo)
        cella.font, cella.alignment = FONT_INTESTAZIONE, allineamento
        for indice_riga, valore in enumerate(colonna, start=2):
            if isinstance(valore, float) and formato == "0":
                valore = int(valore)
            cella = foglio.cell(row=indice_riga, column=indice_colonna, value=valore)
            cella.alignment, cella.number_format = allineamento, formato
            cella.font = FONT_INTESTAZIONE if riga_finale and indice_riga == len(tutte) + 1 else FONT_DATI

        larghezza = max([len(titolo)] + [len(str(v)) for v in colonna[:3000] if v is not None])
        foglio.column_dimensions[cella.column_letter].width = min(max(larghezza + 2, 8), 50)

    foglio.freeze_panes = "A2"
    ultima_colonna = foglio.cell(row=1, column=len(intestazione)).column_letter
    foglio.auto_filter.ref = f"A1:{ultima_colonna}{len(righe) + 1}"


def scrivi_note(foglio: Worksheet, note: list[tuple[str, str]]) -> None:
    for colonna, titolo in enumerate(["Voce", "Spiegazione"], start=1):
        cella = foglio.cell(row=1, column=colonna, value=titolo)
        cella.font, cella.alignment = FONT_INTESTAZIONE, ALLINEA_SINISTRA
    for riga, (voce, testo) in enumerate(note, start=2):
        for colonna, valore in enumerate([voce, testo], start=1):
            cella = foglio.cell(row=riga, column=colonna, value=valore)
            cella.font, cella.alignment = FONT_DATI, ALLINEA_TESTO_LUNGO
    foglio.column_dimensions["A"].width = 26
    foglio.column_dimensions["B"].width = 100
    foglio.freeze_panes = "A2"


def genera_file(plessi: list[Plesso], variante: Variante) -> None:
    intestazione_p, righe_p, riga_italia = righe_province(plessi, variante.includi_ue)
    intestazione_s, righe_s = righe_scuole(plessi, variante)

    cartella = Workbook()
    foglio_province = cartella.active
    foglio_province.title = "Province"
    scrivi_tabella(foglio_province, intestazione_p, righe_p,
                   {"Codice Istat regione", "Codice Istat provincia"}, riga_finale=riga_italia)
    scrivi_tabella(cartella.create_sheet("Scuole"), intestazione_s, righe_s,
                   {"Codice scuola", "CAP", "Codice Istat comune", "Codice Istat provincia",
                    "Codice Istat regione", "Anni di corso >30%"})
    scrivi_note(cartella.create_sheet("Note"), righe_note(variante))
    cartella.save(BASE_DIR / variante.nome_file)

    print(f"{variante.nome_file}: {len(righe_s)} plessi in elenco")
    for (ordine, _), inizio in zip(ORDINI, (4, 9)):
        totale, anno, pct_anno, tot_oltre, pct_tot = riga_italia[inizio:inizio + 5]
        print(f"  {ordine}: {totale} plessi, almeno un anno >30%: {anno} ({pct_anno}%), "
              f"totale >30%: {tot_oltre} ({pct_tot}%)")


def main() -> None:
    plessi = carica_plessi()
    senza_codice = sorted({p.comune for p in plessi if not p.codice_comune})
    if senza_codice:
        print("Attenzione, comuni senza codice Istat:", senza_codice)
    for ordine, anni in ANNI_PER_ORDINE.items():
        assert all(max(p.anni) <= anni for p in plessi if p.ordine == ordine)
    for variante in VARIANTI:
        genera_file(plessi, variante)


if __name__ == "__main__":
    main()
