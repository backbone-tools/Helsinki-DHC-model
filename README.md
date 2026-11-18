# Helsinki DHC model

An hourly district heating and district cooling model of the Finnish capital region - Helsinki,
Espoo (with Kauniainen and the centre of Kirkkonummi) and Vantaa - built for the
[Backbone](https://gitlab.vtt.fi/backbone/backbone) energy-system modelling framework.



## What the model covers

- **Networks**: district heating in five nodes (two in Helsinki, one in Espoo, two in Vantaa),
  district cooling in Helsinki and Espoo, the heat trade between the cities, and the heat
  storages, including the large seasonal ones.
- **Units**: CHP plants, heat-only boilers, heat pumps, electric boilers, waste incineration and
  cooling units, with their fuels, efficiencies, emissions and electricity bought and sold
  at a market price.
- **Years**: three independent choices. The unit fleet of each year 2016-2025 or of the
  scenarios 2030, 2035 and 2040; the prices and taxes of any of those years; and the hourly
  time series (heat supply, weather, electricity price) as a 365-day window that starts on
  any day from 1 January 2016 to 1 January 2025. Heat supply is the heat sold plus the network
  losses. *Choose the years* below says how they combine.
- **Run**: a rolling schedule. The model solves one day at a time and looks 28 days ahead,
  or 120 days when a seasonal storage of 30,000 MWh or more is active. The first day ahead
  is hourly and the rest coarser. Heat supply and electricity price carry a forecast.
- **Additions to Backbone's standard features** are in `inputData/changes.inc`: the largest
  storages end a run that reaches day 365 at the level they started from, and the oil and gas
  heat-only boilers give a minimum amount of heat each year in the coldest hours, as real ones
  do for testing and for supply temperature at the network edges.



## Citation

If you use the Helsinki DHC model in published work, please cite the article that documents and
validates it:

E. Pursiheimo, T. J. Lindroos, D. Sundell, M. Rämä, V. Tulkki, Optimal investment analysis for
heat pumps and nuclear heat in decarbonised Helsinki metropolitan district heating system,
Energy Storage and Saving, Volume 1, Issue 2, 2022, Pages 80-92, ISSN 2772-6835,
https://doi.org/10.1016/j.enss.2022.03.001.

`CITATION.cff` carries the same reference for GitHub's "Cite this repository" button.



## Authors

- Tomi J. Lindroos
- Esa Pursiheimo
- Pauli Hiltunen
- Dennis Sundell
- Heidi Kirppu



## History

From January 2022 to August 2025 the model was developed at VTT in a public GitLab repository,
https://gitlab.vtt.fi/backbone/models/helsinki-dhc-model. This repository continues that
work from the model as it stood in November 2026. The earlier commit history was not carried
over.



## Licence

The input data, the documentation and the validation material are under the Creative Commons
Attribution 4.0 International licence (CC BY 4.0), in `LICENSE`.

`inputData/modelsInit.gms` and `inputData/scheduleInit.gms` are adapted from Backbone's own
templates and keep Backbone's licence, the GNU Lesser General Public License version 3 or
later, as their headers say.



## What you need

- **Backbone v3.15** or higher, installed by its own instructions.
- **GAMS with a full licence and a MIP solver.** One daily solve of the 2016 run has about
  25,000 rows and 19,000 columns, 913 of them binary, which is beyond a GAMS demo or community
  licence.



## Install

Clone the model into your Backbone folder, under the name `Helsinki-DHC-model`:

    cd <your Backbone folder>
    git clone https://github.com/backbone-tools/Helsinki-DHC-model.git

The run files run Backbone from the folder above their own, and read the inputs from
`./Helsinki-DHC-model/inputData`. So the folder has to sit directly in the Backbone folder and
keep this name. It does not change Backbone's own files or other models.

To update later, run `git pull` in the model folder. Git refuses to overwrite a file you have
changed, so keep your own versions under new names (see below).



## Run

Two run files, for Windows:

| File | Runs | Writes to `results/` |
|---|---|---|
| `run-schedule-1d.cmd` | a quick test: one day, day 150, with the debug file | `results_day150_1d.gdx`, `debug_day150_1d.gdx` |
| `run-schedule-365d.cmd` | a full year, from day 1 | `results_day1_365d.gdx` |

Double-click one, or start it from a command prompt. The two lines at the top of each choose
the days:

    set /a START=1       first day solved
    set /a D=365         how many days

The start of the time series and the start of the run are set in two places:

- **The workbook sets the time series.** `RunSetup` C13:E13 is the date the time series
  start from, and the workbook always gives the model 8760 hours (365 days) from that date as
  `t000001` ... `t008760`. As published, the date is 1 January 2025, so `t000001` is the first hour of 2025; with
  1 June 2024 there, `t000001` would be the first hour of 1 June 2024.
- **The two switches set the run inside those 8760 hours.** `--startDay` is the first day
  solved, counted from the workbook's start date, and `--modelledDays` is how many days are
  solved. `START=1` and `D=365` solve the whole window, and `START=150` solves its 150th day,
  whatever date that is.

Only a run that reaches day 365 ends the largest storages at the level they started from.

On any system, the full-year run from the Backbone folder is:

    gams Backbone.gms --input_dir=./Helsinki-DHC-model/inputData --input_file_excel=HelsinkiDHC-inputData.xlsx --input_excel_index=INDEX --input_excel_checkdate=checkDate --output_dir=./Helsinki-DHC-model/results --output_file=results_day1_365d.gdx --init_file=scheduleInit.gms --startDay=1 --modelledDays=365

| Option | What it sets | Default |
|---|---|---|
| `--startDay` | the first day solved, counted from the start date in `RunSetup` (day 1 = that date) | 1 |
| `--modelledDays` | how many days are solved | 365 |
| `--debug` | 1 also writes the debug file, with Backbone's internal sets and parameters | 0 |
| `--input_file_excel` | the input workbook in `inputData/` | |

`warnings.log` beside the results notes the horizon the run picked. Backbone's documentation
explains what `results.gdx` holds and how to read it.



## Change the inputs

All input data is in `inputData/HelsinkiDHC-inputData.xlsx`. Its `RunSetup` sheet chooses what a
run models: the three years below, and which cities are active (I5:I7). The other sheets
follow Backbone's input format, which Backbone's documentation describes.

### Choose the years

`RunSetup` takes three years, and each sets a different part of the inputs. They are kept
apart on purpose, so that a future system can be run on any year's weather and under past or
future prices.

| Cell | Name | Sets | Choices |
|---|---|---|---|
| C5 | unit year | the unit fleet of that year, the heat trade capacities between the cities, and how heat supply changes in the future years: 1 up to 2025, and in Helsinki 0.979, 0.950 and 0.920 for 2030, 2035 and 2040 (Espoo and Vantaa in rows 52-54). For 2030-2040 the unit adjustments in rows 98-119 also apply. | 2016-2025, 2030, 2035, 2040 |
| C9 | price year | fuel prices, the EU ETS CO2 price, taxes and fees, and the average electricity price (rows 128-160). For 2016-2025 these are that year's values, the electricity price the average of its hourly prices; for 2030-2040 they are projections. Each row has a user adjustment added on top. | 2016-2025, 2030, 2035, 2040 |
| C13:E13 | time-series start | the 8760 hours the model sees: heat supply, district cooling demand, temperatures (and through them the heat pump COPs), the hourly shape of the electricity price, and the forecasts | any day from 1.1.2016 to 1.1.2025 |

How they combine, hour by hour:

- **Heat supply** is the time-series window's hourly supply, times the unit year's multiplier.
  The weather of the time-series years is kept: a cold year brings more heat demand into any
  scenario.
- **Electricity price** is the time-series window's hourly price, scaled so that its average
  is the price year's average. The window gives the shape, the price year the level. When the
  price year is the time-series year and the window starts on 1 January, the prices are the
  ones that occurred. The price forecast is built from the 2023-2025 prices and scaled to the
  same average.
- **Fuel and CO2 prices, taxes and fees** follow the price year alone.
- **Unit maintenance breaks** are fixed calendar dates in the summer, whatever the window start.
- **The Varanto storage** starts from a level set by the start month (sheet `varanto_starts`).

The hourly shape of the electricity price comes from the time-series year, and it has changed
a lot: in 2016-2019 the cheapest twentieth of the hours still cost 18-28 EUR/MWh, while in
2023-2025 it was at zero or below. A scenario run on an older time-series year inherits the
older shape.

Typical combinations:

| Purpose | Unit year | Price year | Time-series start |
|---|---|---|---|
| reproduce a past year, as the validation does | Y | Y | 1 January Y |
| a future system under projected prices | 2030, 2035 or 2040 | the same | any; it picks the weather |
| a future system under a past market, such as the 2022 price crisis | 2030, 2035 or 2040 | 2016-2025 | any |
| a past fleet under future prices | 2016-2025 | 2030-2040 | any; it runs, and `RunSetup` E9 warns about the pairing |

`RunSetup` C19 checks the choices. The pairing warning in E9 does not stop a run.

**Recalculate and save the workbook in Excel after a change.** A run reads the values the
workbook last stored, and many cells are formulas, so a value written by a script without
Excel's recalculation does not reach the run.

To keep your own scenario beside the published one, copy the workbook to a new name such as
`HelsinkiDHC-inputData-scen1.xlsx`, copy the run file, and change `--input_file_excel` in the
copy. Git ignores both copies, so `git pull` leaves them alone.



## Data sources

- **Heat supply.** Helsinki's hourly district heating supply is Helen's open data,
  https://www.helen.fi/en/about-us/helen/open-data. Espoo and Vantaa follow the same hourly
  profile, scaled to their annual supply in the district heating statistics of Energiateollisuus
  ry (Finnish Energy). The
  `dhSupply` and `RunSetup` sheets show the factors. Supply here is heat sold plus network
  losses, without the heat traded between the cities.
- **Electricity prices.** The hourly prices for Finland are from the ENTSO-E Transparency
  Platform, https://transparency.entsoe.eu/.
- **Validation statistics.** See Validation below.



## Validation

`HelsinkiDHC-validation.html` compares ten history runs, the calendar years 2016-2025, with
the published statistics of those years: Energiateollisuus ry's district heating statistics
and the Energy Authority's verified EU ETS emissions per installation. Open it in a browser.

`validation-scripts/` rebuilds it. `statistics.csv` holds every statistic the report reads, each
with the file, sheet and cell it came from. The source workbooks are not redistributed here and
are available from their publishers. `validation-scripts/readme.md` describes the steps, and
`statistics-notes.md` the definitions and the known doubts in the statistics.



## Files

| Path | What |
|---|---|
| `run-schedule-1d.cmd` | A one day test run file |
| `run-schedule-365d.cmd` | A full-year run file |
| `inputData/HelsinkiDHC-inputData.xlsx` | all input data, and the `RunSetup` choices |
| `inputData/scheduleInit.gms` | the run structure: horizon, time steps, forecasts |
| `inputData/changes.inc` | the model's additions to Backbone's standard features |
| `inputData/1_options.gms`, `modelsInit.gms`, `timeAndSamples.inc` | GAMS options and Backbone's set-up files |
| `results/` | where the run files write their results |
| `HelsinkiDHC-validation.html` | the validation report |
| `validation-scripts/` | the scripts and statistics behind the report |
