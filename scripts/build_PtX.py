#!/usr/bin/env python  
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 11:47 25/01/2021

import pandas as pd
import time
import sys
import os
from functools import reduce

dirname = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(dirname, 'backbone-to-spineopt'))
from spineopt_structure import *
from gdx2spinedb.io_config import open_spinedb
from bb2spineopt import dummy_unit_for_node
from gdx2spinedb.import_ts import SpineDBImporter, generate_time_index


def operating_time(func):
    def wrapper(*x):
        t0 = time.time()
        func_output = func(*x)
        delta_t = time.time() - t0
        print(f"time elapsed for execution: {delta_t} s")
        return func_output

    return wrapper
    # a function f with @operating_time maintain its original output


@operating_time
def multiply(*items):
    result = reduce((lambda x, y: x * y), items)
    return result


class SpineOptPowerToXModule:
    def __init__(self, y: int, excel, _spinedb_importer=None, _target_spineopt_db=None, _timeseries_repeat=False):
        """
        :param y:
        :param excel:
        :param _spinedb_importer: an instance of gdx2spinedb.import_ts.SpineDBImporter
        :param _target_spineopt_db:
               an instance of gdx2spinedb.spinedb.SpinedbIO obtained by gdx2spinedb.io_config.open_spinedb()
        """
        self.year = y
        self.excel = excel  # an excel file object obtained from pd.ExcelFile()
        self.sheets = ['Data_Parameters4py']
        self._spinedb_importer = _spinedb_importer
        self._spineopt_db = _target_spineopt_db
        self._timeseries_repeat = _timeseries_repeat

    def set_year(self, y: int):
        self.year = y

    def set_importer(self, _spinedb_importer):
        self._spinedb_importer = _spinedb_importer

    def set_target_spineopt_db(self, _target_spineopt_db):
        self._spineopt_db = _target_spineopt_db

    @property
    def read_data(self):
        _p2x_data = []
        for sheet in self.sheets:
            _df = pd.read_excel(self.excel, sheet)
            _df = _df.reset_index(drop=True)
            _p2x_data.append(_df)
        return _p2x_data

    def add_alternative(self, alternative):
        """
        :param alternative: ('alternative_name', 'description') or simply 'alternative_name'
        :return:
        """
        self._spinedb_importer.alternatives.append(alternative)

    @property
    def parameters(self):
        return self.read_data[0]

    def control_alternative(self, active_alternative, create_alternative: bool = True):
        """
        A handy approach to control the activation of entities by setting the unit_capacity values to be 0
        :param active_alternative: ('name_alternative', 'description') or simply 'name_alternative'
        :param create_alternative:
        :return:
        """
        parameter = self._spinedb_importer.relationship_parameter_values
        if create_alternative:
            self._spinedb_importer.alternatives.append(active_alternative)

        for k, v in enumerate(parameter):
            if v[2] == 'unit_capacity' and v[4] != active_alternative:
                value_for_original_alternative = list(v)
                value_for_original_alternative[3] = 0
                value_for_original_alternative = tuple(value_for_original_alternative)
                parameter[k] = value_for_original_alternative

                value_for_active_alternative = list(v)
                value_for_active_alternative[4] = active_alternative
                value_for_active_alternative = tuple(value_for_active_alternative)
                parameter.append(value_for_active_alternative)
            else:
                continue

        parameter = self._spinedb_importer.object_parameter_values
        for k, v in enumerate(parameter):
            if v[2] == 'demand' and v[4] != active_alternative:
                value_for_original_alternative = list(v)
                value_for_original_alternative[3] = 0
                value_for_original_alternative = tuple(value_for_original_alternative)
                parameter[k] = value_for_original_alternative

                value_for_active_alternative = list(v)
                value_for_active_alternative[4] = active_alternative
                value_for_active_alternative = tuple(value_for_active_alternative)
                parameter.append(value_for_active_alternative)
            else:
                continue
        return None

    def import_to_spineopt(self, target_spineopt_db=None):
        _spineopt_db = self._spineopt_db
        if target_spineopt_db:
            _spineopt_db = target_spineopt_db
        if self._spinedb_importer and _spineopt_db:
            self._spinedb_importer.import_data(_spineopt_db)
        return None

    def find_parameter_value(self, **kwargs):
        _df = self.parameters
        for k, v in kwargs.items():
            _df = _df[_df[k] == v]
        if _df.empty:
            _value = None
        else:
            _value = _df['value'].item()
        return _value

    def fix_node_start_state(self, node_name: str, start_timestamp=None, start_state: int = None):
        """
        :param node_name:
        :param start_timestamp: a pandas.Timestamp(year=2021, month=1, day=1, hour=0)) instance
        :param start_state:
        :return: a timeseries data with the fix_node_state parameter at the first hour of the modelling year
        """
        if not start_timestamp:
            start_timestamp = str(pd.Timestamp(year=self.year, month=1, day=1, hour=0))
        else:
            start_timestamp = str(start_timestamp)
        excel_value = self.find_parameter_value(category='assumption', entity=f'{node_name}_start_state')
        if any([excel_value, excel_value == 0]):
            start_state = excel_value
        # either the start_state is None or nan; when the excel cell is empty, we get a nan float value
        if start_state != start_state:
            data = None
        elif start_state == 0:
            data = {
                "type": "time_series", "data": {start_timestamp: start_state}, "index": {"repeat": self._timeseries_repeat}
            }
        elif not start_state:
            data = None
        else:
            data = {
                "type": "time_series", "data": {start_timestamp: start_state}, "index": {"repeat": self._timeseries_repeat}
            }
        return data

    def conversion_process(
            self, process_name: str, sub_process_unit: str,
            input_node: str, input_node_commodity: str, output_node: str, output_node_commodity: str,
            alternative: str = 'Base', fueling_input_node: bool = False, output_node_storage: bool = True,
            **kwargs
    ):
        """
        :param output_node_storage:
        :param fueling_input_node:
        :param output_node_commodity:
        :param output_node:
        :param input_node_commodity:
        :param input_node:
        :param sub_process_unit:
        :param process_name:
        :param alternative:
        :return:
        """
        _temp_importer = SpineDBImporter()
        if self._spinedb_importer:
            _temp_importer = self._spinedb_importer

        # nodes and commodities
        _temp_importer.objects += [
            ('node', input_node), ('commodity', input_node_commodity),
            ('node', output_node), ('commodity', output_node_commodity),
        ]

        if output_node_storage:
            _temp_importer.object_parameter_values += [
                ('node', output_node, 'has_state', True, alternative),
                ('node', output_node, 'state_coeff', 1.0, alternative),
            ]
            if self.fix_node_start_state(output_node, start_state=None):
                _temp_importer.object_parameter_values.append(
                    (
                        'node', output_node, 'fix_node_state', self.fix_node_start_state(output_node, start_state=None),
                        alternative
                    )
                )

            _node_state_cap = self.find_parameter_value(category='assumption', entity=f'{output_node}_storage_capacity')
            if any([_node_state_cap, _node_state_cap == 0]):
                _temp_importer.object_parameter_values.append(
                    ('node', output_node, 'node_state_cap', _node_state_cap, alternative)
                )

        _temp_importer.relationships += [
            ("node__commodity", (input_node, input_node_commodity)),
            ("node__commodity", (output_node, output_node_commodity)),
        ]

        # unit and unit_constraints
        _unit_name = f'{process_name}_{sub_process_unit}'
        _unit_constraint = f'Eff_{process_name}_{input_node_commodity}_to_{output_node_commodity}'
        _temp_importer.objects += [('unit', _unit_name), ('unit_constraint', _unit_constraint)]

        _fom_cost = self.find_parameter_value(category='fom_cost', entity=_unit_name)
        if any([_fom_cost, _fom_cost == 0]):
            _temp_importer.object_parameter_values.append(('unit', _unit_name, 'fom_cost', _fom_cost, alternative))

        _temp_importer.object_parameter_values += [
            ('unit_constraint', _unit_constraint, 'constraint_sense', '==', alternative),
            ('unit_constraint', _unit_constraint, 'right_hand_side', 0, alternative),
        ]

        _fix_units_on = kwargs.get('fix_units_on', None)
        if _fix_units_on:
            _temp_importer.object_parameter_values.append(
                ('unit', _unit_name, 'fix_units_on', _fix_units_on, alternative)
            )

        _temp_importer.relationships += [
            ("unit__unit_constraint", (_unit_name, _unit_constraint)),
            ("unit__from_node", (_unit_name, input_node)),
            ("unit__from_node__unit_constraint", (_unit_name, input_node, _unit_constraint)),
            ("unit__to_node", (_unit_name, output_node)),
            ("unit__to_node__unit_constraint", (_unit_name, output_node, _unit_constraint)),
        ]

        _temp_importer.relationship_parameter_values += [
            (
                f"unit__{direction}_node", (_unit_name, node), 'unit_capacity',
                self.find_parameter_value(category=f'capacity_{direction}_{node}', entity=_unit_name), alternative
            )
            for node, direction in {input_node: 'from', output_node: 'to'}.items()
            if any([
                self.find_parameter_value(category=f'capacity_{direction}_{node}', entity=_unit_name),
                self.find_parameter_value(category=f'capacity_{direction}_{node}', entity=_unit_name) == 0
            ])
        ]

        _temp_importer.relationship_parameter_values.append(
            (
                "unit__to_node__unit_constraint", (_unit_name, output_node, _unit_constraint),
                'unit_flow_coefficient', -1, alternative
            )
        )

        _coefficient = self.find_parameter_value(
            category='flow_ratio', entity=f'{input_node_commodity}_to_{output_node_commodity}'
        )
        if not _coefficient:
            _coefficient = 1
        _temp_importer.relationship_parameter_values.append(
            (
                "unit__from_node__unit_constraint", (_unit_name, input_node, _unit_constraint),
                'unit_flow_coefficient', 1 / _coefficient, alternative
            )
        )

        # other affiliated components
        if fueling_input_node:
            dummy_unit_for_node(
                _temp_importer, input_node, f'Fueling_{input_node}', 'to_node', _alternative=alternative,
            )

        return _temp_importer


