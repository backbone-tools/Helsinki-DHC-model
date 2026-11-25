"""Step 3 of the validation report: build HelsinkiDHC-validation.html in the model folder.

    python validation-scripts/build_validation.py

The page compares the history runs 2016-2025 with the statistics, as rows of small trend panels:
the region, then each city, then what moves between the cities. The whole chain:

    make_inputs.py      one input folder a year, from the workbook copies (its docstring says how)
    run_years.py        the ten runs, into output/validation-runs/runs/
    build_validation.py this page

How model output is matched to the statistics is in annual.py (dh_type, DH_SPLIT) and
comparison.py; the statistics are statistics.csv here (make_statistics.py). The sentences under the rows
are written by hand in TEXT and IN_SHORT; every number in them is computed, through a
{gap:Area:key} style token (see fill).
"""
import datetime
import re
import sys
from html import escape
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import annual  # noqa: E402
import comparison  # noqa: E402
import svgcharts as sc  # noqa: E402
from comparison import CITIES, KEYS  # noqa: E402

# ---------------------------------------------------------------- PATHS AND PERIODS
MODEL = HERE.parent
ROUND = MODEL / "output" / "validation-runs"
RUNS = ROUND / "runs"
RUN_NAME = "y{year}"
STATISTICS = HERE / "statistics.csv"
OUT_HTML = MODEL / "HelsinkiDHC-validation.html"
HISTORY = list(range(2016, 2026))
RECENT = (2023, 2025)   # the years the future is expected to resemble: the reference of every panel's corner
RECENT_YEARS = list(range(RECENT[0], RECENT[1] + 1))
CORNER_HINT = f"mean over {RECENT[0]}–{RECENT[1]}"
SHADED = (2020, 2022)   # COVID and the gas crisis, drawn as a band in every panel
PAGE_WIDTH = 1148       # px inside the page's column, for the panels' nominal width
FUEL_PANEL_FROM = 100   # GWh: a fuel gets a trend panel in an area where it reaches this in some year


# ---------------------------------------------------------------- GATHER
def supply_input(year):
    """{(year, city): GWh} of the heat supply the run was given, heat sold plus network losses:
    ts_influx on the district heating
    nodes, the realized branch f00 over the 8760 modelled hours."""
    g = annual.read_gdx(ROUND / f"input-y{year}" / "inputData.gdx", ["ts_influx"])
    out = {}
    for (grid, node, f, t), v in g.values("ts_influx").items():
        if grid == "dh" and f == "f00" and 1 <= int(t[1:]) <= 8760:
            key = (year, annual.city(node))
            out[key] = out.get(key, 0.0) - v / 1000.0
    return out


def gather():
    """The comparison table and one check row per run."""
    rows, checks, influx = [], [], {}
    for y in HISTORY:
        run = RUNS / RUN_NAME.format(year=y)
        if not (run / "sweep_cell.json").is_file():
            raise SystemExit(f"{y}: no finished run in {run}")
        r, problems, n_solves, n_steps = annual.annual(run)
        rows += r
        info = (run / "info.txt").read_text(errors="replace")
        core = re.search(r"git_version\s*:\s*(\S+)", info)
        horizon = re.search(r"Horizon:\s*(\d+)", info)
        checks.append(dict(year=y, problems=problems, solves=n_solves, steps=n_steps, core=core.group(1) if core else "?",
                           horizon=int(horizon.group(1)) if horizon else None))
        influx.update(supply_input(y))
        print(f"[{'ok' if not problems else 'CHECK'}] {y}: {n_solves} solves, {n_steps} steps"
              + ("; " + "; ".join(problems) if problems else ""), flush=True)
    return comparison.build(pd.DataFrame(rows), pd.read_csv(STATISTICS), influx), checks


