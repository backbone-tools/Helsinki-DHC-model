"""Model against statistics, per area and year, for the history runs.

    build(model_annual_df, validation_df) -> DataFrame: year, area, key, stat, model

One row per year, area (Helsinki, Espoo, Vantaa, Region) and key of KEYS. GWh, CO2 in kt.
Statistics: statistics.csv (Finnish Energy's district heating tables Taul1-3 and the Energy
Authority's verified emissions; statistics-notes.md has the definitions).
Model: annual.py rows. Espoo's statistics are the Fortum Espoo network (fuels summed over the
Espoo, Kauniainen and Kirkkonummi rows). Region is the three cities added together.
"""
import math

import pandas as pd

CITIES = ["Helsinki", "Espoo", "Vantaa"]
AREAS = CITIES + ["Region"]
COMPANY = {"Helsinki": "Helen Oy", "Espoo": "Fortum Power and Heat Oy, Espoo",
           "Vantaa": "Vantaan Energia Oy"}
NAN = float("nan")

KEYS = {  # key: (name on the page, unit)
    "chp_heat": ("Heat from CHP plants", "GWh"),
    "hob_heat": ("Heat from heat-only boilers", "GWh"),
    "el_heat": ("Heat from electricity and heat recovery", "GWh"),
    "chp_el": ("CHP electricity", "GWh"),
    "el_used": ("Electricity used by heat pumps and e-boilers", "GWh"),
    "co2": ("CO2, verified (ETS)", "kt"),
    "coal": ("Coal", "GWh"),
    "gas": ("Natural gas", "GWh"),
    "wood": ("Wood", "GWh"),
    "waste": ("Waste", "GWh"),
    "other": ("Other fuels", "GWh"),
    "fuel": ("Total fuel use", "GWh"),
    "from_Helsinki": ("Heat bought from Helsinki", "GWh"),
    "from_Espoo": ("Heat bought from Espoo", "GWh"),
    "from_Vantaa": ("Heat bought from Vantaa", "GWh"),
    "spill": ("Spilled heat", "GWh"),
    "network_use": ("Heat sold plus network losses", "GWh"),
}

v = m = None  # the statistics and the model rows, set by build()
read = set()  # index of every statistics row that entered a number; make_statistics.py keeps these


def picked(x):
    """Statistics rows x, recorded as read."""
    read.update(x.index)
    return x


def mv(year, city, metric, cat="total"):
    x = m[(m.year == year) & (m.city == city) & (m.metric == metric) & (m.category == cat)]
    return float(x.value.sum()) if len(x) else 0.0


def mv_like(year, city, metric, pattern):
    x = m[(m.year == year) & (m.city == city) & (m.metric == metric)
          & m.category.str.contains(pattern, regex=True)]
    return float(x.value.sum())


def t1(year, city, metric_start):
    """One Taul1 figure of the city's company; nan when the statistics have none."""
    x = picked(v[(v.table == "Taul1") & (v.year == year) & (v.entity == COMPANY[city])
                 & v.metric.str.startswith(metric_start)])
    if len(x) > 1:
        raise ValueError(f"{len(x)} rows for {year} {city} {metric_start}")
    return float(x.value.iloc[0]) if len(x) else NAN


# Taul3 fuel columns by group. The key is the text before the first colon of the column's name.
FUEL_GROUPS = {
    "coal": ["coal"], "natural gas": ["natural gas"],
    "oil": ["heavy fuel oil", "light fuel oil", "other oil products"], "bio-oil": ["bio-oil"],
    "wood excl. pellets": ["forest chips and wood fuel", "industrial wood residues",
                           "forest industry by-products", "recycled wood", "other biomass"],
    "wood pellets": ["wood pellets"], "peat": ["peat"], "waste": ["waste"],
    "biogas": ["biogas and biomethane"], "e-boiler electricity": ["electricity for e-boilers"],
}
# From 2025 the statistics book gas taken from the gas grid under a biomethane contract in a
# column of its own. It is grid gas, and the model burns it as gas, so it counts as natural gas.
GRID_BIOMETHANE = "biogas and biomethane: Biometaani (otto maakaasuverkosta)"
# The page's fuels: statistics groups and model fuels (model: bio is wood chips, syngas has no statistic).
PAGE_FUELS = {
    "coal": (["coal"], ["coal"]),
    "gas": (["natural gas"], ["gas"]),
    "wood": (["wood excl. pellets", "wood pellets"], ["bio", "pellet"]),
    "waste": (["waste"], ["waste"]),
    "other": (["oil", "bio-oil", "peat", "biogas"], ["oil", "bioOil", "bioGas", "syngas"]),
}


def t3(year, city, group):
    """Fuel use of one FUEL_GROUPS group, whole plants at lower heating value."""
    x = v[(v.table == "Taul3") & (v.year == year) & (v.city == city)
          & (v.metric == "fuel use, DH and CHP")]
    cat = x.category.fillna("")
    grp = cat.str.split(":").str[0].where(cat != GRID_BIOMETHANE, "natural gas")
    return float(picked(x[grp.isin(FUEL_GROUPS[group])]).value.sum())


