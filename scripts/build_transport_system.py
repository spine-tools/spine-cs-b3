#!/usr/bin/env python  
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 17:49 17/04/2020

# To convert EV data into demand curve

import pandas as pd
import time
import sys
from functools import reduce
import os

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


def _hybrid_units_via_availability(
        unit_1: str, direction_1: str, unit_2: str, direction_2: str,
        unit_constraint: str, common_node: str, common_availability, alternative: str
):
    """
    :param unit_1:
    :param direction_1: direction between unit_1 and the common node, from_node/to_node
    :param unit_2:
    :param direction_2:
    :param unit_constraint:
    :param common_node:
    :param common_availability: SpineDB value types
    :param alternative:
    :return:
    """
    _temp_importer = SpineDBImporter()
    _temp_importer.objects.append(('unit_constraint', unit_constraint))
    _temp_importer.object_parameter_values += [
        ('unit', unit_1, 'online_variable_type', 'unit_online_variable_type_linear', alternative),
        ('unit', unit_2, 'online_variable_type', 'unit_online_variable_type_linear', alternative),
        ('unit_constraint', unit_constraint, 'constraint_sense', '<=', alternative),
        ('unit_constraint', unit_constraint, 'right_hand_side', common_availability, alternative)
    ]

    _temp_importer.relationships += [
        ("unit__unit_constraint", (unit_1, unit_constraint)),
        ("unit__unit_constraint", (unit_2, unit_constraint)),
        (f"unit__{direction_1}__unit_constraint", (unit_1, common_node, unit_constraint)),
        (f"unit__{direction_2}__unit_constraint", (unit_2, common_node, unit_constraint)),
    ]
    _temp_importer.relationship_parameter_values += [
        ("unit__unit_constraint", (unit_1, unit_constraint), 'units_on_coefficient', 1, alternative),
        ("unit__unit_constraint", (unit_2, unit_constraint), 'units_on_coefficient', 1, alternative),
    ]
    return _temp_importer


def _unit_battery_charger(
        unit: str, unit_availability, elec_capacity,
        unit_constraint: str, elec_node: str, battery_node: str, alternative: str,
        conversion_eff=1, is_discharge: bool = False, flex_discharge_share: float = 1.0
):
    _temp_importer = SpineDBImporter()
    # to represent the active/effective share of the charger fleet, 100% by default
    cap_to_flow_rate = 1.0
    source_node = elec_node
    target_node = battery_node
    if is_discharge:
        source_node, target_node = target_node, source_node
        # to represent the active/effective share of the charger fleet being able to discharge
        cap_to_flow_rate = flex_discharge_share
    _temp_importer.objects += [
        ('unit', unit), ('unit_constraint', unit_constraint), ('node', source_node), ('node', target_node)
    ]
    _temp_importer.object_parameter_values += [
        ('unit', unit, 'unit_availability_factor', unit_availability, alternative),
        ('unit_constraint', unit_constraint, 'constraint_sense', '==', alternative),
        ('unit_constraint', unit_constraint, 'right_hand_side', 0, alternative)
    ]
    _temp_importer.relationships += [
        ("unit__unit_constraint", (unit, unit_constraint)),
        ("unit__to_node", (unit, target_node)),
        ("unit__to_node__unit_constraint", (unit, target_node, unit_constraint)),
        ("unit__from_node", (unit, source_node)),
        ("unit__from_node__unit_constraint", (unit, source_node, unit_constraint)),
    ]

    _temp_importer.relationship_parameter_values += [
        (
            "unit__to_node__unit_constraint", (unit, target_node, unit_constraint),
            'unit_flow_coefficient', -1, alternative
        ),
        ("unit__from_node", (unit, source_node), 'unit_capacity', elec_capacity, alternative),
        ("unit__from_node", (unit, source_node), 'unit_conv_cap_to_flow', cap_to_flow_rate, alternative),
        (
            "unit__from_node__unit_constraint", (unit, source_node, unit_constraint),
            'unit_flow_coefficient', conversion_eff, alternative
        ),
    ]
    return _temp_importer


