"""Step 2 of the validation report: the history runs, into output/validation-runs/runs/y<year>/.

    python validation-scripts/run_years.py [year ...] [--gams GAMS] [--solver SOLVER]
                                           [--workers N] [--cpus LIST] [--dry-run] [--force] [--hours H]

One calendar-year schedule run a year (365 daily solves from 1 January), each on the input folder
make_inputs.py wrote for it, on one solver thread. --gams and --solver choose as Backbone's
scripts/run_backbone.py does: else BB_GAMS and BB_SOLVER, else the gams on PATH and the first
usable solver. Use the GAMS whose gdxxrw converted the inputs. --workers runs that many years
at once (default 1), each with its own solver licence and memory, and --cpus holds every run on
those logical processors, such as 0-3. A year that already finished clean is skipped; after any
change to the inputs, --force. A year takes some minutes.
"""
import argparse
import sys
from pathlib import Path

MODEL = Path(__file__).resolve().parents[1]
REPO = next(p for p in MODEL.parents if (p / "Backbone.gms").is_file())
sys.path.insert(0, str(REPO))
from scripts.gams_api import GAMS_FLAG, GAMS_KWARGS, SOLVER_FLAG, SOLVER_KWARGS  # noqa: E402
from scripts.run_backbone import _set_cpus, cpus_problem, parse_cpus  # noqa: E402
from scripts.sweep_backbone import Cell, run_driver  # noqa: E402

ROUND = MODEL / "output" / "validation-runs"
REL = ROUND.relative_to(REPO).as_posix()

parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
parser.add_argument("years", nargs="*", type=int, metavar="year",
                    help="history years to run (default: 2016-2025)")
parser.add_argument(*GAMS_FLAG, **GAMS_KWARGS)
parser.add_argument(*SOLVER_FLAG, **{**SOLVER_KWARGS,
                                     "help": "solver to run with, e.g. CPLEX. Overrides BB_SOLVER."})
parser.add_argument("--workers", type=int, default=1, help="how many years run at once (default 1)")
parser.add_argument("--cpus", default=None, metavar="LIST",
                    help="hold every run on these logical processors, such as 0-3")
parser.add_argument("--dry-run", action="store_true", help="list the runs, start none")
parser.add_argument("--force", action="store_true", help="run again the years that finished clean")
parser.add_argument("--hours", type=float, default=None, help="wall-clock budget for the batch")
args = parser.parse_args()
years = args.years or list(range(2016, 2026))

cells = [Cell(f"y{y}", [f"--input_dir={REL}/input-y{y}", "--input_file_gdx=inputData.gdx",
                        "--init_file=scheduleInit.gms", "--debug=1", "--startDay=1", "--modelledDays=365"],
              note=f"history {y}") for y in years]

if args.cpus:
    cpus = parse_cpus(args.cpus)
    problem = cpus_problem(cpus)
    if problem:
        sys.exit(f"--cpus {args.cpus}: {problem}")
    _set_cpus(cpus)  # GAMS and the solver inherit the affinity
sys.exit(run_driver(cells, root_dir=ROUND / "runs", argv=[], exe=args.gams, solver=args.solver,
                    threads=1, workers=args.workers, dry_run=args.dry_run, force=args.force,
                    budget_hours=args.hours))