class Data:
    """The comparison, read as series: {year: value or None} per area and key."""

    def __init__(self, cmp_):
        self.s, self.m = {}, {}
        for r in cmp_.itertuples(index=False):
            self.s.setdefault((r.area, r.key), {})[r.year] = None if pd.isna(r.stat) else float(r.stat)
            self.m.setdefault((r.area, r.key), {})[r.year] = None if pd.isna(r.model) else float(r.model)

    def stat(self, area, key):
        return self.s[(area, key)]

    def model(self, area, key):
        return self.m[(area, key)]

    def gap(self, area, key, years=HISTORY):
        """Mean of model minus statistics over the years where both have a value."""
        s, m = self.stat(area, key), self.model(area, key)
        d = [m[y] - s[y] for y in years if s[y] is not None and m[y] is not None]
        return sum(d) / len(d) if d else None

    def mean(self, series, years=HISTORY):
        v = [series[y] for y in years if series[y] is not None]
        return sum(v) / len(v) if v else None

    def top(self, area, keys):
        """The largest value, statistics or model, of the keys: the top of a scale they share."""
        both = [d for k in keys for d in (self.stat(area, k), self.model(area, k))]
        return max([v for d in both for v in d.values() if v is not None] or [0])


# ---------------------------------------------------------------- NUMBERS IN TEXT
def signed(v):
    if v is None:
        return "–"
    r = round(v)
    return ("+" if r > 0 else "−" if r < 0 else "") + f"{abs(r):,}"


def fill(text, D):
    """Replace the tokens of a hand-written sentence with numbers from the comparison:

        {gap:Area:key}         mean of model minus statistics, signed, all years
        {gap:Area:key:23-25}   the same over 2023-2025; any yy-yy range, or one year as yy
        {stat:Area:key[:yy-yy]}  mean of the statistics    {model:Area:key[:yy-yy]}  mean of the model
    """
    def one(match):
        kind, area, key, rng = match.group(1), match.group(2), match.group(3), match.group(4)
        years = HISTORY
        if rng:
            a, _, b = rng.partition("-")
            years = list(range(2000 + int(a), 2000 + int(b or a) + 1))
        if kind == "gap":
            return signed(D.gap(area, key, years))
        v = D.mean(D.stat(area, key) if kind == "stat" else D.model(area, key), years)
        return "–" if v is None else f"{v:,.0f}"

    return re.sub(r"\{(gap|stat|model):([A-Za-z]+):(\w+?)(?::(\d\d(?:-\d\d)?))?\}", one, text)


# ---------------------------------------------------------------- PANELS AND ROWS
FUEL_PARTS = [("coal", "var(--s7)"), ("gas", "var(--s4)"), ("wood", "var(--s3)"), ("waste", "var(--s5)"),
              ("other", "var(--faint)")]
CITY_COLOR = {"Helsinki": "var(--s7)", "Espoo": "var(--s4)", "Vantaa": "var(--s3)"}


def card(title, corner, svg, hint=""):
    tip = f' title="{escape(hint)}"' if hint else ""
    return f'<div class="sm"><h4><span>{escape(title)}</span><span class="md"{tip}>{corner}</span></h4>{svg}</div>'


def trend_card(D, area, key, width, ymax=None):
    name, unit = KEYS[key]
    svg = sc.trend(HISTORY, D.stat(area, key), D.model(area, key), unit, width, ymax=ymax, shaded=SHADED)
    gap = D.gap(area, key, RECENT_YEARS)
    return card(name, "" if gap is None else f"{signed(gap)} {unit}/a", svg, f"model minus statistics, {CORNER_HINT}")


def fuel_card(D, area, width):
    parts = [(KEYS[k][0], color, {y: (D.model(area, k)[y] or 0) - (D.stat(area, k)[y] or 0) for y in HISTORY})
             for k, color in FUEL_PARTS]
    svg = sc.bars(HISTORY, parts, "GWh", width, shaded=SHADED, net="all fuels")
    return card("Difference by fuel", f"{signed(D.gap(area, 'fuel', RECENT_YEARS))} GWh/a", svg,
                f"all fuels, model minus statistics, {CORNER_HINT}")


