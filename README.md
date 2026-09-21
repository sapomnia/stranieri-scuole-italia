# Il tetto del 30%: alunni stranieri nelle scuole italiane (a.s. 2024/25)

Quante classi delle scuole primarie e secondarie di primo grado statali superano il 30% di alunni con cittadinanza non italiana, la soglia indicata dalla circolare ministeriale n. 2 dell'8 gennaio 2010.

**Pagina interattiva:** https://sapomnia.github.io/stranieri-scuole-italia/
Si sceglie regione, provincia, comune e scuola e si vede quanti anni di corso superano il 30%, con il confronto con provincia, regione e Italia.

## Contenuto

| File | Cosa contiene |
|---|---|
| `index.html` | La pagina interattiva (dati incorporati, nessuna dipendenza oltre ai Google Fonts) |
| `Scuole_stranieri_oltre30_nonUE_2024-25.xlsx` | Stranieri = solo cittadini extra-UE |
| `Scuole_stranieri_oltre30_UE_e_nonUE_2024-25.xlsx` | Stranieri = tutti i cittadini non italiani (UE ed extra-UE) |
| `build.py` | Genera i due file Excel |
| `web/prep_web.py`, `web/template.html` | Generano `index.html` |
| `ALUITASTRACITSTA20242520250831.csv` | MIM, alunni per cittadinanza, scuola e anno di corso |
| `SCUANAGRAFESTAT20242520250831.csv` | MIM, anagrafica delle scuole statali |
| `istat/` | Elenchi Istat di regioni, province e comuni con i codici |

Ogni file Excel ha due fogli:
- **Province**: per primarie e secondarie di primo grado, numero di plessi e quota di quelli con almeno un anno di corso oltre il 30% e con il totale del plesso oltre il 30%.
- **Scuole**: elenco dei plessi oltre soglia con indirizzo, comune, provincia, regione, codici Istat e percentuali per anno di corso.

## Metodo

- **Classi = anni di corso.** Il MIM non pubblica i dati per singola sezione ma per anno di corso (tutte le prime, tutte le seconde… di un plesso). Un anno di corso supera il tetto se gli stranieri sono più del 30% degli iscritti.
- Due criteri: *almeno un anno di corso oltre il 30%* e *totale del plesso oltre il 30%*.
- Nessuna soglia minima di alunni: nei plessi piccoli bastano pochi alunni per superare il 30%.
- Solo scuole statali; Valle d'Aosta e Trentino-Alto Adige non sono coperti dal dataset MIM.
- Le province sarde sono quelle usate dal MIM (assetto pre-2025, con Sud Sardegna), con i codici Istat allora in vigore.

## Riprodurre

```bash
pip install openpyxl
python3 build.py          # file Excel
python3 web/prep_web.py   # index.html
```

## Fonti

- Ministero dell'Istruzione e del Merito, [Portale unico dei dati della scuola](https://dati.istruzione.it/opendata/) — licenza IODL 2.0
- Istat, codici delle unità amministrative territoriali
