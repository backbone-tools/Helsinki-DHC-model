"""Annual figures of one validation run, as rows of year, city, metric, category, value, unit.

    rows, problems, n_solves, n_steps = annual(run_folder)

Reads the run's results.gdx and checks it (solve status, penalty, realized steps, warnings).
All energies are r_gen_gnu totals over the 365 modelled days (hourly steps, one sample of
weight 1), in GWh; emissions are r_emission_u in kt. Heat spilled at the district heating
nodes (r_spill_gn) stands for the plants' auxiliary coolers, which are not modelled as units.
"""
import re
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = next(p for p in HERE.parents if (p / "Backbone.gms").is_file())
sys.path.insert(0, str(REPO))
from scripts.gams_api import read_gdx  # noqa: E402

FUELS = {"bio", "bioGas", "bioOil", "coal", "gas", "oil", "pellet", "syngas", "waste"}


def city(name):
    m = re.search(r"(hel|esp|van)", name)
    return {"hel": "Helsinki", "esp": "Espoo", "van": "Vantaa"}[m.group(1)]


def plant(u):
    """Plant or group a unit belongs to, for emissions and CHP comparisons."""
    for pat, name in [(r"VuA", "Vuosaari A"), (r"VuB", "Vuosaari B"), (r"VuC", "Vuosaari C"),
                      (r"SaB", "Salmisaari"), (r"HaB", "Hanasaari"),
                      (r"Su1", "Suomenoja 1"), (r"Su2", "Suomenoja 2"), (r"Su3", "Suomenoja 3"),
                      (r"Su6", "Suomenoja 6"), (r"Mar", "Martinlaakso"),
                      (r"JV|wasteBoiler", "Vantaa waste-to-energy"),
                      (r"Sto", "storage"), (r"hp", "heat pumps"),
                      (r"elecBoiler", "electric boilers"), (r"Cool", "cooling"),
                      (r"Boiler", "heat-only boilers")]:
        if re.search(pat, u):
            return name
    return "other"


CHP_PLANTS = {"Vuosaari A", "Vuosaari B", "Salmisaari", "Hanasaari", "Suomenoja 1",
              "Suomenoja 2", "Suomenoja 6", "Martinlaakso", "Vantaa waste-to-energy"}


# DH output classified as the statistics do (Taul1): heat recovery (1.2) is flue-gas condensing
# and Martinlaakso 4's recovered heat; heat a CHP unit makes without electricity (bypass) is
# separate production, not CHP (1.8). A unit listed in DH_SPLIT has its DH divided by shares.
DH_SPLIT = {"u_van1-Mar4": (("CHP plant", 70 / 120), ("heat recovery", 50 / 120))}  # 120 MW: 70 gas turbine, 50 recovery


def dh_type(u):
    p = plant(u)
    if u.endswith("-red"):
        return "CHP bypass"
    if re.search(r"JV-boiler", u):
        return "heat recovery"  # the waste boilers' DH output is their flue-gas condensing
    if p in CHP_PLANTS and not re.search(r"wasteBoiler|Su6-boiler", u):
        return "CHP plant"
    if p == "heat pumps":
        return "heat pump"
    if p == "electric boilers":
        return "electric boiler"
    if p == "storage":
        return "storage (net)"
    if re.search(r"wasteBoiler", u):
        return "waste heat-only boiler"
    m = re.search(r"-(\w+?)Boiler|VuC|Su3", u)
    if m:
        fuel = {"VuC": "bio", "Su3": "coal"}.get(m.group(0), m.group(1) if m.lastindex else "")
        return f"heat-only {fuel}"
    return "other"


