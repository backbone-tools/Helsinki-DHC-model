# statistics.csv: what it holds and how to read it

`statistics.csv` holds the statistics the validation report compares the model with: the rows
of `validation/validation_long.csv` (not in git) that `comparison.py` reads, plus the inputs of
the derived rows. This page keeps what is needed to read them. The publications are listed in
`readme.md`.

## The rows

Columns: year, city, entity, table, metric, category, value, unit, source.

- `source` is `file | sheet | cell [column code and header]`. 2016 was read from an .xlsx
  conversion of the original .xls, so its `source` names `kl-tilasto-2016.xlsx`.
- Only numeric cells were written. `-` (no activity) and `..` (not reported or too uncertain) are
  skipped, so a missing row is not a zero. A written 0 is a reported 0.
- Values are in the source unit: GWh for the district heating tables, t CO2 for emissions (the
  report shows kt). Excel float noise is rounded to 10 significant digits.

| `table` | What | Rows used |
|---|---|---|
| `Taul1` | network heat balance per company or municipality | 1.1, 1.2, 1.4, 1.6, 1.8, 1.9 of the three companies; 1.3 of Kauniainen and Kirkkonummi |
| `Taul2` | heat bought from other companies, buyer view | purchases among the three |
| `Taul3` | fuels for district heat and CHP electricity, GWh at lower heating value | fuel columns, e-boiler electricity, heat-pump electricity |
| `EV-installations` | verified fossil EU ETS emissions per installation, t CO2 | the installations listed below |
| `derived` | computed from Taul1 | Espoo network deliveries to other companies |

## Entities

- **Helsinki** is `Helen Oy` (code 005).
- **Vantaa** is `Vantaan Energia Oy` (016). Its Järvenpää-Tuusula subsidiary (code 202) is not Vantaa
  and is left out.
- **Espoo** is Fortum's Espoo network: the municipality rows `Fortum Power and Heat Oy, Espoo`
  (148.26), `..., Kauniainen` (148.27) and `..., Kirkkonummi (keskusta)` (148.28). The company row
  148 is not used: until 2019 it also held Joensuu, Järvenpää and Tuusula. `Adven Oy, Kirkkonummi`
  is a separate network and is left out.
  - Supply, purchases from Helen and Vantaa, and losses are all on the 148.26 row, so Espoo's Taul1
    figures are that row alone. Taul3 fuels are summed over all three rows.
  - Kauniainen and Kirkkonummi buy only from Espoo, so Espoo's 1.6 deliveries include 154-193 GWh a
    year that stay inside the network. The `derived` row removes them: Espoo 1.6 minus
    Kauniainen 1.3 minus Kirkkonummi 1.3. `make_statistics.py` checks that sum for every year.

## Definitions

Taul1 balances as 1.4 supply = 1.1 + 1.2 + 1.3 = 1.5 + 1.6 + 1.7:

- **1.1** net production from fuels, after the plants' own use. It includes e-boiler heat (stated in
  the 2024-2025 footnotes). E-boiler heat is never reported separately, only the e-boilers'
  electricity in Taul3.
- **1.2** heat recovery and heat pumps together: flue-gas condensers, waste water, cooling return
  water, data centres.
- **1.3** purchase, **1.5** sales, **1.6** deliveries to other companies, **1.7** losses.
- **1.8** the CHP part of 1.1. Heat a CHP unit makes without electricity is in 1.1 but not in 1.8.
- **1.9** net CHP electricity linked to district heat production, without condensing power.

Taul3 fuels are whole-plant fuel, including the fuel for CHP electricity, not split between heat
and power. They are physical flows, not guarantees of origin. E-boiler electricity is in the Taul3
fuel total and heat-pump electricity is not.

CO2 covers fossil emissions only, so biomass counts as zero. The file has no location column, so
installations were matched to cities by name:

