
* =============================================================================
* --- Additional Model Definitions --------------------------------------------
* =============================================================================


* --- Helsinki DHC Model user parameters --------------------------------------

// first day solved and how many days. %startDay% is replaced where it is compiled, and this
// file is compiled before scheduleInit.gms, so the defaults are set here as well.
$if not set startDay $setglobal startDay 1
$if not set modelledDays $setglobal modelledDays 365



* --- Large storages end the year where they start ------------------------------
* Varanto hot and warm and the Mustikkamaa pool (dh-hel1-sto1) start from their reference
* (boundStart). Each must end at the same level: v_state at t008760 = reference constant.
* Pinned only when the solved days reach day 365, whose last hour is t008760; a run that
* ends earlier gets no pin, even if its horizon reaches t008760. Soft, at the default
* penalty: read r_qUserconstraint. A node not active in the run year gets no constraint.

Set pinned_node(node) "Large storages pinned at t008760 to their reference"
    / 'dh-van2-sto2-elec', 'dh-van2-sto2-DH', 'dh-hel1-sto1' /;
$onMulti
Set group / 'storageEnd-van2-hot', 'storageEnd-van2-warm', 'storageEnd-hel1' /;
$offMulti
Set pinned_group(group, node) "End-pin group of each large storage"
    / 'storageEnd-van2-hot'.'dh-van2-sto2-elec', 'storageEnd-van2-warm'.'dh-van2-sto2-DH',
      'storageEnd-hel1'.'dh-hel1-sto1' /;
Parameter pin_level(node) "End level of each pinned storage, the reference constant (MWh)";
Scalar pin_lastDay "Last day the run solves";
pin_lastDay = %startDay% + %modelledDays% - 1;

loop(pinned_group(group, pinned_node(node))
        $ { pin_lastDay >= 365
            and p_gn('storage', node, 'isActive') > 0
            and p_gnBoundaryPropertiesForStates('storage', node, 'reference', 'useConstant') },
    // an Eps reference is a zero target: no constant row
    pin_level(node) = p_gnBoundaryPropertiesForStates('storage', node, 'reference', 'constant')
        * [ p_gnBoundaryPropertiesForStates('storage', node, 'reference', 'multiplier')
            + 1 $ (not p_gnBoundaryPropertiesForStates('storage', node, 'reference', 'multiplier')) ];
    p_userconstraint(group, 'storage', node, '-', '-', 'v_state') = 1;
    p_userconstraint(group, 't008760', '-', '-', '-', 'timestep') = 1;
    p_userconstraint(group, '-', '-', '-', '-', 'eq') = 1;
    p_userconstraint(group, '-', '-', '-', '-', 'constant') $ (pin_level(node) > 0) = pin_level(node);
);
display pin_level;



* --- Minimum use of oil and gas heat-only boilers ------------------------------
* Real oil and gas boilers run some hours every winter, for test runs and to lift the supply
* temperature at the edges of the network, though the model would rarely dispatch them. Each
* city's oil and gas heat-only boilers must therefore give at least bmin_flh x their DH capacity
* of heat in a year, in the coldest hours. In each hour:
*     DH output of the city's boilers of that fuel >= min(capacity, k x max(0, demand - threshold))
* with the threshold the demand of the city's bmin_hours-th highest hour and k set so that the
* year sums to the minimum. Only active units on active DH nodes count, so retiring half of the
* capacity halves the minimum, and a city or a fuel without an active boiler gets no constraint.
* A heat-only boiler here takes fuel from grid oil or gas (oil wins for a unit with both) and
* outputs to grid dh only. CHP units, bio and waste boilers, heat pumps and e-boilers get none.
* The minimum is heat, whichever fuel the boiler burns (oil boilers can also burn bio-oil).

Scalar bmin_hours "Coldest hours of the year the minimum is spread over (h)" / 500 /;
Set bmin_fuel(grid) "Fuel grids whose heat-only boilers have a minimum use" / oil, gas /;
Set bmin_city "Cities with a minimum" / hel, esp, van /;
Set bmin_cityNode(bmin_city, *) "DH nodes of each city" / hel.(dh-hel1, dh-hel2), esp.dh-esp, van.(dh-van1, dh-van2) /;
// Vantaa's oil boilers ran about 7 h a year in 2016-2025, Helsinki's about 59 h and Espoo's about 42 h
Table bmin_flh(bmin_city, bmin_fuel) "Minimum full-load hours a year of heat-only boilers, by city and fuel (h)"
         oil   gas
    hel   50    50
    esp   50    50
    van   30    30
;
$onMulti
Set group / 'hel-oilMin', 'hel-gasMin', 'esp-oilMin', 'esp-gasMin', 'van-oilMin', 'van-gasMin' /;
$offMulti
Set bmin_group(group, bmin_city, bmin_fuel) "User constraint of each city and fuel"
    / 'hel-oilMin'.hel.oil, 'hel-gasMin'.hel.gas, 'esp-oilMin'.esp.oil, 'esp-gasMin'.esp.gas,
      'van-oilMin'.van.oil, 'van-gasMin'.van.gas /;
Set bmin_iter "Bisection steps for the threshold" / i1*i60 /;
Set
    bmin_gIn(grid, unit) "Grids a unit takes input from"
    bmin_gOut(grid, unit) "Grids a unit outputs to"
    bmin_node(node) "Active DH nodes"
    bmin_unit(unit, bmin_city, bmin_fuel) "Active heat-only boilers counted in each city's minimum"
    bmin_t(t) "Hours of the data year"