if __name__ == '__main__':
    default_alternative = "Base"
    
    dir_spineopt_db = sys.argv[1]
    spineopt_db = open_spinedb(dir_spineopt_db, create_new_db=False)
    
    for dir_xlsx in sys.argv[2:]:
        xlsx = pd.ExcelFile(dir_xlsx)

        p2g = SpineOptPowerToXModule(
            2021, xlsx, _spinedb_importer=SpineDBImporter(), _target_spineopt_db=spineopt_db, _timeseries_repeat=False
        )

        active_alternative = p2g.find_parameter_value(category='alternative_name', entity='is_PtL_active')
        p2g.add_alternative(active_alternative)
        default_alternative = active_alternative
        p2g.import_to_spineopt()

        p2g.set_importer(SpineDBImporter())
        p2g.conversion_process(
            'PtL', 'elec_to_H2', '75FI', 'elec', 'PtL_H2_tank', 'H2', alternative=default_alternative
        )
        p2g.import_to_spineopt()

        p2g.set_importer(SpineDBImporter())
        p2g.conversion_process(
            'PtL', 'gasoline_production', '75FI', 'elec', 'PtL_gasoline_tank', 'gasoline',
            alternative=default_alternative, fix_units_on=1.0
        )
        p2g.import_to_spineopt()

        p2g.set_importer(SpineDBImporter())
        p2g.conversion_process(
            'PtL', 'gasoline_production', 'PtL_H2_tank', 'H2', 'PtL_gasoline_tank', 'gasoline',
            alternative=default_alternative
        )
        p2g.import_to_spineopt()

        p2g.set_importer(SpineDBImporter())
        p2g.conversion_process(
            'PtL', 'gasoline_production', 'PtL_CO2_tank', 'Inflow_CO2', 'PtL_gasoline_tank', 'gasoline',
            alternative=default_alternative, fueling_input_node=True
        )
        p2g.import_to_spineopt()

        p2g.set_importer(SpineDBImporter())
        p2g.conversion_process(
            'PtL', 'gasoline_delivery', 'PtL_gasoline_tank', 'gasoline', 'transport_gasoline_station', 'gasoline',
            alternative=default_alternative, output_node_storage=False
        )
        p2g.import_to_spineopt()