class SpineOptTransportModule:
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
        self.sheets = ['Data_Parameters4py', 'Data_Timeseries_BEV', 'Data_Timeseries_PHEV']
        self._spinedb_importer = _spinedb_importer
        self._spineopt_db = _target_spineopt_db
        self._timeseries_repeat = _timeseries_repeat

    def set_year(self, y: int):
        self.year = y

    def set_importer(self, _spinedb_importer):
        self._spinedb_importer = _spinedb_importer

    def set_target_spineopt_db(self, _target_spineopt_db):
        self._spineopt_db = _target_spineopt_db

    def add_alternative(self, alternative):
        """
        :param alternative: ('alternative_name', 'description') or simply 'alternative_name'
        :return:
        """
        self._spinedb_importer.alternatives.append(alternative)

    @property
    def read_data(self):
        # generate the tailored dataset with respect to year and country
        _transport_system_data = []
        for sheet in self.sheets:
            _df = pd.read_excel(self.excel, sheet)
            _df = _df.reset_index(drop=True)
            _transport_system_data.append(_df)
        return _transport_system_data

    def time_index_year(self, leap=False, time_steps=None):
        year = self.year
        index = generate_time_index(year, relative_pos=(0, 0), full_year=True, leap=leap, frequency='H')
        index = [str(x) for x in index[:time_steps]]
        return index

    def ev_fleet_behaviour(self, ev_key: str = None, para_key: str = None, add_time_index=True):
        _skip = 1
        for k, v in enumerate(self.sheets[_skip:]):
            k += _skip
            if ev_key in v:
                _df = self.read_data[k]
                if para_key:
                    _df = _df[para_key]
                if add_time_index:
                    _df.index = self.time_index_year(time_steps=len(_df))
                return _df
            else:
                continue
        return None

    @property
    def parameters(self):
        return self.read_data[0]

    @property
    def fundamental_objects(self):
        _temp_importer = SpineDBImporter()
        if self._spinedb_importer:
            _temp_importer = self._spinedb_importer
        _df = self.parameters
        _temp_importer.objects += [
            (row['entity'], row['value']) for i, row in _df.iterrows() if row['category'] == 'spineopt_object'
        ]
        return _temp_importer

    def control_alternative(self, active_alternative, create_alternative: bool = True):
        """
        A handy approach to control the activation of entities by setting the unit_capacity values to be 0
        :param active_alternative: ('name_alternative', 'description') or simply 'name_alternative'
        :param create_alternative:
        :return:
        """
        if create_alternative:
            self._spinedb_importer.alternatives.append(active_alternative)

        parameter = self._spinedb_importer.relationship_parameter_values
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

    def _fix_node_start_state(self, node_name: str, start_timestamp=None, start_state: int = 0):
        """
        :param node_name:
        :param start_timestamp: a pandas.Timestamp(year=year, month=1, day=1, hour=0)) instance
        :param start_state:
        :return: a timeseries data with the fix_node_state parameter at the first hour of the modelling year
        """
        if not start_timestamp:
            start_timestamp = self.time_index_year()[0]
        else:
            start_timestamp = str(start_timestamp)
        if self.find_parameter_value(category='assumption', entity=f'{node_name}_start_state'):
            start_state = self.find_parameter_value(category='assumption', entity=f'{node_name}_start_state')
        data = {
            "type": "time_series", "data": {start_timestamp: start_state}, "index": {"repeat": self._timeseries_repeat}
        }
        return data

    def transport_utility(self, utility: str, alternative: str, *vehicle_types: str):
        """
        :param vehicle_types:
        :param utility:
        :param alternative:
        :return:
        """
        _temp_importer = SpineDBImporter()

        _utility_node_name = f'transport_all_{utility}_use'

        _temp_importer.objects += [('commodity', utility), ('node', _utility_node_name)]

        demand_data = 0.0
        for vehicle in vehicle_types:
            base_hourly_use = self.find_parameter_value(category='hourly_mileage', entity=f'transport_{vehicle}_use')
            if 'EV' in vehicle:
                df_demand = self.ev_fleet_behaviour(ev_key=vehicle, para_key='HOURLY_MILEAGE', add_time_index=True)
                demand_data += df_demand
            else:
                demand_data += base_hourly_use

        if isinstance(demand_data, pd.Series):
            _temp_importer.object_parameter_values.append(
                (
                    'node', _utility_node_name, 'demand',
                    {
                        "type": "time_series", "data": demand_data.to_dict(),
                        "index": {"repeat": self._timeseries_repeat}
                    },
                    alternative
                )
            )
        elif isinstance(demand_data, float):
            _temp_importer.object_parameter_values.append(
                ('node', _utility_node_name, 'demand', demand_data, alternative)
            )

        _temp_importer.relationships.append(("node__commodity", (_utility_node_name, utility)))

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer, _utility_node_name

    def ev_battery(self, vehicle_type: str, energy_flow: str, alternative: str):
        _temp_importer = SpineDBImporter()

        _battery_node_name = f'transport_{vehicle_type}_battery'
        _temp_importer.objects += [('commodity', energy_flow), ('node', _battery_node_name)]
        _node_state_cap = multiply(
            self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='CONNECTED', add_time_index=True),
            self.find_parameter_value(category='number_of_cars', entity=vehicle_type),
            self.find_parameter_value(category='BATTERY_CAPACITY', entity=_battery_node_name)
        ).to_dict()
        _temp_importer.object_parameter_values += [
            ('node', _battery_node_name, 'has_state', True, alternative),
            ('node', _battery_node_name, 'state_coeff', 1.0, alternative),
            (
                'node', _battery_node_name, 'node_state_cap',
                {"type": "time_series", "data": _node_state_cap, "index": {"repeat": self._timeseries_repeat}},
                alternative
            ),
            ('node', _battery_node_name, 'fix_node_state', self._fix_node_start_state(_battery_node_name), alternative),
        ]
        _temp_importer.relationships.append(("node__commodity", (_battery_node_name, energy_flow)))

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer, _battery_node_name

    def _ev_battery_state_ideal_net_change(
            self, vehicle_type: str, battery_node_name: str, alternative: str, build_basic_components: bool = True
    ):
        """
        the change of connected battery electricity if EVs leave and arrive with fully charged battery
        :param vehicle_type:
        :param battery_node_name:
        :param alternative:
        :param build_basic_components:
        :return:
        """
        _temp_importer = SpineDBImporter()
        # node state net change is modelled as negative demand
        _node_state_net_change = -(
            multiply(
                self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='ARRIVAL', add_time_index=True)
                - self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='LEAVING', add_time_index=True),
                self.find_parameter_value(category='number_of_cars', entity=vehicle_type),
                self.find_parameter_value(category='BATTERY_CAPACITY', entity=battery_node_name)
            )
        )

        if build_basic_components:
            _temp_importer.objects.append(('node', battery_node_name))

        _temp_importer.object_parameter_values.append(
            (
                'node', battery_node_name, 'demand',
                {
                    "type": "time_series", "data": _node_state_net_change.to_dict(),
                    "index": {"repeat": self._timeseries_repeat}
                },
                alternative
            )
        )

        return _temp_importer

    def _fix_ev_elec_consumption_on_road(
            self, vehicle_type: str, _utility_node_name: str, _battery_node_name: str, alternative: str,
            build_basic_components: bool = True
    ):
        _temp_importer = SpineDBImporter()

        _unit_name = f'transport_{vehicle_type}_motor'

        if build_basic_components:
            _temp_importer.objects += [('unit', _unit_name), ('node', _battery_node_name)]

            _temp_importer.relationships.append(("unit__from_node", (_unit_name, _battery_node_name)))

        elec_consumption = self.ev_fleet_behaviour(
            ev_key=vehicle_type, para_key='CONSUMPTION_ENTIRE_FLEET', add_time_index=True
        )
        _temp_importer.relationship_parameter_values.append(
            (
                "unit__from_node", (_unit_name, _battery_node_name), 'fix_unit_flow',
                {
                    "type": "time_series", "data": elec_consumption.to_dict(),
                    "index": {"repeat": self._timeseries_repeat}
                },
                alternative
            )
        )

        return _temp_importer

    def ev_motor(
            self, vehicle_type: str, _utility_node_name: str, _battery_node_name: str, alternative: str,
            fix_elec_use: bool = False
    ):
        _temp_importer = SpineDBImporter()

        _unit_name = f'transport_{vehicle_type}_motor'
        _unit_constraint = f'Eff_{_unit_name}'
        _temp_importer.objects += [('unit', _unit_name), ('unit_constraint', _unit_constraint)]
        _availability = 1 - self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='CONNECTED', add_time_index=True)
        _temp_importer.object_parameter_values += [
            ('unit_constraint', _unit_constraint, 'constraint_sense', '==', alternative),
            ('unit_constraint', _unit_constraint, 'right_hand_side', 0, alternative),
            (
                'unit', _unit_name, 'unit_availability_factor',
                {"type": "time_series", "data": _availability.to_dict(), "index": {"repeat": self._timeseries_repeat}},
                alternative
            ),
        ]
        _temp_importer.relationships += [
            ("unit__unit_constraint", (_unit_name, _unit_constraint)),
            ("unit__to_node", (_unit_name, _utility_node_name)),
            ("unit__to_node__unit_constraint", (_unit_name, _utility_node_name, _unit_constraint)),
            ("unit__from_node", (_unit_name, _battery_node_name)),
            ("unit__from_node__unit_constraint", (_unit_name, _battery_node_name, _unit_constraint)),
        ]

        efficiency = self.find_parameter_value(category='electric_motor_efficiency', entity=_unit_name)
        _temp_importer.relationship_parameter_values += [
            (
                "unit__to_node__unit_constraint", (_unit_name, _utility_node_name, _unit_constraint),
                'unit_flow_coefficient', -1, alternative
            ),
            (
                "unit__from_node__unit_constraint", (_unit_name, _battery_node_name, _unit_constraint),
                'unit_flow_coefficient', efficiency, alternative
            ),
        ]

        if fix_elec_use:
            _temp_importer += self._fix_ev_elec_consumption_on_road(
                vehicle_type, _utility_node_name, _battery_node_name, alternative, build_basic_components=False
            )
            _temp_importer += self._ev_battery_state_ideal_net_change(vehicle_type, _battery_node_name, alternative)
        else:
            transport_capacity_est = multiply(
                self.find_parameter_value(category='number_of_cars', entity=vehicle_type),
                self.find_parameter_value(category='average_speed', entity=_unit_name)
            )
            elec_capacity_est = transport_capacity_est / efficiency

            _temp_importer.relationship_parameter_values += [
                ("unit__to_node", (_unit_name, _utility_node_name), 'unit_capacity', transport_capacity_est,
                 alternative),
                ("unit__to_node", (_unit_name, _utility_node_name), 'unit_conv_cap_to_flow', 1, alternative),
                ("unit__from_node", (_unit_name, _battery_node_name), 'unit_capacity', elec_capacity_est, alternative),
                ("unit__from_node", (_unit_name, _battery_node_name), 'unit_conv_cap_to_flow', 1, alternative),
            ]

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer, _unit_name

    def ev_battery_charger(
            self, vehicle_type: str, _elec_node: str, _battery_node: str, alternative: str,
            enable_discharge: bool = False
    ):
        _temp_importer = SpineDBImporter()

        _unit_name_1 = f'transport_{vehicle_type}_charger'
        _unit_constraint = f'Eff_{_unit_name_1}'

        _availability = self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='CONNECTED', add_time_index=True)
        _availability = {
            "type": "time_series", "data": _availability.to_dict(), "index": {"repeat": self._timeseries_repeat}
        }

        elec_capacity_est = multiply(
            self.find_parameter_value(category='number_of_cars', entity=vehicle_type),
            self.find_parameter_value(category='BATTERY_CHARGER', entity=_battery_node)
        )
        efficiency = self.find_parameter_value(category='assumption', entity=f'Charging_efficiency_{vehicle_type}')

        _importer_charger = _unit_battery_charger(
            _unit_name_1, _availability, elec_capacity_est, _unit_constraint, _elec_node, _battery_node, alternative,
            conversion_eff=efficiency
        )
        _temp_importer += _importer_charger
        if enable_discharge:
            _unit_name_2 = f'transport_{vehicle_type}_charger_discharge'
            _unit_constraint = f'Eff_{_unit_name_2}'
            efficiency = self.find_parameter_value(category='assumption', entity=f'Discharge_efficiency_{vehicle_type}')
            discharge_share = self.find_parameter_value(category='assumption', entity=f'Discharge_share_{vehicle_type}')
            _importer_charger = _unit_battery_charger(
                _unit_name_2, _availability, elec_capacity_est, _unit_constraint, _elec_node, _battery_node,
                alternative, conversion_eff=efficiency, is_discharge=True, flex_discharge_share=discharge_share
            )
            _temp_importer += _importer_charger

            hybrid_constraint = f'transport_{vehicle_type}_flexible_charge'
            _importer_charger = _hybrid_units_via_availability(
                _unit_name_1, 'to_node', _unit_name_2, 'from_node', hybrid_constraint,
                _battery_node, _availability, alternative
            )
            _temp_importer += _importer_charger

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer

    def fuel_station(self, energy_flow: str, alternative: str):
        _temp_importer = SpineDBImporter()

        _station_node_name = f'transport_{energy_flow}_station'
        dummy_unit_for_node(
            _temp_importer,
            _station_node_name, f'Fueling_{_station_node_name}', 'to_node', _alternative=alternative,
            fuel_cost=self.find_parameter_value(category='assumption', entity=f'{energy_flow}_price')
        )

        _temp_importer.objects += [('commodity', energy_flow), ('node', _station_node_name)]
        _temp_importer.relationships.append(("node__commodity", (_station_node_name, energy_flow)))

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer, _station_node_name

    def _icv_engine_emission(
            self, _spinedb_importer, vehicle_type: str, utility: str, _station_node_name: str, emission_name: str,
            emission_cost: float, alternative: str
    ):
        _temp_importer = _spinedb_importer

        _unit_name = f'transport_{vehicle_type}_engine'
        _unit_constraint = f'Emission_{emission_name}_{_unit_name}'
        _sink_node = f'sink_{emission_name}_{utility}'
        _commodity = f'Emission_{emission_name}'
        dummy_unit_for_node(
            _temp_importer, _sink_node, f'Emission_{emission_name}_absorber', 'from_node', _alternative=alternative,
        )

        _temp_importer.objects += [
            ('commodity', _commodity), ('node', _sink_node), ('unit', _unit_name), ('unit_constraint', _unit_constraint)
        ]
        _temp_importer.object_parameter_values += [
            ('node', _sink_node, 'tax_out_unit_flow', emission_cost, alternative),
            ('unit_constraint', _unit_constraint, 'constraint_sense', '==', alternative),
            ('unit_constraint', _unit_constraint, 'right_hand_side', 0, alternative)
        ]
        _temp_importer.relationships += [
            ("node__commodity", (_sink_node, _commodity)),
            ("unit__unit_constraint", (_unit_name, _unit_constraint)),
            ("unit__to_node", (_unit_name, _sink_node)),
            ("unit__to_node__unit_constraint", (_unit_name, _sink_node, _unit_constraint)),
            ("unit__from_node", (_unit_name, _station_node_name)),
            ("unit__from_node__unit_constraint", (_unit_name, _station_node_name, _unit_constraint)),
        ]

        emission_factor = self.find_parameter_value(
            category='assumption', entity=f'{_unit_name}_{emission_name}_emission_factor'
        )
        _temp_importer.relationship_parameter_values += [
            (
                "unit__to_node__unit_constraint", (_unit_name, _sink_node, _unit_constraint),
                'unit_flow_coefficient', -1, alternative
            ),
            (
                "unit__from_node__unit_constraint", (_unit_name, _station_node_name, _unit_constraint),
                'unit_flow_coefficient', emission_factor, alternative
            ),
        ]

        return _temp_importer

    def icv_engine(
            self, vehicle_type: str, _utility_node_name: str, _station_node_name: str, alternative: str,
            availability_data
    ):
        _temp_importer = SpineDBImporter()

        _unit_name = f'transport_{vehicle_type}_engine'
        _unit_constraint = f'Eff_{_unit_name}'

        _temp_importer.objects += [('unit', _unit_name), ('unit_constraint', _unit_constraint)]
        _temp_importer.object_parameter_values += [
            ('unit', _unit_name, 'unit_availability_factor', availability_data, alternative),
            ('unit_constraint', _unit_constraint, 'constraint_sense', '==', alternative),
            ('unit_constraint', _unit_constraint, 'right_hand_side', 0, alternative)
        ]
        _temp_importer.relationships += [
            ("unit__unit_constraint", (_unit_name, _unit_constraint)),
            ("unit__to_node", (_unit_name, _utility_node_name)),
            ("unit__to_node__unit_constraint", (_unit_name, _utility_node_name, _unit_constraint)),
            ("unit__from_node", (_unit_name, _station_node_name)),
            ("unit__from_node__unit_constraint", (_unit_name, _station_node_name, _unit_constraint)),
        ]

        transport_capacity_est = multiply(
            self.find_parameter_value(category='number_of_cars', entity=vehicle_type),
            self.find_parameter_value(category='average_speed', entity=_unit_name)
        )
        efficiency = self.find_parameter_value(category='engine_efficiency', entity=_unit_name)
        _temp_importer.relationship_parameter_values += [
            ("unit__to_node", (_unit_name, _utility_node_name), 'unit_capacity', transport_capacity_est,
             alternative),
            ("unit__to_node", (_unit_name, _utility_node_name), 'unit_conv_cap_to_flow', 1, alternative),
            (
                "unit__to_node__unit_constraint", (_unit_name, _utility_node_name, _unit_constraint),
                'unit_flow_coefficient', -1, alternative
            ),
            (
                "unit__from_node__unit_constraint", (_unit_name, _station_node_name, _unit_constraint),
                'unit_flow_coefficient', efficiency, alternative
            ),
        ]

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer, _unit_name

    def build_icv_profile(
            self, availability_data, vehicle_type: str = None, utility: str = None, energy_flow: str = None,
            emission_name: str = None, alternative: str = 'Base', common_utility: bool = False
    ):
        if not self._spinedb_importer:
            self.set_importer(SpineDBImporter())

        _utility_node = f'transport_all_{utility}_use'
        _temp_importer, _station_node = self.fuel_station(energy_flow, alternative)
        _temp_importer, _powertrain = self.icv_engine(
            vehicle_type, _utility_node, _station_node, alternative, availability_data
        )

        _emission_cost = self.find_parameter_value(
            category='assumption', entity=f'{energy_flow}_{emission_name}_emission_cost'
        )

        _temp_importer += self._icv_engine_emission(
            self._spinedb_importer, vehicle_type, utility, _station_node, emission_name, _emission_cost, alternative
        )

        return _temp_importer

    def hybrid_powertrains(
            self, vehicle_type: str, utility_node: str, powertrain_1: str, powertrain_2: str,
            alternative: str = 'Base', fix_driving_distance_share: bool = True
    ):
        _temp_importer = SpineDBImporter()

        if fix_driving_distance_share:
            _driving_distance_share_1 = self.find_parameter_value(
                category='assumption', entity=f'hybrid_driving_distance_share_{powertrain_1}'
            )
            _driving_distance_share_2 = self.find_parameter_value(
                category='assumption', entity=f'hybrid_driving_distance_share_{powertrain_2}'
            )
            _ratio = _driving_distance_share_2 / _driving_distance_share_1
            _unit_constraint = f'Hybrid_powertrain_{vehicle_type}_driving_distance_share'
            _temp_importer.objects.append(('unit_constraint', _unit_constraint))

            _temp_importer.object_parameter_values += [
                ('unit_constraint', _unit_constraint, 'constraint_sense', '==', alternative),
                ('unit_constraint', _unit_constraint, 'right_hand_side', 0, alternative)
            ]

            _temp_importer.relationships += [
                ("unit__unit_constraint", (powertrain_1, _unit_constraint)),
                ("unit__unit_constraint", (powertrain_2, _unit_constraint)),
                ("unit__to_node__unit_constraint", (powertrain_1, utility_node, _unit_constraint)),
                ("unit__to_node__unit_constraint", (powertrain_2, utility_node, _unit_constraint)),
            ]
            _temp_importer.relationship_parameter_values += [
                (
                    "unit__to_node__unit_constraint", (powertrain_1, utility_node, _unit_constraint),
                    'unit_flow_coefficient', _ratio, alternative
                ),
                (
                    "unit__to_node__unit_constraint", (powertrain_2, utility_node, _unit_constraint),
                    'unit_flow_coefficient', -1, alternative
                ),
            ]
        else:
            _unit_constraint = f'Hybrid_powertrain_{vehicle_type}_bind'
            _temp_importer.objects += [
                ('unit_constraint', _unit_constraint), ('unit', powertrain_1), ('unit', powertrain_2),
            ]

            _hybrid_availability = 1 - self.ev_fleet_behaviour(
                ev_key=vehicle_type, para_key='CONNECTED', add_time_index=True
            )
            _hybrid_availability = {
                "type": "time_series", "data": _hybrid_availability.to_dict(),
                "index": {"repeat": self._timeseries_repeat}
            }
            _importer_hybrid = _hybrid_units_via_availability(
                powertrain_1, 'to_node', powertrain_2, 'to_node', _unit_constraint,
                utility_node, _hybrid_availability, alternative
            )
            _temp_importer += _importer_hybrid

        if self._spinedb_importer:
            self._spinedb_importer += _temp_importer

        return _temp_importer

    def build_ev_profile(
            self, vehicle_type: str = None, utility: str = None, fuel: str = None, source_node: str = None,
            alternative: str = 'Base', hybrid: bool = False,
            alternative_fuel: str = None, emission_name: str = None,
            fix_driving_distance_share: bool = True, fix_ev_use: bool = False, battery_discharge: bool = False
    ):
        if not self._spinedb_importer:
            self.set_importer(SpineDBImporter())

        self._spinedb_importer.objects.append(('commodity', fuel))
        self._spinedb_importer.relationships.append(('node__commodity', (source_node, fuel)))
        battery_fuel = f"{fuel}_battery"

        _utility_node = f'transport_all_{utility}_use'
        _temp_importer, _battery_node = self.ev_battery(vehicle_type, battery_fuel, alternative)
        _temp_importer, _powertrain_ev = self.ev_motor(
            vehicle_type, _utility_node, _battery_node, alternative, fix_elec_use=fix_ev_use
        )
        _temp_importer = self.ev_battery_charger(
            vehicle_type, source_node, _battery_node, alternative, enable_discharge=battery_discharge
        )
        if fix_ev_use:
            _temp_importer += self._ev_battery_state_ideal_net_change(vehicle_type, _battery_node, alternative)

        if hybrid:
            _availability = 1 - self.ev_fleet_behaviour(ev_key=vehicle_type, para_key='CONNECTED', add_time_index=True)
            _availability = {
                "type": "time_series", "data": _availability.to_dict(), "index": {"repeat": self._timeseries_repeat}
            }

            _temp_importer, _station_node = self.fuel_station(alternative_fuel, alternative)
            _temp_importer, _powertrain_icv = self.icv_engine(
                vehicle_type, _utility_node, _station_node, alternative, _availability
            )

            _emission_cost = self.find_parameter_value(
                category='assumption', entity=f'{alternative_fuel}_{emission_name}_emission_cost'
            )
            _temp_importer += self._icv_engine_emission(
                self._spinedb_importer, vehicle_type, utility, _station_node, emission_name, _emission_cost, alternative
            )

            _temp_importer = self.hybrid_powertrains(
                vehicle_type, _utility_node, _powertrain_ev, _powertrain_icv,
                alternative=alternative, fix_driving_distance_share=fix_driving_distance_share
            )
        return _temp_importer