def row(title, cards, scale, text, legend=""):
    n = len(cards)
    return (f'<div class="row"><div class="rowhead"><h3>{escape(title)}</h3><span class="scale">{scale}</span>{legend}</div>'
            f'<div class="panels n{n}" style="--n:{n}">{"".join(cards)}</div>'
            + (f'<p class="note">{text}</p>' if text else "") + "</div>")


def panel_width(n):
    return int((PAGE_WIDTH - 12 * (n - 1)) / n) - 22


FUEL_LEGEND = sc.legend([(KEYS[k][0].lower(), c, "box") for k, c in FUEL_PARTS] + [("all fuels, net", "var(--ink)", "dot")],
                        "tiny", "difference by fuel:")
SHARED, OWN = "one scale across the trend panels", "each panel on its own scale"
LEGEND = sc.legend([("statistics", sc.STAT, "line"), ("model", sc.MODEL, "dash"),
                    (f"{SHADED[0]}–{SHADED[1]}: COVID and the gas crisis", "", "band")])


def fuel_row(D, area, text):
    keys = [k for k in ("coal", "gas", "wood", "waste") if D.top(area, [k]) >= FUEL_PANEL_FROM]
    w = panel_width(len(keys) + 1)
    top = D.top(area, keys)
    cards = [trend_card(D, area, k, w, ymax=top) for k in keys] + [fuel_card(D, area, w)]
    return row("Fuels", cards, SHARED, text, FUEL_LEGEND)


def sec_region(D):
    keys = ["chp_heat", "chp_el", "fuel", "co2"]
    w = panel_width(len(keys) + 1)
    cards = [trend_card(D, "Region", k, w) for k in keys] + [fuel_card(D, "Region", w)]
    return ('<section id="region"><h2>The region</h2>' + LEGEND
            + row("The three cities added together", cards, OWN, fill(TEXT[("Region", "all")], D), FUEL_LEGEND) + "</section>")


def sec_city(D, c):
    heat, el = ["chp_heat", "hob_heat", "el_heat"], ["chp_el", "el_used", "co2"]
    w = panel_width(3)
    top = D.top(c, heat)
    return (f'<section id="{c.lower()}"><h2>{c}</h2>{LEGEND}'
            + row("Heat by kind of plant", [trend_card(D, c, k, w, ymax=top) for k in heat], SHARED, fill(TEXT[(c, "heat")], D))
            + row("Electricity and CO2", [trend_card(D, c, k, w) for k in el], OWN, fill(TEXT[(c, "el")], D))
            + fuel_row(D, c, fill(TEXT[(c, "fuel")], D)) + "</section>")


def sec_between(D):
    keys = [f"from_{c}" for c in CITIES]
    w = panel_width(4)
    top = D.top("Region", keys)
    cards = [trend_card(D, "Region", k, w, ymax=top) for k in keys]
    parts = [(c, CITY_COLOR[c], D.model(c, "spill")) for c in CITIES]
    spill = D.mean(D.model("Region", "spill"), RECENT_YEARS)
    cards.append(card("Spilled heat (model only)", f"{spill:,.0f} GWh/a", sc.bars(HISTORY, parts, "GWh", w, shaded=SHADED),
                      f"the model's spilled heat, {CORNER_HINT}"))
    legend = sc.legend([(c, CITY_COLOR[c], "box") for c in CITIES], "tiny", "spilled heat:")
    return ('<section id="between"><h2>Between the cities</h2>' + LEGEND
            + row("Heat bought, and heat spilled", cards, "heat bought on one scale",
                  fill(TEXT[("Between", "all")], D), legend) + "</section>")


