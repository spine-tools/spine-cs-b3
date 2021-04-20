#!/usr/bin/env python  
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 11:48 28/10/2020

"""
Functions to configure the structure of a SpineOpt model from SpineDB database.

:author: J. Huang (VTT)
:date:   28.10.2020
"""

import sys
import os
import pandas as pd

dirname = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(dirname, 'backbone-to-spineopt'))
from gdx2spinedb import io_config
from gdx2spinedb.import_ts import SpineDBImporter, generate_time_index


# create model objects and the corresponding structures, an example of the "Base" alternative
def spineopt_b3_default_model(_model_name: str, _alternative, _target_spineopt_db=None):
    """
    :param _model_name:
    :param _alternative: ('name_alternative', 'description') or simply 'name_alternative'
    :param _target_spineopt_db:
    :return:
    """
    name_stochastic_scenario = "deterministic"
    name_stochastic_structure = "default"
    name_temporal_block_1 = "tb1_core"
    name_temporal_block_2 = "tb2_look_ahead"

    # initialise a spinedb importer
    _temp_importer = SpineDBImporter()

    if _alternative != "Base":
        _temp_importer.alternatives.append(_alternative)

    _temp_importer.objects += [
        ("model", _model_name),
        ("stochastic_scenario", name_stochastic_scenario),
        ("stochastic_structure", name_stochastic_structure),
        ("temporal_block", name_temporal_block_1),
        ("temporal_block", name_temporal_block_2),
    ]

    _temp_importer.object_parameter_values += [
        ("model", _model_name, "duration_unit", "hour", _alternative),
        ("model", _model_name, "model_start",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=1, day=1, hour=0))}, _alternative),
        ("model", _model_name, "model_end",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=12, day=30, hour=0))}, _alternative),
        ("model", _model_name, "roll_forward", {"type": "duration", "data": "8h"}, _alternative),
        ("temporal_block", name_temporal_block_1, "block_start", {"type": "duration", "data": "0h"}, _alternative),
        ("temporal_block", name_temporal_block_1, "block_end", {"type": "duration", "data": "1D"}, _alternative),
        ("temporal_block", name_temporal_block_1, "resolution", {"type": "duration", "data": "1h"}, _alternative),
        ("temporal_block", name_temporal_block_2, "block_start", {"type": "duration", "data": "1D"}, _alternative),
        ("temporal_block", name_temporal_block_2, "block_end", {"type": "duration", "data": "2D"}, _alternative),
        ("temporal_block", name_temporal_block_2, "resolution", {"type": "duration", "data": "8h"}, _alternative),
    ]

    _temp_importer.relationships += [
        ("model__default_stochastic_structure", (_model_name, name_stochastic_structure)),
        ("model__default_temporal_block", (_model_name, name_temporal_block_1)),
        ("model__default_temporal_block", (_model_name, name_temporal_block_2)),
        ("model__stochastic_structure", (_model_name, name_stochastic_structure)),
        ("model__temporal_block", (_model_name, name_temporal_block_1)),
        ("model__temporal_block", (_model_name, name_temporal_block_2)),
        ("stochastic_structure__stochastic_scenario", (name_stochastic_structure, name_stochastic_scenario)),
    ]

    _temp_importer.relationship_parameter_values += [
        ("stochastic_structure__stochastic_scenario", (name_stochastic_structure, name_stochastic_scenario),
         "weight_relative_to_parents", 1.0, _alternative),
    ]
    if _target_spineopt_db:
        _temp_importer.import_data(_target_spineopt_db)
    return _temp_importer


def spineopt_b3_model_horizon_alternatives(_model_name: str, _target_spineopt_db=None):
    _temp_importer = SpineDBImporter()

    alternative_1 = "Jan"
    alternative_2 = "Jul"

    _temp_importer.alternatives += [alternative_1, alternative_2]

    _temp_importer.objects.append(("model", _model_name))
    _temp_importer.object_parameter_values += [
        ("model", _model_name, "model_start",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=1, day=1, hour=0))}, alternative_1),
        ("model", _model_name, "model_end",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=2, day=1, hour=0))}, alternative_1),
        ("model", _model_name, "model_start",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=7, day=1, hour=0))}, alternative_2),
        ("model", _model_name, "model_end",
         {"type": "date_time", "data": str(pd.Timestamp(year=2021, month=8, day=1, hour=0))}, alternative_2),
    ]

    if _target_spineopt_db:
        _temp_importer.import_data(_target_spineopt_db)
    return _temp_importer, alternative_1, alternative_2