def hp_elec(year, city):
    x = picked(v[(v.table == "Taul3") & (v.year == year) & (v.city == city)
                 & v.metric.str.startswith("electricity used by heat pumps")])
    return float(x.value.sum()) if len(x) else NAN


def trade(year, buyer, seller):
    """Heat the buyer's company bought from the seller's (Taul2)."""
    x = v[(v.table == "Taul2") & (v.year == year) & (v.entity == COMPANY[buyer])
          & (v.metric == "heat purchased, by supplier")]
    sel = x.category.fillna("")
    if seller == "Espoo":
        hit = sel.str.contains("Fortum Power and Heat Oy, Espoo|^Fortum Power and Heat Oy$")
    else:
        hit = sel.str.contains(COMPANY[seller])
    return float(picked(x[hit]).value.sum())


def ets_co2(year, city):
    """Verified emissions of the city's ETS installations, kt. Data centres' standby plants are
    left out; waste incineration is outside the ETS and in a file of its own."""
    x = v[(v.year == year) & (v.city == city) & (v.table == "EV-installations")]
    keep = ~x.category.fillna("").str.contains(r"Data Center|FI-HEL-DC01")
    return float(picked(x[keep]).value.sum()) / 1000.0


def network_use(year, city):
    """Heat sold plus network losses: supply (Taul1 1.4) less deliveries to other companies."""
    if city == "Espoo":  # deliveries to Kauniainen and Kirkkonummi are inside the one network
        d = v[(v.table == "derived") & (v.year == year) & (v.city == city)]
        deliv = float(picked(d[d.metric == "heat delivered to other DH companies"]).value.sum())
    else:
        deliv = t1(year, city, "heat delivered to other DH companies")
    return t1(year, city, "heat supply total") - deliv


def nansum(values):
    vals = [x for x in values if x is not None and not math.isnan(x)]
    return sum(vals) if vals else NAN


def city_rows(y, c, influx):
    """{key: (statistics, model)} of one city and year."""
    eb = t3(y, c, "e-boiler electricity")  # the e-boilers' heat is taken as their electricity
    out = {
        # Taul1 1.8 against the CHP units without their bypass units and heat recovery
        "chp_heat": (t1(y, c, "DH net production in CHP"), mv(y, c, "DH production by type", "CHP plant")),
        # 1.1 - 1.8 - e-boilers: the statistics count heat a CHP unit makes without electricity here
        "hob_heat": (t1(y, c, "heat net production from fuels") - t1(y, c, "DH net production in CHP") - eb,
                     mv_like(y, c, "DH production by type", r"^heat-only |^waste heat-only|^CHP bypass$")),
        # 1.2 + e-boilers: heat pumps, flue-gas condensing and other recovery, electric boilers
        "el_heat": (t1(y, c, "heat from heat recovery and heat pumps") + eb,
                    mv_like(y, c, "DH production by type", r"^heat pump$|^electric boiler$|^heat recovery$")),
        # 1.9 is net electricity linked to district heat, so the model's condensing output is left out
        "chp_el": (t1(y, c, "CHP electricity net production"),
                   mv(y, c, "Electricity production") - mv(y, c, "Electricity production", "condensing")),
        "el_used": (nansum([hp_elec(y, c), eb]),
                    mv_like(y, c, "Electricity consumption by group", r"^heat pumps$|^electric boilers$")),
        "co2": (ets_co2(y, c), mv(y, c, "Emissions ETS-CO2")),
        "spill": (NAN, mv(y, c, "DH spilled")),
        "network_use": (network_use(y, c), influx.get((y, c), NAN)),
    }
    for key, (stat_groups, model_fuels) in PAGE_FUELS.items():
        out[key] = (sum(t3(y, c, g) for g in stat_groups), sum(mv(y, c, "Fuel use", f) for f in model_fuels))
    out["fuel"] = (sum(out[k][0] for k in PAGE_FUELS), mv(y, c, "Fuel use"))
    for seller in CITIES:  # heat this city bought from the seller
        out[f"from_{seller}"] = (NAN, NAN) if seller == c else (trade(y, c, seller), mv(y, c, "DH import", seller))
    return out


def build(model_annual, validation, influx=None):
    """The comparison table. influx: {(year, city): GWh} of the model's heat supply input."""
    global m, v
    m = model_annual.copy()
    m["category"] = m["category"].fillna("")
    v = validation
    rows = []
    for y in sorted(int(x) for x in m.year.unique()):
        per_city = {c: city_rows(y, c, influx or {}) for c in CITIES}
        for key in KEYS:
            for c in CITIES:
                rows.append(dict(year=y, area=c, key=key, stat=per_city[c][key][0], model=per_city[c][key][1]))
            rows.append(dict(year=y, area="Region", key=key,
                             stat=nansum(per_city[c][key][0] for c in CITIES),
                             model=nansum(per_city[c][key][1] for c in CITIES)))
    return pd.DataFrame(rows)