# ---------------------------------------------------------------- THE HAND-WRITTEN TEXT
IN_SHORT = [  # (bold lead, sentence with tokens)
    ("The regional totals follow the statistics.",
     "Over the ten years total fuel use is {gap:Region:fuel} GWh a year from the reported {stat:Region:fuel}, heat from "
     "CHP plants {gap:Region:chp_heat} from {stat:Region:chp_heat}, CHP electricity {gap:Region:chp_el} from "
     "{stat:Region:chp_el} and CO2 {gap:Region:co2} kt from {stat:Region:co2}. All four fall over the decade as the "
     "statistics do."),
    ("The split between fuels is the weak part, not the total.",
     "Natural gas is {gap:Region:gas} GWh a year, coal {gap:Region:coal}, wood {gap:Region:wood} and other fuels "
     "{gap:Region:other}: opposite gaps that leave {gap:Region:fuel} in total. Most of the gas gap is from "
     "2016&ndash;2021 ({gap:Region:gas:16-21} a year); in 2023&ndash;2025 it is {gap:Region:gas:23-25}."),
    ("A city is further off than the region.",
     "Heat from CHP plants is {gap:Helsinki:chp_heat} GWh a year in Helsinki, {gap:Espoo:chp_heat} in Espoo and "
     "{gap:Vantaa:chp_heat} in Vantaa, which add up to {gap:Region:chp_heat}. The model makes more of the region's heat "
     "in Vantaa and moves it to Helsinki: {gap:Region:from_Vantaa} GWh a year more than is reported bought from Vantaa."),
    ("2023&ndash;2025, the years most like the future.",
     "The fuel split is closer: natural gas {gap:Region:gas:23-25}, coal {gap:Region:coal:23-25}, wood "
     "{gap:Region:wood:23-25} and other fuels, mostly oil, {gap:Region:other:23-25} GWh a year. The largest gap left is "
     "CHP electricity: {gap:Region:chp_el:23-25} GWh a year against a reported {stat:Region:chp_el:23-25}, and above "
     "the statistics in all three cities, with heat from CHP plants {gap:Region:chp_heat:23-25} and from heat-only "
     "boilers {gap:Region:hob_heat:23-25}."),
]
TEXT = {
    ("Region", "all"):
        "Sums are closer than their parts: a gap in one city is often the opposite gap in another, and the same holds "
        "between fuels. In the bars, gas below zero with coal and wood above it is largely one error seen twice, heat "
        "made with the wrong fuel; the black dot is what is left in total fuel use. The extreme year is 2020, with "
        "{gap:Region:gas:20} GWh of gas and {gap:Region:coal:20} of coal.",
    ("Helsinki", "heat"):
        "Heat from CHP plants is below the statistics in every year, by {gap:Helsinki:chp_heat} GWh a year "
        "({gap:Helsinki:chp_heat:23-25} in 2023&ndash;2025). The other two kinds and heat bought from Vantaa make up for "
        "it. The heat pumps run close to baseload in the model: limits on their heat sources (sewage water flow, cooling "
        "return heat) are probably missing.",
    ("Helsinki", "el"):
        "CHP electricity is below the statistics until 2021 ({gap:Helsinki:chp_el:16-21} GWh a year), as the CHP plants' "
        "gas is, and above them since ({gap:Helsinki:chp_el:22-25}). The heat pumps and e-boilers use more electricity "
        "than reported until 2024; in 2025 the reported use rises to {stat:Helsinki:el_used:25} GWh, mostly in electric "
        "boilers, and the model has {model:Helsinki:el_used:25}. CO2 is {gap:Helsinki:co2} kt a year below, as the gas is.",
    ("Helsinki", "fuel"):
        "Until 2021 gas is {gap:Helsinki:gas:16-21} GWh a year and coal {gap:Helsinki:coal:16-21} against the "
        "statistics: at one fuel price a year the model prefers the coal CHP plants, most of all in 2020. In 2022 "
        "it is the other way round ({gap:Helsinki:gas:22} of gas): nothing in the model stands for that year's gas "
        "supply. In 2023&ndash;2025 gas is {gap:Helsinki:gas:23-25} and coal {gap:Helsinki:coal:23-25}. The statistics "
        "still have {stat:Helsinki:coal:25} GWh of coal in 2025 and the model none: a plant is in the model for a whole "
        "year or not at all. Other fuels, mostly oil, are {gap:Helsinki:other:21-24} GWh a year in 2021&ndash;2024.",
    ("Espoo", "heat"):
        "The three kinds follow the statistics, closest in 2023&ndash;2025: CHP plants {gap:Espoo:chp_heat:23-25}, "
        "heat-only boilers {gap:Espoo:hob_heat:23-25}, electricity and recovery {gap:Espoo:el_heat:23-25} GWh a year. In "
        "2017&ndash;2019 heat-only boilers are {gap:Espoo:hob_heat:17-19} GWh a year and CHP plants "
        "{gap:Espoo:chp_heat:17-19}.",
    ("Espoo", "el"):
        "CHP electricity is {gap:Espoo:chp_el} GWh a year against the statistics, most in 2016 "
        "({model:Espoo:chp_el:16} against {stat:Espoo:chp_el:16}) when heat from the CHP plants matches: the model's "
        "plants make more electricity for their heat than is reported. Electricity use matches in 2024 and 2025 "
        "({gap:Espoo:el_used:24-25} GWh a year). The earlier gaps are doubtful statistics: e-boiler electricity is "
        "reported for 2016&ndash;2019 and 2021 with no e-boiler in the plant list, and the heat-pump electricity "
        "reported for 2023 is out of line with the other years.",
    ("Espoo", "fuel"):
        "Total fuel use is close ({gap:Espoo:fuel} GWh a year), and in 2024 and 2025 each fuel is. In 2020 and 2021 the "
        "model burns coal and wood where Espoo burned gas: natural gas {gap:Espoo:gas:20-21}, coal "
        "{gap:Espoo:coal:20-21}, wood {gap:Espoo:wood:20-21} GWh a year. In 2022 gas is {gap:Espoo:gas:22}, as in "
        "Helsinki.",
    ("Vantaa", "heat"):
        "Much of this is bookkeeping. The statistics count heat that a CHP unit makes without electricity as heat-only "
        "production, and Vantaa reports its flue-gas heat recovery with heat pumps; in the model only the waste plant "
        "has such a bypass. So CHP plants {gap:Vantaa:chp_heat}, heat-only boilers {gap:Vantaa:hob_heat} and "
        "electricity and recovery {gap:Vantaa:el_heat} GWh a year largely cancel. What is left is heat the model makes "
        "in Vantaa and sends to Helsinki.",
    ("Vantaa", "el"):
        "CHP electricity is {gap:Vantaa:chp_el} GWh a year against a reported {stat:Vantaa:chp_el}, in every period "
        "({gap:Vantaa:chp_el:16-19}, {gap:Vantaa:chp_el:20-22} and {gap:Vantaa:chp_el:23-25}). Part of it is fuel the "
        "model burns and Vantaa did not: gas in the waste plant's gas turbine in 2016&ndash;2019 and coal in "
        "Martinlaakso 2 after the bio unit came in 2019. The rest is not explained yet. The electric boiler is in the "
        "model for all of 2025 and uses {model:Vantaa:el_used:25} GWh against {stat:Vantaa:el_used:25} reported: its "
        "start date needs checking.",
    ("Vantaa", "fuel"):
        "Waste is a fuel with no yearly cap in the model, so the plant burns what its capacity allows: "
        "{model:Vantaa:waste:16-21} GWh a year in 2016&ndash;2021 against {stat:Vantaa:waste:16-21} reported. The model "
        "has the enlarged plant at full capacity from the start of 2022 and the reported amounts reach that level in "
        "2024, so 2022 and 2023 are {gap:Vantaa:waste:22-23} GWh a year. Coal is {gap:Vantaa:coal:19-25} GWh a year "
        "from 2019 (Martinlaakso 2), wood {gap:Vantaa:wood:19-25}, and gas {gap:Vantaa:gas:16-19} in 2016&ndash;2019 "
        "(the gas turbine).",
    ("Between", "all"):
        "The model moves more heat between the cities than is reported bought: {gap:Region:from_Vantaa} GWh a year more "
        "from Vantaa ({gap:Region:from_Vantaa:23-25} in 2023&ndash;2025), {gap:Region:from_Espoo} from Espoo, and "
        "{gap:Region:from_Helsinki:16-18} from Helsinki in 2016&ndash;2018. In the model a link is limited by its "
        "capacity and a transfer cost. Spilled heat is heat produced and not used; it stands for the plants' auxiliary "
        "coolers, which are not modelled as units. Vantaa spills regularly from 2022 ({model:Vantaa:spill:22-25} GWh a "
        "year), where waste is burnt for electricity through the summer. In Helsinki and Espoo fuel costs more and the "
        "storages take up short surpluses, so spilling rarely pays: {model:Helsinki:spill:22} and "
        "{model:Espoo:spill:22} GWh in 2022 and a few GWh in the other years.",
}


