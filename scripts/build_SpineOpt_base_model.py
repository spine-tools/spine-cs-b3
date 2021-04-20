#!/usr/bin/env python
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 16:30 04/09/2020

import sys
import os

dirname = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(dirname, 'backbone-to-spineopt'))
from gdx2spinedb import io_config
from gdx2spinedb.import_ts import SpineDBImporter, generate_time_index
from bb2spineopt import *

from modify_SpineOpt_db import *
from spineopt_structure import *

default_alternative = "Base"

dir_bb_spine_db, dir_spineopt_db = sys.argv[1:3]
bb_spine_db = io_config.open_spinedb(dir_bb_spine_db, create_new_db=False)
spineopt_db = io_config.open_spinedb(dir_spineopt_db, create_new_db=False)

if len(sys.argv) >= 4:
    # the 4th argument is a placeholder for json template
    dir_json = sys.argv[3]
    io_config.import_json(dir_json, spineopt_db)

source_db = bb_spine_db.export_spinedb()

time_index = generate_time_index(2021, full_year=True, leap=False)

# nodes with timeseries demand (ts_influx)
# electricity node: south Finland, 75FI
importer_spineopt = demand_time_series(
    source_db, 'elec', '75FI', time_index, 'f00', _auto_alternative=False, _base_alternative='f00'
)
importer_spineopt.import_data(spineopt_db)
importer_spineopt = node_parameters(source_db, 'elec', '75FI', time_index)
importer_spineopt.import_data(spineopt_db)
# other relevant nodes for 75FI, excluding the water
grid__node_w_ts = set([
    tuple(x[1][:2]) for x in source_db['relationships']
    if all([x[0] == 'ts_grid__node__f', x[1][0] != 'water', x[1][0] != 'elec'])
])

# the nodes of no use in the modelled system
# nodes "75FI_smaWoo_17PP", "75FI_logRes_17PP" are not in use as the 17PP related units are excluded
# the capacity of unit__to_node for nodes "75FI_bioSto_01He", "75FI_bioSto_02Es", "75FI_bioSto_03Va" are too small, 1e-6
# nodes "75FI_indRes_01He", "75FI_indRes_02Es", "75FI_indRes_03Va" lack expected ts_influx
excluded_nodes = ["75FI_smaWoo_17PP", "75FI_logRes_17PP",
                  "75FI_bioSto_01He", "75FI_bioSto_02Es", "75FI_bioSto_03Va",
                  "75FI_indRes_01He", "75FI_indRes_02Es", "75FI_indRes_03Va"]
for (grid, node) in grid__node_w_ts:
    if all(['75FI' in node, node not in excluded_nodes]):
        importer_spineopt = demand_time_series(
            source_db, grid, node, time_index, 'f00', _auto_alternative=False, _base_alternative='f00'
        )
        importer_spineopt.import_data(spineopt_db)
        importer_spineopt = node_parameters(source_db, grid, node, time_index)
        # allow energy spill for heat and cool nodes
        if any([grid == 'heat', grid == 'cool']):
            importer_spineopt = dummy_unit_for_node(importer_spineopt, node, f"Spill_{node}", "from_node")
        importer_spineopt.import_data(spineopt_db)
    else:
        continue

# units
# exclude unit 75FI_rusImport as the system is supposed to be self-sustained
master_units = set([
    x[1][2] for x in source_db['relationships']
    if all([x[0] == 'grid__node__unit__io', 'elec' in x[1], '75FI' in x[1]])
])
# hydro power units, to be excluded
hydro_units = set([
    x[1][2] for x in source_db['relationships']
    if all([x[0] == 'grid__node__unit__io', 'water' in x[1]])
])
# other units to be excluded
excluded_units = set([
    x[1] for x in source_db['objects']
    if all([x[0] == 'unit', '75FI_rusImport' in x[1]])
])
master_units = master_units.difference(hydro_units, excluded_units)
grid__node__unit_master = [
    tuple(x[1][:3]) for x in source_db['relationships']
    if all([x[0] == 'grid__node__unit__io', 'elec' in x[1], '75FI' in x[1]])
]
for (grid, node, unit) in grid__node__unit_master:
    if unit in master_units:
        # units operating on the master grid, i.e. electricity, and without explicit effLevel
        if unit in ['75FI_PV2', '75FI_Wind2']:
            importer_spineopt = unit_parameters(source_db, grid, node, unit, time_index, _eff_level=2)
            importer_spineopt.import_data(spineopt_db)
        # units operating on the master grid, i.e. electricity, and with explicit effLevel
        else:
            importer_spineopt = unit_parameters(source_db, grid, node, unit, time_index, _p_unit=True)
            importer_spineopt.import_data(spineopt_db)
    else:
        continue