if __name__ == '__main__':

    def build_transport_system_alternative(transport_module, use_base_alternative: bool = True):
        active_alternative = 'Base'
        if not use_base_alternative:
            active_alternative = transport_module.find_parameter_value(category='alternative_name', entity='fleet')
            transport_module.add_alternative(active_alternative)
            transport_module.import_to_spineopt()

        transport_module.set_importer(SpineDBImporter())
        transport_module.transport_utility('transport', active_alternative, 'BEV', 'PHEV', 'ICV_gasoline')
        transport_module.import_to_spineopt()

        transport_module.set_importer(SpineDBImporter())
        transport_module.build_ev_profile(
            vehicle_type='BEV', utility='transport', fuel='elec', source_node='75FI',
            alternative=active_alternative, fix_ev_use=True, battery_discharge=True
        )
        transport_module.import_to_spineopt()

        transport_module.set_importer(SpineDBImporter())
        transport_module.build_icv_profile(
            8 / 24, vehicle_type='ICV_gasoline', utility='transport', energy_flow='gasoline', emission_name='CO2',
            alternative=active_alternative
        )
        transport_module.import_to_spineopt()

        transport_module.set_importer(SpineDBImporter())
        transport_module.build_ev_profile(
            vehicle_type='PHEV', utility='transport', fuel='elec', source_node='75FI',
            alternative=active_alternative, hybrid=True, alternative_fuel='gasoline',
            emission_name='CO2', fix_driving_distance_share=True, fix_ev_use=True, battery_discharge=True
        )
        transport_module.import_to_spineopt()

        return None

    def build_discharge_alternative(transport_module, *ev_types, use_base_alternative: bool = True):
        active_alternative = 'Base'
        _temp_importer = SpineDBImporter()
        if not use_base_alternative:
            active_alternative = transport_module.find_parameter_value(
                category='alternative_name', entity='flexible_discharge_rate'
            )
            _temp_importer.alternatives.append(active_alternative)

        for vehicle_type in ev_types:
            discharge_share = transport_module.find_parameter_value(
                category='assumption', entity=f'Discharge_share_{vehicle_type}'
            )
            _temp_importer.relationship_parameter_values.append(
                (
                    "unit__from_node",
                    (f'transport_{vehicle_type}_charger_discharge', f'transport_{vehicle_type}_battery'),
                    'unit_conv_cap_to_flow', discharge_share, active_alternative
                )
            )

        transport_module.set_importer(_temp_importer)
        transport_module.import_to_spineopt()
        return None

    dir_spineopt_db = sys.argv[0]
    spineopt_db = open_spinedb(dir_spineopt_db, create_new_db=False)
    
    for dir_xlsx in sys.argv[1:]:
        xlsx = pd.ExcelFile(dir_xlsx)
        transport = SpineOptTransportModule(
            2021, xlsx, _spinedb_importer=SpineDBImporter(), _target_spineopt_db=spineopt_db, _timeseries_repeat=False
        )
        build_transport_system_alternative(transport, use_base_alternative=False)
        build_discharge_alternative(transport, 'BEV', 'PHEV', use_base_alternative=False)