| City | Installations |
|---|---|
| Helsinki | every Helen installation: Alppila, Hanasaari (B plant to 2023, heat plant), Jakomäki, Kellosaari, Lassila, Munkkisaari, Myllypuro, Patola, Ruskeasuo, Salmisaari A and B, Vuosaari A, ABC and heat plant |
| Espoo | Juvanmalmi, Kaupunginkallio, Kivenlahti, Otaniemi, Suomenoja, Tapiola, Vermo; Kirkkonummi and Masala (to 2017) heat plants |
| Vantaa | every Vantaan Energia installation: Hakunila, Jussla (to 2017), Koivukylä, Lentokenttä, Maarinkunnas, Martinlaakso, Vantaan jätevoimala |

Fortum's plants outside the Espoo network (Inkoo, Meri-Pori, Loviisa, Tuusula, Joensuu) and the
data centres' standby plants (Telia, Verne) are left out. `Vuosaaren A-voimalaitos` is reported
inside `Vuosaaren ABC-voimalaitos` from 2022.

## From statistics to the report's keys

`comparison.py` does this; Region is the three cities added together, skipping a city with no value.

| Key | Statistic |
|---|---|
| `chp_heat` | 1.8 |
| `hob_heat` | 1.1 - 1.8 - e-boiler electricity |
| `el_heat` | 1.2 + e-boiler electricity (an e-boiler's heat is taken as its electricity) |
| `chp_el` | 1.9 |
| `el_used` | heat-pump electricity + e-boiler electricity |
| `co2` | the city's installations above, in kt |
| `coal`, `gas`, `wood`, `waste`, `other` | Taul3 columns grouped in `FUEL_GROUPS` and `PAGE_FUELS`: wood is wood chips, residues, pellets and other biomass; other is oil, bio-oil, peat and biogas |
| `fuel` | the five above; e-boiler electricity is not a fuel here |
| `from_<city>` | Taul2: what the city's company bought from that city's company |
| `network_use` | 1.4 - 1.6, for Espoo with the `derived` deliveries |
| `spill` | no statistic |

## Doubts in these rows

- **Espoo e-boiler electricity before 2023 is doubtful.** The plant list has no Espoo e-boiler before
  2023, yet Taul3 reports 8.6, 102.9, 100.5, 90.6 GWh (2016-2019) and 15.1 GWh (2021). The 2017-2019
  values equal that year's heat-pump electricity, so they are probably double entries. These values
  move Espoo's `hob_heat`, `el_heat` and `el_used`.
- **Espoo 2023 heat-pump electricity** is 25.3 GWh against 616 GWh of recovery and heat-pump heat,
  which is implausible. The 195.9 GWh of e-boiler electricity may hold part of it.
- **Vantaa never reports heat-pump electricity** (`..`), so its `el_used` statistic is the e-boiler
  electricity alone: 0 until 2024, 19.2 GWh in 2025. Its 1.2 has no number in 2016-2017.
- **Grid gas booked as biomethane.** From 2025 Taul3 has a column for gas taken from the gas grid
  as biomethane: Helen 406.6, Espoo 34.6 and Vantaa 25.3 GWh. `comparison.py` counts it as natural
  gas (`GRID_BIOMETHANE`), as the model burns it.
- **Vantaa's waste-fired CO2 is outside the cube.** The `Vantaan jätevoimala` row (45.9 kt in 2016,
  under 0.6 kt since 2020) seems to cover only the plant's non-waste fuels (assumption). Waste
  incineration's own CO2 was reported only from 2024, in a separate file that is not used here
  (283 kt in 2024, 305 kt in 2025). So Vantaa's `co2` leaves it out in every year.
- **Revised editions.** The district heating tables of 2021, 2023 and 2024 were revised (16.6.2023,
  12.12.2024 and 12.6.2026; the dates are in the file names). The emissions file is the 2026
  publication and carries corrections.

## Checks

These ran on the full table in `validation/` at extraction. They cannot be rerun from this file
alone, because they need rows it leaves out:

- In every entity and year, Taul1 balances (1.4 = 1.1 + 1.2 + 1.3 = 1.5 + 1.6 + 1.7) within 0.15 GWh.
- The Taul3 fuel columns sum to the Taul3 total, and the Taul2 purchases to 1.3.
- From 2020 the Fortum company row equals the Espoo network.
- 182 cells named in `source` were reopened and all matched.

`make_statistics.py` checks the `derived` rows against the Taul1 rows beside them.
