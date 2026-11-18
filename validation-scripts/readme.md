# validation-scripts

Builds `../HelsinkiDHC-validation.html`: the 2016-2025 history runs against the statistics.

**Statistics** are in `statistics.csv` here: every row the report reads, each with its `source` as
`file | sheet | cell [column]` in these publications.

| `source` file | Publication |
|---|---|
| `kl-tilasto <year> ...xlsx`, 2017-2025 | Energiateollisuus ry, Kaukolämpötilasto, yearly tables, [energia.fi](https://energia.fi/tilastot/kaukolampotilastot/kaukolammitys-ja-jaahdytys/); `paivitetty` in a name marks a revised edition |
| `kl-tilasto-2016.xlsx` | the same for 2016, read from an .xlsx conversion of `kl-tilasto 2016 Vuositaulukot16_netti.xls` |
| `Laitoskohtaiset tiedot vuosien 2013-2025 päästöistä.xlsx` | Energiavirasto, verified EU ETS emissions per installation, [päästökaupan julkaisut](https://energiavirasto.fi/paastokaupan-julkaisut) |
| `derived from Taul1 rows ...` | computed from Taul1 rows of the same year, which are in the file too |

[statistics-notes.md](statistics-notes.md) has the entities, definitions and known doubts.
`make_statistics.py` cuts the file from `validation/validation_long.csv`, which is not in git, nor
are the workbooks. Run it again after that table is rebuilt or `comparison.py` reads something new.

**Run files it needs**, not in git, under the model folder:

- `output/validation-runs/runs/y2016` ... `y2025`, each with `results.gdx`, `info.txt`,
  `warnings.log` and `sweep_cell.json`. The rest of a run folder (`debug.gdx`, `Backbone.lst`,
  `gams_scratch/`) is not read.
- `output/validation-runs/input-y2016` ... `input-y2025`, each with `inputData.gdx` (the hourly heat
  supply the run was given: heat sold plus network losses).
- `output/validation-runs/workbooks/HelsinkiDHC-inputData-original.xlsx` (only its save time).

**Regenerate**, from the model folder, with a Python environment that runs Backbone's own scripts
(the model folder must sit inside a Backbone folder, v3.15 or higher):

    python validation-scripts/build_validation.py

Without the runs, first `make_inputs.py` (after the workbook copies its docstring describes), then
`run_years.py`, then `build_validation.py`. `make_inputs.py` and `run_years.py` take `--gams` to
name the GAMS, and `run_years.py` takes `--solver`, and `--workers` to run several years at once;
`--help` lists the rest.