def spineopt_b3_temporal_alternative(model_name: str, _target_spineopt_db=None, **kwargs):
    """
    :param model_name:
    :param _target_spineopt_db:
    :param kwargs: node = [node_name_1, node_name_2], unit = [unit_name_1, unit_name_2]
    :return:
    """
    _temp_importer = SpineDBImporter()
    temporal_block_1 = "tb3_fuel"
    temporal_block_2 = "tb4_fuel_look_ahead"
    _alternative = "Base"
    active_alternative = "low_resolution"

    _temp_importer.alternatives.append([active_alternative, "for PtL nodes with storage"])

    _temp_importer.objects += [
        ("model", model_name),
        ("temporal_block", temporal_block_1),
        ("temporal_block", temporal_block_2),
    ]

    _temp_importer.object_parameter_values += [
        ("temporal_block", temporal_block_1, "block_start", {"type": "duration", "data": "0h"}, _alternative),
        ("temporal_block", temporal_block_1, "block_end", {"type": "duration", "data": "1D"}, _alternative),
        ("temporal_block", temporal_block_1, "resolution", {"type": "duration", "data": "1h"}, _alternative),
        ("temporal_block", temporal_block_1, "resolution", {"type": "duration", "data": "8h"}, active_alternative),
        ("temporal_block", temporal_block_2, "block_start", {"type": "duration", "data": "1D"}, _alternative),
        ("temporal_block", temporal_block_2, "block_end", {"type": "duration", "data": "2D"}, _alternative),
        ("temporal_block", temporal_block_2, "resolution", {"type": "duration", "data": "8h"}, _alternative),
        ("temporal_block", temporal_block_2, "resolution", {"type": "duration", "data": "1D"}, active_alternative),
    ]

    _temp_importer.relationships += [
        ("model__temporal_block", (model_name, temporal_block_1)),
        ("model__temporal_block", (model_name, temporal_block_2)),
    ]

    for k, v in kwargs.items():
        if k == "node":
            for node in v:
                _temp_importer.relationships += [
                    ("node__temporal_block", (node, temporal_block_1)),
                    ("node__temporal_block", (node, temporal_block_2)),
                ]
        elif k == "unit":
            for unit in v:
                _temp_importer.relationships += [
                    ("units_on__temporal_block", (unit, temporal_block_1)),
                    ("units_on__temporal_block", (unit, temporal_block_2)),
                ]
        else:
            continue

    if _target_spineopt_db:
        _temp_importer.import_data(_target_spineopt_db)
    return _temp_importer, active_alternative

def default_report_output(_target_spineopt_db=None, _model_name: str = None):
    """
    :param _target_spineopt_db: an instance of gdx2spinedb.spinedb.SpineIO, claimed via io_config.open_spinedb()
    :param _model_name:
    :return:
    """
    _temp_importer = SpineDBImporter()

    _temp_importer.objects += [
        ("output", "unit_flow"),
        ("output", "units_started_up"),
        ("output", "units_shut_down"),
        ("output", "units_available"),
        ("output", "units_on"),
        ("output", "connection_flow"),
        ("output", "node_state"),
        ("output", "node_slack_pos"),
        ("output", "node_slack_neg"),
        ("output", "node_injection"),
        ("output", "units_mothballed"),
        ("output", "unit_flow_op"),
        ("output", "units_invested"),
        ("output", "nonspin_ramp_up_unit_flow"),
        ("output", "start_up_unit_flow"),
        ("output", "units_invested_available"),
        ("output", "ramp_up_unit_flow"),
        ("output", "nonspin_units_started_up"),
        ("output", "total_costs"),
        ("output", "variable_om_costs"),
        ("output", "fixed_om_costs"),
        ("output", "taxes"),
        ("output", "operating_costs"),
        ("output", "fuel_costs"),
        ("output", "unit_investment_costs"),
        ("output", "connection_investment_costs"),
        ("output", "storage_investment_costs"),
        ("output", "start_up_costs"),
        ("output", "shut_down_costs"),
        ("output", "objective_penalties"),
        ("output", "connection_flow_costs"),
        ("output", "renewable_curtailment_costs"),
        ("output", "ramp_costs"),
    ]
    _temp_importer.objects += [
        ("report", "all_objective_terms"),
        ("report", "all_variables"),
    ]
    _temp_importer.relationships += [
        ("report__output", ("all_objective_terms", x[1])) for x in _temp_importer.objects[18:-2]
    ]
    _temp_importer.relationships += [
        ("report__output", ("all_variables", x[1])) for x in _temp_importer.objects[:18]
    ]
    if _model_name:
        _temp_importer.relationships += [
            ("model__report", (_model_name, x[1])) for x in _temp_importer.objects[-2:]
        ]
    if _target_spineopt_db:
        _temp_importer.import_data(_target_spineopt_db)
    return _temp_importer