def check(d, folder):
    """Whether the run can be quoted: every solve optimal or feasible, no dummy penalty in
    r_cost_penalty, 8760 realized hours, and no '!!! Warning' line in warnings.log."""
    problems = []
    st = d.records("r_info_solveStatus")
    stats = defaultdict(dict)
    for row in st.itertuples(index=False):
        stats[row[0]][row[1]] = row[-1]
    bad = [t for t, s in stats.items()
           if s.get("modelStat") not in (1, 8) or not 1 <= s.get("solveStat", 0) <= 3]
    if bad:
        problems.append(f"{len(bad)} solves with bad status, first {bad[0]}")
    if abs(d.scalar("r_cost_penalty")) > 1e-9:
        problems.append(f"r_cost_penalty {d.scalar('r_cost_penalty')}")
    n_t = len(d.labels("r_info_t_realized"))
    if n_t != 8760:
        problems.append(f"{n_t} realized steps, not 8760")
    warn = (folder / "warnings.log").read_text(errors="replace")
    if "!!! Warning" in warn:
        problems.append("warnings.log has !!! Warning lines")
    return problems, len(stats), n_t


def annual(folder):
    year = int(re.search(r"(\d{4})", folder.name).group(1))
    d = read_gdx(folder / "results.gdx",
                 ["r_gen_gnu", "r_emission_u", "r_cost_penalty", "r_cost_realizedCost",
                  "r_info_solveStatus", "r_info_t_realized", "r_spill_gn",
                  "r_transferRightward_gnnft", "r_transferLeftward_gnnft"])
    problems, n_solves, n_t = check(d, folder)
    out = defaultdict(float)

    def add(c, metric, cat, v):
        out[(c, metric, cat)] += v
        out[("Region", metric, cat)] += v

    for (g, n, u), v in d.values("r_gen_gnu").items():
        gwh = v / 1000.0
        c = city(u)
        if g == "dh":
            add(c, "DH net into network", "", gwh)
            if v > 0 and plant(u) != "storage":
                add(c, "DH production", "total", gwh)
                for kind, share in DH_SPLIT.get(u, ((dh_type(u), 1.0),)):
                    add(c, "DH production by type", kind, gwh * share)
                add(c, "DH production by plant", plant(u), gwh)
            elif plant(u) == "storage":
                add(c, "DH production by type", "storage (net)", gwh)
            else:
                add(c, "DH consumed by units", u, -gwh)
        elif g == "elec":
            if v > 0:
                add(c, "Electricity production", "total", gwh)
                add(c, "Electricity production by plant", plant(u), gwh)
                if u.endswith("-ct"):
                    add(c, "Electricity production", "condensing", gwh)
            else:
                add(c, "Electricity consumption", "total", -gwh)
                add(c, "Electricity consumption by group", plant(u), -gwh)
        elif g == "dc":
            if plant(u) != "storage":
                add(c, "DC production", "total", gwh)
                add(c, "DC production by unit", u, gwh)
        elif g in FUELS and v < 0:
            add(c, "Fuel use", g, -gwh)
            add(c, "Fuel use", "total", -gwh)
            add(c, "Fuel use by plant", f"{plant(u)} | {g}", -gwh)
    # Inter-city DH trade, gross per direction. Both tables hold the link's first node
    # first; rightward flows first -> second, leftward second -> first (MWh/h, hourly).
    for sym, forward in (("r_transferRightward_gnnft", True), ("r_transferLeftward_gnnft", False)):
        for key, v in d.values(sym).items():
            g, n1, n2 = key[:3]
            if g != "dh" or city(n1) == city(n2):
                continue
            src, dst = (n1, n2) if forward else (n2, n1)
            out[(city(src), "DH export", city(dst))] += v / 1000.0
            out[(city(dst), "DH import", city(src))] += v / 1000.0
            out[(city(src), "DH export", "total")] += v / 1000.0
            out[(city(dst), "DH import", "total")] += v / 1000.0
    for (g, n), v in d.values("r_spill_gn").items():
        if g == "dh":
            add(city(n), "DH spilled", "total", v / 1000.0)
    for (u, e), v in d.values("r_emission_u").items():
        add(city(u), "Emissions " + e, "total", v / 1000.0)
        add(city(u), "Emissions " + e + " by plant", plant(u), v / 1000.0)
    rows = [dict(year=year, city=c, metric=m, category=k, value=round(v, 4),
                 unit="kt" if m.startswith("Emissions") else "GWh")
            for (c, m, k), v in sorted(out.items())]
    rows.append(dict(year=year, city="Region", metric="Realized cost", category="",
                     value=round(d.scalar("r_cost_realizedCost"), 4), unit="MEUR"))
    return rows, problems, n_solves, n_t
