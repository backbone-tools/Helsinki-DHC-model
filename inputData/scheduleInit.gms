$ontext
This file is part of Backbone.

Backbone is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Backbone is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Lesser General Public License for more details.

You should have received a copy of the GNU Lesser General Public License
along with Backbone.  If not, see <http://www.gnu.org/licenses/>.
$offtext


* =============================================================================
* --- Horizon length by the largest storage -----------------------------------
* =============================================================================

* A seasonal storage needs a horizon that sees the next season; daily and weekly 
* storages do not. The horizon is hz_daysLong when any active storage holds 
* hz_threshold or more, else hz_daysShort. 
* Size = upwardLimit constant x multiplier x energyStoredPerUnitOfState (MWh);
* a storage limited only by a time series is not counted. 
* warnings.log notes the pick.

// define new scalars needed for the selection
Scalars
    hz_threshold  "Storage size from which the long horizon is used (MWh)" / 30000 /
    hz_daysShort  "Horizon when every storage is below hz_threshold (days)" / 28 /
    hz_daysLong   "Horizon when a storage reaches hz_threshold (days)" / 120 /
    hz_maxStorage "Largest active storage of the run (MWh)"
    hz_days       "Horizon of the run (days)"
;
Parameter hz_size(grid, node) "Size of each active storage (MWh)";

// Define simulation horizon and moving horizon optimization "speed"
hz_size(gn_state(grid, node)) 
    $ p_gnBoundaryPropertiesForStates(grid, node, 'upwardLimit', 'useConstant')
    = p_gnBoundaryPropertiesForStates(grid, node, 'upwardLimit', 'constant')
      * p_gnBoundaryPropertiesForStates(grid, node, 'upwardLimit', 'multiplier')
      * p_gn(grid, node, 'energyStoredPerUnitOfState');
hz_maxStorage = max(0, smax(gn_state(grid, node), hz_size(grid, node)));
hz_days = hz_daysShort + (hz_daysLong - hz_daysShort) $ (hz_maxStorage >= hz_threshold);

// print to warnings.log
put f_warn "Note: scheduleInit.gms set a " hz_days:0:0 "-day horizon: the largest storage";
loop(gn_state(grid, node) $ {hz_maxStorage > 0 and hz_size(grid, node) = hz_maxStorage}, put " " node.tl:0;);
put " holds " hz_maxStorage:0:0 " MWh (" hz_daysLong:0:0 " days from " hz_threshold:0:0 " MWh, else " hz_daysShort:0:0 ")." /;
    

* =============================================================================
* --- Model Definition - Schedule ---------------------------------------------
* =============================================================================