# capacity factors for corresponding units, e.g. solar PV and wind
# automatically include multiple units to one flow, e.g. units 75FI_PV and 75FI_PV2 to the PV flow
for (flow, node) in [('PV', '75FI'), ('wind', '75FI')]:
    importer_spineopt = capacity_factor_time_series(
        source_db, flow, node, 'elec', time_index, 'f00', _auto_alternative=False, _base_alternative='f00', _mode="node"
    )
    importer_spineopt.import_data(spineopt_db)

# units operating on affiliated grids and with explicit effLevel
# units not related to the master grid, i.e. elec
affiliated_units = set([
    x[1] for x in source_db['objects']
    if all([
        x[0] == 'unit', '75FI' in x[1],
        '17PP-10PO' not in x[1], '19La-10PO' not in x[1],
        '75FI_indRes_01He' not in x[1], '75FI_indRes_02Es' not in x[1], '75FI_indRes_03Va' not in x[1]
    ])
])
# excluding units with '17PP-10PO' and '19La-10PO', linking to region 74FI, is particularly for case B3
# the 3 indRes units are excluded as their source nodes lack fuelling data (ts_influx)
affiliated_units = affiliated_units.difference(master_units, hydro_units, excluded_units)
grid__node__unit_affiliated = [
    tuple(x[1][:3]) for x in source_db['relationships']
    if all([x[0] == 'grid__node__unit__io', 'elec' not in x[1], 'water' not in x[1]])
]
for (grid, node, unit) in grid__node__unit_affiliated:
    if unit in master_units:
        importer_spineopt = unit_parameters(source_db, grid, node, unit, time_index)
        importer_spineopt.import_data(spineopt_db)
    # model fuel supply in detail,
    elif unit in affiliated_units:
        importer_spineopt = unit_parameters(source_db, grid, node, unit, time_index, _p_unit=True)
        importer_spineopt.import_data(spineopt_db)

# supplement node parameters for new nodes without timeseries demand (ts_influx) and imported with affiliated_units
grid__node_wo_ts = set([
    tuple(x[:2]) for x in grid__node__unit_affiliated if '74FI' not in x[1]
]).difference(grid__node_w_ts)

# the following nodes are not used in the case B3 system
# exclude node rusElc as the system is supposed to be self-sustained
excluded_nodes = ["rusElc", "Biomass_High_1", "Biomass_Low_1", "Coal_1", "Lignite_1", ]

for (grid, node) in grid__node_wo_ts:
    if node in excluded_nodes:
        continue
    importer_spineopt = node_parameters(source_db, grid, node, time_index)
    importer_spineopt.import_data(spineopt_db)

# units having bi outputs/inputs, e.g. CHPs
unit_list = set([
    x[1][0] for x in source_db['relationships'] if all([x[0] == 'unit__constraint__node', ])
])

unit__node_1__node_2 = list()
for _unit in unit_list:
    if '75FI' not in _unit:
        continue
    unit__constraint__node = [
        x[1] for x in source_db['relationships'] if all([x[0] == 'unit__constraint__node', _unit in x[1]])
    ]
    for _item in unit__constraint__node:
        _node_pair = sorted([x[2] for x in unit__constraint__node if x[:2] == _item[:2]])
        _node_pair.insert(0, _unit)
        unit__node_1__node_2.append(tuple(_node_pair))
unit__node_1__node_2 = set(unit__node_1__node_2)

for (unit, node_1, node_2) in unit__node_1__node_2:
    importer_spineopt = unit_bi_inputs_outputs(source_db, unit, node_1, node_2)
    importer_spineopt.import_data(spineopt_db)

# emissions
fuel_node__unit = [
    tuple(x[1][1:3]) for _unit in master_units.union(affiliated_units)
    for x in source_db['relationships'] if all([x[0] == 'grid__node__unit__io', 'fuel' in x[1], _unit in x[1]])
]

fuel_node__emission = [
    tuple(x[1]) for x in source_db['relationships'] if x[0] == 'node__emission'
]

# list of [grid, demand_node, policy, emission]
emission_tax = [
    x[1] for x in source_db['relationship_parameter_values'] if x[0] == 'grid__node__policy__emission'
]

for (fuel_node, unit) in fuel_node__unit:
    # no unit has both input and output on the same grid
    if unit in master_units:
        # the emission of units such as heatpumps and abscool that consume elec is counted on the elec grid
        # the emission of units such as CHPs that have other output in addition to elec is counted on the elec grid
        (grid, demand_node) = [
            tuple(x[1][:2]) for x in source_db['relationships']
            if all([x[0] == 'grid__node__unit__io', 'elec' in x[1], unit in x[1]])
        ][0]
    # all fuelled affiliated units have singular output to one grid
    elif unit in affiliated_units:
        (grid, demand_node) = [
            tuple(x[1][:2]) for x in source_db['relationships']
            if all([
                x[0] == 'grid__node__unit__io', 'elec' not in x[1], 'water' not in x[1], unit in x[1], 'output' in x[1]
            ])
        ][0]
    else:
        continue

    # a fuel can have multiple types of emission
    emissions = [x[1] for x in fuel_node__emission if fuel_node in x]
    for _emission in emissions:
        importer_spineopt = unit_emissions(
            source_db, "elec", demand_node, fuel_node, unit,
            _emission_name=_emission, _alternative='Base', _create_structure=False
        )
        importer_spineopt.import_data(spineopt_db)