;
Parameter
    bmin_cap(bmin_city, bmin_fuel) "Active DH capacity of the counted boilers (MW)"
    bmin_target(bmin_city, bmin_fuel) "Minimum heat from them in a year (MWh)"
    bmin_supply(bmin_city, t) "City DH supple (demand + losses), ts_influx f00 (MW)"
    bmin_threshold(bmin_city) "Demand of the city's bmin_hours-th highest hour (MW)"
    bmin_excess(bmin_city) "Demand above the threshold, summed over the year (MWh)"
    bmin_summary(bmin_city, bmin_fuel, *) "Boiler minimum: capacity MW, minimum MWh, floor sum MWh, threshold MW"
;
Scalars bmin_lo, bmin_hi, bmin_mid;

loop((grid, node, unit, param_gnu) $ p_gnu_io(grid, node, unit, 'input', param_gnu), bmin_gIn(grid, unit) = yes;);
loop((grid, node, unit, param_gnu) $ p_gnu_io(grid, node, unit, 'output', param_gnu), bmin_gOut(grid, unit) = yes;);
// isActive: this model sets it on every unit and node, and a city switched off in RunSetup leaves it empty
bmin_node(node) $ {p_gn('dh', node, 'isActive') > 0} = yes;
bmin_unit(unit, bmin_city, bmin_fuel)
    $ { p_unit(unit, 'isActive') > 0
        and bmin_gIn(bmin_fuel, unit)
        and [sameAs(bmin_fuel, 'oil') or not bmin_gIn('oil', unit)]
        and not sum(grid $ {bmin_gOut(grid, unit) and not sameAs(grid, 'dh')}, 1)
        and sum(bmin_node(node) $ bmin_cityNode(bmin_city, node), p_gnu_io('dh', node, unit, 'output', 'capacity')) > 0
      } = yes;
bmin_cap(bmin_city, bmin_fuel)
    = sum((unit, bmin_node(node)) $ {bmin_unit(unit, bmin_city, bmin_fuel) and bmin_cityNode(bmin_city, node)},
          p_gnu_io('dh', node, unit, 'output', 'capacity'));
bmin_target(bmin_city, bmin_fuel) = bmin_flh(bmin_city, bmin_fuel) * bmin_cap(bmin_city, bmin_fuel);

// the shape: hours 1-8760 of the city's demand, above the bmin_hours-th highest hour
bmin_t(t) $ {ord(t) > 1 and ord(t) <= 8761} = yes;
bmin_supply(bmin_city, bmin_t)
    $ sum(bmin_fuel, bmin_target(bmin_city, bmin_fuel))
    = - sum(bmin_node(node) $ bmin_cityNode(bmin_city, node), ts_influx('dh', node, 'f00', bmin_t));
loop(bmin_city $ sum(bmin_fuel, bmin_target(bmin_city, bmin_fuel)),
    bmin_lo = 0;
    bmin_hi = smax(bmin_t, bmin_supply(bmin_city, bmin_t));
    loop(bmin_iter,
        bmin_mid = (bmin_lo + bmin_hi) / 2;
        if(sum(bmin_t $ {bmin_supply(bmin_city, bmin_t) > bmin_mid}, 1) > bmin_hours,
            bmin_lo = bmin_mid;
        else
            bmin_hi = bmin_mid;
        );
    );
    bmin_threshold(bmin_city) = bmin_hi;
);
bmin_excess(bmin_city) $ bmin_threshold(bmin_city)
    = sum(bmin_t, max(0, bmin_supply(bmin_city, bmin_t) - bmin_threshold(bmin_city)));

// one eachTimestep gt user constraint per city and fuel, its RHS in ts_groupPolicy
loop(bmin_group(group, bmin_city, bmin_fuel) $ {bmin_target(bmin_city, bmin_fuel) > 0 and bmin_excess(bmin_city) > 0},
    ts_groupPolicy(group, 'userConstraintRHS', bmin_t)
        = min(bmin_cap(bmin_city, bmin_fuel),
              bmin_target(bmin_city, bmin_fuel) / bmin_excess(bmin_city)
              * max(0, bmin_supply(bmin_city, bmin_t) - bmin_threshold(bmin_city)));
    p_userconstraint(group, 'dh', node, unit, '-', 'v_gen')
        $ {bmin_unit(unit, bmin_city, bmin_fuel) and bmin_node(node) and bmin_cityNode(bmin_city, node)
           and p_gnu_io('dh', node, unit, 'output', 'capacity') > 0}
        = 1;
    p_userconstraint(group, 'userConstraintRHS', '-', '-', '-', 'ts_groupPolicy') = 1;
    p_userconstraint(group, '-', '-', '-', '-', 'gt') = 1;
    p_userconstraint(group, '-', '-', '-', '-', 'eachTimestep') = 1;
    bmin_summary(bmin_city, bmin_fuel, 'floorSum_MWh') = sum(bmin_t, ts_groupPolicy(group, 'userConstraintRHS', bmin_t));
);
bmin_summary(bmin_city, bmin_fuel, 'capacity_MW') = bmin_cap(bmin_city, bmin_fuel);
bmin_summary(bmin_city, bmin_fuel, 'minimum_MWh') = bmin_target(bmin_city, bmin_fuel);
bmin_summary(bmin_city, bmin_fuel, 'threshold_MW') $ bmin_cap(bmin_city, bmin_fuel) = bmin_threshold(bmin_city);
display bmin_summary;