# ---------------------------------------------------------------- THE PAGE
CSS = """
:root { --bg:#f5f7f8; --surface:#fff; --ink:#132029; --muted:#52606b; --faint:#85929c; --rule:#d9dfe3; --grid:#e3e8ec;
  --band:#eff2f5; --accent:#1c5cab; --accent-soft:#e4eef9; --far-bg:#fbe4e2; --far-fg:#9a2b22;
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100; --s5:#e87ba4; --s7:#6250d6;
  --font-display:"Source Serif 4",Georgia,"Times New Roman",serif;
  --font-body:"IBM Plex Sans","Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --font-data:"IBM Plex Mono",Consolas,"SFMono-Regular",Menlo,monospace; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#111518; --surface:#181d21; --ink:#e8edf1; --muted:#a5b0b9; --faint:#74808a; --rule:#2b3238; --grid:#2a3137;
  --band:#20262b; --accent:#6da7ec; --accent-soft:#1b2a3b; --far-bg:#3a1a17; --far-fg:#f2a59c;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s7:#9085e9; color-scheme:dark; } }
:root[data-theme="dark"] {
  --bg:#111518; --surface:#181d21; --ink:#e8edf1; --muted:#a5b0b9; --faint:#74808a; --rule:#2b3238; --grid:#2a3137;
  --band:#20262b; --accent:#6da7ec; --accent-soft:#1b2a3b; --far-bg:#3a1a17; --far-fg:#f2a59c;
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500; --s5:#d55181; --s7:#9085e9; color-scheme:dark; }
* { box-sizing:border-box; }
html { -webkit-text-size-adjust:100%; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.55 var(--font-body); }
.wrap { max-width:1180px; margin:0 auto; padding-block:28px 64px;
  padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); }
header { display:grid; gap:10px; padding-bottom:14px; }
.eyebrow { font:600 12px/1 var(--font-body); letter-spacing:.08em; text-transform:uppercase; color:var(--accent); }
h1 { font:600 clamp(28px, 4vw, 38px)/1.15 var(--font-display); margin:0; text-wrap:balance; }
h2 { font:600 24px/1.2 var(--font-display); margin:0; }
h3 { font:600 15.5px/1.3 var(--font-body); margin:0; }
h4 { font:600 12.5px/1.25 var(--font-body); margin:0; color:var(--muted); display:flex; justify-content:space-between;
  gap:8px; align-items:baseline; }
h4 .md { font:12px var(--font-data); color:var(--ink); white-space:nowrap; }
p, li { max-width:78ch; margin:0; }
.lede { font-size:16.5px; color:var(--muted); }
.read { font-size:13.5px; color:var(--muted); }
.meta { display:flex; flex-wrap:wrap; gap:4px 22px; margin:2px 0 0; font-size:13px; }
.meta div { display:flex; gap:6px; } .meta dt { color:var(--faint); }
.meta dd { margin:0; font:12.5px var(--font-data); }
nav { display:flex; flex-wrap:wrap; gap:4px 16px; padding:10px 0; font-size:14px; border-top:1px solid var(--rule);
  border-bottom:1px solid var(--rule); }
nav a { color:var(--accent); text-decoration:none; } nav a:hover, nav a:focus-visible { text-decoration:underline; }
section { display:grid; gap:14px; padding-block:26px 22px; border-bottom:1px solid var(--rule); min-width:0;
  scroll-margin-top:8px; }
.row { display:grid; gap:8px; min-width:0; }
.rowhead { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 12px; }
.scale { font-size:12px; color:var(--faint); }
.panels { display:grid; gap:12px; grid-template-columns:repeat(var(--n), minmax(0, 1fr)); }
.sm { background:var(--surface); border:1px solid var(--rule); border-radius:6px; padding:8px 10px 4px; display:grid;
  gap:4px; min-width:0; align-content:start; }
.n5 h4 { min-height:2.5em; align-items:start; }
.chart { display:block; width:100%; height:auto; overflow:visible; }
.chart .gl { stroke:var(--grid); stroke-width:1; }
.chart .axis0 { stroke:var(--faint); stroke-width:1; }
.chart .band { fill:var(--band); }
.chart .tick { fill:var(--muted); font:10.5px var(--font-data); }
.chart .mark { stroke:var(--surface); stroke-width:1.2; }
.chart .hit { fill:transparent; }
.chart .pt:hover .mark, .chart .seg:hover { opacity:.7; }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:12.5px; color:var(--muted); }
.legend.tiny { font-size:12px; gap:2px 10px; margin-left:auto; }
.legend .li { display:inline-flex; align-items:center; gap:5px; }
.sw { display:inline-block; flex:none; } .sw.box { width:10px; height:10px; border-radius:2px; }
.sw.dot { width:8px; height:8px; border-radius:50%; } .sw.line { width:18px; height:0; }
.band-sw { background:var(--band); border:1px solid var(--rule); }
.note { font-size:14px; }
.take { margin:0; padding-left:20px; display:grid; gap:6px; } .take li { max-width:92ch; }
.problem { background:var(--far-bg); color:var(--far-fg); padding:8px 12px; border-radius:6px; }
footer { padding-top:22px; font-size:13.5px; color:var(--muted); display:grid; gap:8px; }
code { font:12.5px var(--font-data); background:var(--accent-soft); padding:1px 5px; border-radius:3px; }
@media (max-width: 900px) { .panels { grid-template-columns:repeat(auto-fit, minmax(min(100%, 250px), 1fr)); } }
"""