# connections for electricity export and heat nodes
grid__node__node = [
    x[1] for x in source_db['relationships'] if all([x[0] == 'grid__node__node', any(['elec' in x[1], 'heat' in x[1]])])
]

for (grid, node_1, node_2) in grid__node__node:
    # in case B3, model only the electricity export for 75FI
    if (grid, node_1, node_2) == ('elec', '75FI', 'elec_export'):
        importer_spineopt = connection_for_node(
            source_db, grid, node_1, node_2, _alternative='Base', _create_structure=True
        )
        importer_spineopt.import_data(spineopt_db)
        importer_spineopt = node_parameters(source_db, 'elec', 'elec_export', time_index, _alternative='Base')
        # add a dummy consumption unit for electricity export w.r.t. SpineOpt modelling
        importer_spineopt = dummy_unit_for_node(
            importer_spineopt, 'elec_export', 'Consumption_elec_export', 'from_node', _alternative='Base'
        )
        importer_spineopt.import_data(spineopt_db)
    # replicate the heat network within 75FI, i.e. southern Finland
    elif all([grid == 'heat', '75FI' in node_1, '75FI' in node_2]):
        # all heat nodes and the corresponding parameters have been imported already
        importer_spineopt = connection_for_node(
            source_db, grid, node_1, node_2, _alternative='Base', _create_structure=False
        )
        importer_spineopt.import_data(spineopt_db)

# add dummy unit to the master node, i.e. 75FI
importer_spineopt = dummy_unit_for_node(
    importer_spineopt, "75FI", "dummy_75FI", "to_node", _alternative=default_alternative, vom_cost=100000.0
)
importer_spineopt = dummy_unit_for_node(importer_spineopt, "75FI", "dummy_75FI", "from_node", vom_cost=100000.0)
importer_spineopt.import_data(spineopt_db)

# add curtailment unit for the renewables
importer_spineopt = SpineDBImporter()
for unit in ['75FI_Wind', '75FI_Wind2', '75FI_PV', '75FI_PV2']:
    importer_spineopt = dummy_unit_for_node(importer_spineopt, f"source_{unit}", f"Curtailment_{unit}", "from_node")
importer_spineopt.import_data(spineopt_db)

# expand the capacity of some generation units (basically the renewables) to make the system self-sustained
# according to the generation units under plan
spineopt_db_export = spineopt_db.export_spinedb()
# Nuclear generation units
unit_name = '75FI_Nuclear'
demand_node = '75FI'
# the nuclear capacity will expand with one unit retiring and two to be committed (1600 + 1200MW),
# i.e. the number of units remains (5 units) with the total capacity adding up to 5590MW
new_total_capacity = 5594.0
new_number_of_units = 6
importer_spineopt = adapt_start_up_costs_of_units(
    spineopt_db_export, unit_name, demand_node, new_total_capacity, _new_number_of_units=new_number_of_units,
    _unit_constraint='Startup_fuel_75FI_Nuclear'
)

importer_spineopt.import_data(spineopt_db)

importer_spineopt = modify_generation_capacity_of_units(
    spineopt_db_export, unit_name, demand_node, new_total_capacity, _new_number_of_units=new_number_of_units
)
importer_spineopt.import_data(spineopt_db)

# Wind power generation units
importer_spineopt = modify_generation_capacity_of_units(
    spineopt_db_export, '75FI_Wind', '75FI', 11330.0, _new_number_of_units=2614, _source_node_name='source_75FI_Wind'
)
importer_spineopt.import_data(spineopt_db)

# escalate GasCHP unit by 3 folds
importer_spineopt = SpineDBImporter()
GasCHP_units = [x[1] for x in spineopt_db_export["objects"] if all([x[0] == "unit", "GasCHP" in x[1]])]
importer_spineopt.object_parameter_values += [
    ('unit', unit, 'number_of_units', 3, default_alternative) for unit in GasCHP_units
]
importer_spineopt.import_data(spineopt_db)

# set up model and the related structure
name_model = f"CS_B3_75FI_excl_hydro_and_reserves"
# the following two functions come from spineopt_structure.py
spineopt_b3_default_model(name_model, default_alternative, _target_spineopt_db=spineopt_db)
default_report_output(_target_spineopt_db=spineopt_db, _model_name=name_model)