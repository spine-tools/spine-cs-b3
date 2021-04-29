#!/usr/bin/env python  
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 17:00 28/12/2020

import sys

sys.path.append('.\\backbone-to-spineopt')
from gdx2spinedb.import_ts import SpineDBImporter


def adapt_start_up_costs_of_units(
        _spineopt_db_export, _unit_name: str, _demand_node_name: str, _new_total_capacity,
        _new_number_of_units=1, _unit_constraint: str = None, search_alternative='Base', new_alternative: str = 'Base'
):
    """
    adapt the start up related costs info linearly per change of unit capacity
    :param new_alternative:
    :param search_alternative:
    :param _spineopt_db_export: an export dictionary for spineDB, obtained via gdx2spinedb.spinedb.export_spinedb()
    :param _unit_name:
    :param _demand_node_name:
    :param _new_total_capacity:
    :param _new_number_of_units:
    :param _unit_constraint: the unit_constraint that holds the corresponding start_up_coefficient of the unit
    :return:
    """
    # initialise a spinedb importer
    _importer_spineopt = SpineDBImporter()
    if new_alternative != search_alternative:
        _importer_spineopt.alternatives.append(new_alternative)

    _original_db = _spineopt_db_export
    _original_number_of_units = [
        x[3] for x in _original_db['object_parameter_values']
        if all([x[:3] == ('unit', _unit_name, 'number_of_units'), x[-1] == search_alternative])
    ][0]
    _original_unit_capacity = [
        x[3] for x in _original_db['relationship_parameter_values']
        if all([
            x[:3] == ('unit__to_node', [_unit_name, _demand_node_name], 'unit_capacity'), x[-1] == search_alternative
        ])
    ][0]
    _original_start_up_cost = [
        x[3] for x in _original_db['object_parameter_values']
        if all([x[:3] == ('unit', _unit_name, 'start_up_cost'), x[-1] == search_alternative])
    ][0]

    _new_unit_capacity = _new_total_capacity / _new_number_of_units
    _new_start_up_cost = _new_unit_capacity / _original_unit_capacity * _original_start_up_cost
    _importer_spineopt.object_parameter_values += [
        ("unit", _unit_name, "start_up_cost", _new_start_up_cost, new_alternative),
        ("unit", _unit_name, "number_of_units", _new_number_of_units, new_alternative),
    ]

    if _unit_constraint:
        _original_start_up_coefficient = [
            x[3] for x in _original_db['relationship_parameter_values']
            if all([
                x[:3] == (
                    'unit__unit_constraint', [_unit_name, _unit_constraint], 'units_started_up_coefficient'
                ),
                x[-1] == search_alternative
            ])
        ][0]

        _new_start_up_coefficient = _new_unit_capacity / _original_unit_capacity * _original_start_up_coefficient
        _importer_spineopt.relationship_parameter_values += [
            (
                "unit__unit_constraint", [_unit_name, _unit_constraint], "units_started_up_coefficient",
                _new_start_up_coefficient, new_alternative
            ),
        ]

    return _importer_spineopt


def modify_generation_capacity_of_units(
        _spineopt_db_export, _unit_name: str, _demand_node_name: str, _new_total_capacity,
        _new_number_of_units: int = None, _source_node_name: str = None,
        search_alternative='Base', new_alternative: str = 'Base'
):
    """
    :param new_alternative:
    :param search_alternative:
    :param _spineopt_db_export: an export dictionary for spineDB, obtained via gdx2spinedb.spinedb.export_spinedb()
    :param _unit_name:
    :param _demand_node_name:
    :param _new_total_capacity:
    :param _new_number_of_units:
    :param _source_node_name: placeholder to specify the unit's source flow node if such a node exists
                              the default name of the node follows f"source_{_unit_name}"
    :return: an instance of gdx2spinedb.import_ts.SpineDBImporter class
    """
    # initialise a spinedb importer
    _importer_spineopt = SpineDBImporter()
    if new_alternative != search_alternative:
        _importer_spineopt.alternatives.append(new_alternative)

    _original_db = _spineopt_db_export
    _original_number_of_units = [
        x[3] for x in _original_db['object_parameter_values']
        if all([x[:3] == ('unit', _unit_name, 'number_of_units'), x[-1] == search_alternative])
    ][0]
    _original_unit_capacity = [
        x[3] for x in _original_db['relationship_parameter_values']
        if all([
            x[:3] == ('unit__to_node', [_unit_name, _demand_node_name], 'unit_capacity'), x[-1] == search_alternative
        ])
    ][0]
    _original_total_capacity = _original_unit_capacity * _original_number_of_units

    if _new_number_of_units:
        _number_of_units = _new_number_of_units
        # renew fix_units_on w.r.t. the new number of units if there is such in the original database
        fix_units_on = [
            x[3] for x in _spineopt_db_export['object_parameter_values']
            if all([x[:3] == ('unit', _unit_name, 'fix_units_on'), x[-1] == search_alternative])
        ]
        if fix_units_on:
            _importer_spineopt.object_parameter_values.append(
                ('unit', _unit_name, 'fix_units_on', _number_of_units, new_alternative)
            )
    else:
        _number_of_units = _original_number_of_units
    _unit_capacity = _new_total_capacity / _number_of_units

    if _source_node_name:
        _original_source_flow_value = [
            x[3] for x in _original_db['object_parameter_values']
            if all([x[:3] == ('node', _source_node_name, 'demand'), x[-1] == search_alternative])
        ][0].to_dict()

        _new_source_flow = {
            k: v * _new_total_capacity / _original_total_capacity for k, v in
            _original_source_flow_value['data'].items()
        }

        if 'index' in _original_source_flow_value.keys():
            _new_source_flow_value = {
                "type": "time_series", "data": _new_source_flow, "index": _original_source_flow_value['index']
            }
        else:
            _new_source_flow_value = {"type": "time_series", "data": _new_source_flow}

        _importer_spineopt.object_parameter_values.append(
            ('node', _source_node_name, 'demand', _new_source_flow_value, new_alternative)
        )

    _importer_spineopt.object_parameter_values.append(
        ('unit', _unit_name, 'number_of_units', _number_of_units, new_alternative)
    )
    _importer_spineopt.relationship_parameter_values.append(
        ('unit__to_node', [_unit_name, _demand_node_name], 'unit_capacity', _unit_capacity, new_alternative)
    )

    return _importer_spineopt
