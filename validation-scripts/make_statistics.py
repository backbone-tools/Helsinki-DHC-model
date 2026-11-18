"""Cut statistics.csv, the statistics the validation report reads, from validation/validation_long.csv.

    python validation-scripts/make_statistics.py        (needs validation/, which is not published)

statistics.csv keeps every row that comparison.py reads into a number on the page, as it is in the
long table: year, city, entity, table, metric, category, value, unit, source. source is
"file | sheet | cell [column]" in the original workbook; readme.md names the publications. Run it
again after validation_long.csv is rebuilt or comparison.py reads something new: a row the cube
lacks reads as nan or 0, not as an error.
"""
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import comparison  # noqa: E402

LONG = HERE.parent / "validation" / "validation_long.csv"
OUT = HERE / "statistics.csv"
YEARS = range(2016, 2026)

raw = pd.read_csv(LONG, dtype=str, keep_default_na=False)  # written back exactly as read
no_model = pd.DataFrame(dict(year=list(YEARS), city="", metric="", category="", value=0.0))
comparison.read.clear()
long = pd.read_csv(LONG)
comparison.build(no_model, long)  # every statistics reader runs and records its rows
keep = set(comparison.read)

# A derived row cites rows, not cells. Keep the Taul1 rows it is computed from, so that every value
# here traces to a cell: Espoo network deliveries = Espoo 1.6 minus Kauniainen and Kirkkonummi 1.3.
FORTUM = "Fortum Power and Heat Oy, "
OUT_DELIV, BOUGHT = "heat delivered to other DH companies", "heat purchased from other DH companies"
derived = long.loc[sorted(keep)].query("table == 'derived'")
if set(derived.metric) - {OUT_DELIV}:
    raise SystemExit(f"comparison.py reads derived rows this script does not trace: {set(derived.metric)}")
for y, value in zip(derived.year, derived.value):
    t1 = long[(long.table == "Taul1") & (long.year == y)]
    out_ = t1[(t1.entity == FORTUM + "Espoo") & (t1.metric == OUT_DELIV)]
    internal = t1[t1.entity.isin([FORTUM + "Kauniainen", FORTUM + "Kirkkonummi (keskusta)"]) & (t1.metric == BOUGHT)]
    if abs(out_.value.sum() - internal.value.sum() - value) > 1e-6:
        raise SystemExit(f"{y}: derived Espoo deliveries {value} do not follow from the Taul1 rows")
    keep |= set(out_.index) | set(internal.index)

cube = raw.loc[sorted(keep)]
cube.to_csv(OUT, index=False, lineterminator="\n")
print(f"wrote {OUT}: {len(cube)} of {len(raw)} rows")
print(cube.groupby("table").size().to_string())