def build_scenario(scenario, *affiliated_alternatives, alternatives_to_be_created: list = None):
    """
    :param scenario: ('name_scenario', active: bool, 'description') or simply 'name_scenario'
    :param affiliated_alternatives: ('name_alternative', 'description') or simply 'name_alternative',
                                    the alternatives are added in the written rank per se,
                                    the rightmost alternative prioritises over the others in parameter values
    :param alternatives_to_be_created: ['name_alternative_1', ('name_alternative_2', 'description_2')]
    :return: an instance of gdx2spinedb.spinedb.SpineIO
    """
    if alternatives_to_be_created is None:
        alternatives_to_be_created = []
    _temp_importer = SpineDBImporter()
    _temp_importer.scenarios.append(scenario)
    _temp_importer.alternatives += alternatives_to_be_created
    if isinstance(scenario, tuple):
        scenario = scenario[0]
    alternative_name_list = [x[0] if isinstance(x, tuple) else x for x in affiliated_alternatives]
    _temp_importer.scenario_alternatives += [(scenario, x) for x in alternative_name_list]
    return _temp_importer


def set_scenarios(_target_spineopt_db=None, *scenarios):
    """
    :param _target_spineopt_db: an instance of gdx2spinedb.spinedb.SpineIO, acquired via io_config.open_spinedb()
    :param scenarios: instances of gdx2spinedb.import_ts.SpineDBImporter, acquired via build_scenario()
    :return:
    """
    _temp_importer = SpineDBImporter()
    for scenario in scenarios:
        _temp_importer += scenario

    if _target_spineopt_db:
        _temp_importer.import_data(_target_spineopt_db)
    return _temp_importer


if __name__ == "__main__":
    
    dir_spineopt_db = sys.argv[1]
    spineopt_model_db = io_config.open_spinedb(dir_spineopt_db, create_new_db=False)

    # model name is defined in build_SpineOpt_model_b3.py, names for storage nodes are defined in build_PtX.py
    tb_importer, tb_alternative = spineopt_b3_temporal_alternative(
        "CS_B3_75FI_excl_hydro_and_reserves", _target_spineopt_db=spineopt_model_db,
        node=['PtL_H2_tank', 'PtL_gasoline_tank'], unit=['PtL_gasoline_production']
    )

    model_horizon_importer, horizon_alt_1, horizon_alt_2 = spineopt_b3_model_horizon_alternatives(
        "CS_B3_75FI_excl_hydro_and_reserves", _target_spineopt_db=spineopt_model_db
    )

    alternative_category_1 = [
        'no_transport', 'transport_low_EV', 'transport_all_EV'
    ]
    alternative_category_2 = ['no_flex_discharge', 'all_flex_discharge']
    alternative_category_3 = ['no_PtL', 'PtL_power_to_gasoline']

    # build core scenarios
    scenario_base = build_scenario(
        ('Base_energy_system', True, 'electricity and heat only'), 'Base', 'no_transport', 'no_flex_discharge', 'no_PtL'
    )
    scenarios_base_transport = SpineDBImporter()
    for alt_horizon in [horizon_alt_1, horizon_alt_2]:
        for alt_transport in alternative_category_1[1:]:
            for alt_discharge in alternative_category_2:
                for alt_ptl in alternative_category_3:
                    scenarios_base_transport += build_scenario(
                        (f'{alt_transport[10:]}__{alt_discharge}__{alt_ptl}__{alt_horizon}', True, ''),
                        'Base', alt_transport, alt_discharge, alt_ptl, alt_horizon
                    )
                    if alt_ptl != "no_PtL":
                        scenarios_base_transport += build_scenario(
                            (f'{alt_transport[10:]}__{alt_discharge}__{alt_ptl}__{alt_horizon}__{tb_alternative}', True,
                             ''),
                            'Base', alt_transport, alt_discharge, alt_ptl, alt_horizon, tb_alternative
                        )
    set_scenarios(spineopt_model_db, scenario_base, scenarios_base_transport)

    # build default model objects
    target_db = spineopt_model_db.export_spinedb()
    model_names = [x[1] for x in target_db["objects"] if x[0] == "model"]
    importer_spineopt = default_report_output(spineopt_model_db, model_names[0])
