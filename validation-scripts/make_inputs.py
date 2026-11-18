"""Step 1 of the validation report: one input folder per history year, in output/validation-runs/.

    python validation-scripts/make_inputs.py [year ...] [--gams GAMS]      (default: 2016-2025)

Each input-y<year>/ holds the model's text files as they are now in inputData/ and that year's
workbook, converted with the gdxxrw of the GAMS that --gams names (else BB_GAMS, else the gams on
PATH). Convert with the GAMS that will run the years. The workbooks come first and are made in
Excel, because only Excel recalculates them: workbooks/HelsinkiDHC-inputData-original.xlsx is a copy of
inputData/HelsinkiDHC-inputData.xlsx, and workbooks/HelsinkiDHC-inputData-y<year>.xlsx is that
copy with RunSetup C5 (unit year), C9 (price year) and C13 (time series year) set to the year and
D13 = E13 = 1, recalculated in full. From PowerShell in the model folder, in a private Excel that
opens the workbook read-only (run gdxxrw only after this Excel has quit):

    $workbooks = "$PWD\\output\\validation-runs\\workbooks"
    $original = "$workbooks\\HelsinkiDHC-inputData-original.xlsx"
    $xl = New-Object -ComObject Excel.Application; $xl.DisplayAlerts = $false
    $wb = $xl.Workbooks.Open($original, 0, $true); $ws = $wb.Worksheets.Item("RunSetup")
    foreach ($y in 2016..2025) {
      "C5","C9","C13" | ForEach-Object { $ws.Range($_).Value2 = [double]$y }
      $ws.Range("D13").Value2 = [double]1; $ws.Range("E13").Value2 = [double]1
      $xl.CalculateFull()                     # C19 must read "ok" and C28 stay empty
      $wb.SaveCopyAs("$workbooks\\HelsinkiDHC-inputData-y$y.xlsx") }
    $wb.Close($false); $xl.Quit()
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

MODEL = Path(__file__).resolve().parents[1]
REPO = next(p for p in MODEL.parents if (p / "Backbone.gms").is_file())
sys.path.insert(0, str(REPO))
from scripts.gams_api import GAMS_FLAG, GAMS_KWARGS, gams_tool_path, select_gams  # noqa: E402

ROUND = MODEL / "output" / "validation-runs"
SRC = MODEL / "inputData"
FILES = ["1_options.gms", "changes.inc", "modelsInit.gms", "scheduleInit.gms", "timeAndSamples.inc"]

parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("years", nargs="*", type=int, metavar="year",
                    help="history years to convert (default: 2016-2025)")
parser.add_argument(*GAMS_FLAG, **GAMS_KWARGS)
args = parser.parse_args()
YEARS = args.years or list(range(2016, 2026))
GDXXRW = gams_tool_path(select_gams(args.gams), "gdxxrw")
if not GDXXRW.is_file():
    sys.exit(f"gdxxrw not found at {GDXXRW}: name a GAMS with --gams or BB_GAMS, or put one on PATH")

failed = 0
for y in YEARS:
    dst = ROUND / f"input-y{y}"
    dst.mkdir(parents=True, exist_ok=True)
    for f in FILES:
        shutil.copy2(SRC / f, dst / f)
    xlsx = ROUND / "workbooks" / f"HelsinkiDHC-inputData-y{y}.xlsx"
    gdx = dst / "inputData.gdx"
    if gdx.exists():
        gdx.unlink()
    s = time.time()
    rc = subprocess.run([str(GDXXRW), f"Input={xlsx}", f"Output={gdx}", "Index=INDEX!",
                         f"Log={ROUND / 'workbooks' / f'gdxxrw-y{y}.log'}"], capture_output=True).returncode
    ok = rc == 0 and gdx.exists()
    failed += not ok
    print(f"y{y} gdxxrw exit {rc}, {'ok' if ok else 'FAILED'}, {time.time() - s:.0f} s", flush=True)
sys.exit(1 if failed else 0)