if (mType('schedule'),
    m('schedule') = yes; // Definition, that the model exists by its name

* =============================================================================
* --- Model Time Structure ----------------------------------------------------
* =============================================================================

* --- Define Key Execution Parameters in Time Indeces -------------------------

    // Define simulation start and end time indeces
    mSettings('schedule', 't_start') = (%startDay%-1)*24 + 1;  // First time step to be solved, 1 corresponds to t000001 (t000000 will then be used for initial status of dynamic variables)
    mSettings('schedule', 't_end') = mSettings('schedule', 't_start') + 24*%modelledDays% -1;  // Last time step to be included in the solve (may solve and output more time steps in case t_jump does not match)

    mSettings('schedule', 't_horizon') = 24*hz_days; // How many active time steps the solve contains (aggregation of time steps does not impact this, unless the aggregation does not match)
    mSettings('schedule', 't_jump') = 24*1; // How many time steps the model rolls forward between each solve

    // Define length of data for proper circulation
    //mSettings('schedule', 'dataLength') = 8760;

    // Define the duration of a single time-step in hours
    mSettings('schedule', 'stepLengthInHours') = 1;


* --- Define Time Step Intervals ----------------------------------------------

    // Define the time step intervals in time-steps
    // Aggregating further timesteps for faster solve
    mInterval('schedule', 'stepsPerInterval', 'c000') = 1;
    mInterval('schedule', 'lastStepInIntervalBlock', 'c000') = 24*1+3;
    mInterval('schedule', 'stepsPerInterval', 'c001') = 3;
    mInterval('schedule', 'lastStepInIntervalBlock', 'c001') = 24*3;
    mInterval('schedule', 'stepsPerInterval', 'c002') = 6;
    mInterval('schedule', 'lastStepInIntervalBlock', 'c002') = 24*5;
    mInterval('schedule', 'stepsPerInterval', 'c003') = 12;
    mInterval('schedule', 'lastStepInIntervalBlock', 'c003') = 24*7;
    mInterval('schedule', 'stepsPerInterval', 'c004') = 24;
    mInterval('schedule', 'lastStepInIntervalBlock', 'c004') = mSettings('schedule', 't_horizon');


* --- Define Unit Approximations ----------------------------------------------

    // Define the last time step for each unit aggregation and efficiency level (3a_periodicInit.gms ensures that there is a effLevel until t_horizon)
    mSettingsEff('schedule', 'level1') = mInterval('schedule', 'lastStepInIntervalBlock', 'c000');
    mSettingsEff('schedule', 'level2') = mSettings('schedule', 't_horizon');



* --- Define Samples ----------------------------------------------------------

    // Number of samples used by the model
    mSettings('schedule', 'samples') = 1;

    // Define Initial and Central samples
    ms_initial('schedule', 's000') = yes;
    ms_central('schedule', 's000') = yes;

    // Define time span of samples
    msStart('schedule', 's000') = 1;
    msEnd('schedule', 's000') = mSettings('schedule', 't_start') + mSettings('schedule', 't_end') + mSettings('schedule', 't_horizon');


    // Define the probability (weight) of samples
    p_msProbability('schedule', s) = 0;
    p_msProbability('schedule', 's000') = 1;
    p_msWeight('schedule', s) = 0;
    p_msWeight('schedule', 's000') = 1;
    p_msAnnuityWeight('schedule', s) = 0;
    p_msAnnuityWeight('schedule', 's000') = 1;



* --- data circulation ----------------------------------------------------

    option clear = ff;
    option ff < p_mfProbability;

    gn_tsCirculation('ts_influx', gn('dh', node), ff, 'interpolateStepChange', 'isActive') = 1;
    gn_tsCirculation('ts_influx', gn('dh', node), ff, 'interpolateStepChange', 'length') = 24;


* =============================================================================
* --- Model Forecast Structure ------------------------------------------------
* =============================================================================

    // Define the number of forecasts used by the model
    mSettings('schedule', 'forecasts') = 1;    // f00 + 1 (f01)

    // Define which nodes and timeseries use forecasts
    Option clear = gn_forecasts;  // By default includes everything, so clear first
    gn_forecasts(gn('dh',node), 'ts_influx') = yes;
    gn_forecasts(gn('elec', node), 'ts_priceNew') = yes;


    // Define which units and timeseries use forecasts
    Option clear = unit_forecasts;  // By default includes everything, so clear first
    //unit_forecasts('XXX', 'ts_unit') = yes;  // declare a time serie that has forecasts. Syntax: (unit, timeseries)

    // Define forecast properties and features
    mSettings('schedule', 't_perfectForesight') = 0;               // How many time steps after there is perfect foresight (including t_jump)
    mSettings('schedule', 't_forecastJump') = 24;                  // How many time steps before new forecast is available
    mSettings('schedule', 't_improveForecastNew') = 168;           // Number of time steps ahead of time that the forecast is improved on each solve.


    // Define Realized and Central forecasts
    mf_realization('schedule', f) = no;
    mf_realization('schedule', 'f00') = yes;
    mf_central('schedule', f) = no;
    mf_central('schedule', 'f01') = yes;


    // Define forecast probabilities (weights)
    p_mfProbability('schedule', f) = 0;
    p_mfProbability('schedule', 'f00') = 1;
    p_mfProbability('schedule', 'f01') = 1;

    // discount factor of samples
    p_s_discountFactor('s000') = 1;


* =============================================================================
* --- Solver Features ---------------------------------------------------------
* =============================================================================

* --- Solver speed improvements -------------------------------

    mSettings('schedule', 'reducedDummies') = 1;
    mSettings('schedule', 'scalingMethod') = 0;
    mSettings('schedule', 'automaticRoundings') = 1;


); // END if(mType)