def run_sentence(checks):
    bad = [f"{c['year']}: {'; '.join(c['problems'])}" for c in checks if c["problems"]]
    if bad:
        return '<p class="problem"><b>Some runs need checking.</b> ' + escape(" | ".join(bad)) + "</p>"
    return (f"<p>All {len(checks)} runs finished every one of their {checks[0]['solves']} daily solves and all "
            f"{checks[0]['steps']:,} hours, with no dummy penalty and no warning.</p>")


def horizon_text(checks):
    days = sorted({c["horizon"] // 24 for c in checks if c["horizon"]})
    return " or ".join(f"{d} days" for d in days) if days else "a horizon not recorded"


def supply_sentence(D):
    pct = {a: {y: 100 * (D.model(a, "network_use")[y] / D.stat(a, "network_use")[y] - 1) for y in HISTORY} for a in CITIES}
    spread = max(max(p[y] for p in pct.values()) - min(p[y] for p in pct.values()) for y in HISTORY)
    allv = [v for p in pct.values() for v in p.values()]
    far = max(HISTORY, key=lambda y: abs(pct["Helsinki"][y]))
    lo, hi = (f"{v:+.1f}%".replace("-", "−") for v in (min(allv), max(allv)))
    return ("<p><b>Heat supply is input, not a result.</b> The hourly supply the model is given (heat sold plus network "
            f"losses) is {lo} to {hi} from the statistics, depending on the year (furthest in {far}), "
            f"and the same in every city to within {max(spread, 0.05):.1f} percentage points. "
            "What the model produces above it is the spilled heat shown above.</p>")


def page(D, checks):
    saved = datetime.datetime.fromtimestamp(
        (ROUND / "workbooks" / "HelsinkiDHC-inputData-original.xlsx").stat().st_mtime).strftime("%Y-%m-%d %H:%M")
    cores = ", ".join(sorted({c["core"] for c in checks}))
    short = "".join(f"<li><b>{lead}</b> {fill(text, D)}</li>" for lead, text in IN_SHORT)
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Helsinki DHC validation</title><style>{CSS}</style></head>
<body><div class="wrap">
<header>
<div class="eyebrow">Helsinki region district heating model</div>
<h1>Does the model reproduce {HISTORY[0]}&ndash;{HISTORY[-1]}?</h1>
<p class="lede">The Backbone model of the district heating systems of Helsinki, Espoo and Vantaa is run for each year
{HISTORY[0]}&ndash;{HISTORY[-1]} on that year's plants, prices and weather. It is not told how the companies ran their
plants. This page compares its yearly results with Finnish Energy's district heating statistics and the Energy
Authority's verified CO2 emissions.</p>
<p class="read"><b>How to read a panel.</b> Solid line: statistics. Dashed line: model. The number in a panel's corner is
the mean difference over {RECENT[0]}&ndash;{RECENT[1]}, model minus statistics: the years after the shaded
{SHADED[0]}&ndash;{SHADED[1]} (COVID and the gas crisis), and the reference period for the future runs. Numbers in the
text are over all ten years unless the text names other years. Differences are in GWh a year (CO2 in kt), not in
percent: a small fuel can be far off in percent and matter little, and too much of one fuel beside too little of
another is a wrong split, which the fuel bars show, not a wrong total. Hover a point for its value.</p>
<dl class="meta">
<div><dt>Workbook</dt><dd>HelsinkiDHC-inputData.xlsx, saved {saved}</dd></div>
<div><dt>Runs</dt><dd>{len(checks)} calendar years</dd></div>
<div><dt>Backbone</dt><dd>{escape(cores)}</dd></div>
<div><dt>Built</dt><dd>{datetime.datetime.now():%Y-%m-%d %H:%M}</dd></div>
</dl>
</header>
<nav aria-label="Sections"><a href="#short">In short</a><a href="#region">The region</a>
{"".join(f'<a href="#{c.lower()}">{c}</a>' for c in CITIES)}<a href="#between">Between the cities</a>
<a href="#runs">The runs</a></nav>
<section id="short"><h2>In short</h2><ul class="take">{short}</ul></section>
{sec_region(D)}
{"".join(sec_city(D, c) for c in CITIES)}
{sec_between(D)}
<footer id="runs">
<p><b>How it was run.</b> Each year is one run of 365 daily solves from 1 January. Every solve looks
{horizon_text(checks)} ahead, in hourly steps at first and daily steps at the end. Fuel and CO2 prices are one value a
year, as in the runs of the future years; electricity prices and heat supply are hourly.</p>
{run_sentence(checks)}
{supply_sentence(D)}
<p><b>The statistics.</b> Finnish Energy's yearly district heating tables (heat production and use, heat bought between
companies, fuels at lower heating value for whole plants) and the Energy Authority's verified emissions of each
installation in the EU emissions trading system. Espoo is Fortum's Espoo network with Kauniainen and Kirkkonummi.
Wood is wood chips, pellets and other biomass; other fuels are oil, bio-oil, peat and biogas. From 2025 the statistics
book gas taken from the gas grid as biomethane in a column of its own; it is counted here as natural gas, as the model
burns it.</p>
<p>Rebuild: <code>python validation-scripts/build_validation.py</code> from the model folder; its docstring names the steps
before it.</p>
</footer>
</div></body></html>
"""


def main():
    cmp_, checks = gather()
    D = Data(cmp_)
    OUT_HTML.write_text(page(D, checks), encoding="utf-8")
    print(f"wrote {OUT_HTML} ({OUT_HTML.stat().st_size / 1e3:.0f} kB)")
    return D


if __name__ == "__main__":
    main()
