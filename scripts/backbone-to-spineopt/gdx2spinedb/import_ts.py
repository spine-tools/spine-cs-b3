#!/usr/bin/env python
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 16:30 04/09/2020

import sys
import os
import pandas as pd
from gdx2py import gams
from gdx2spinedb import io_config


def generate_time_index(year, relative_pos=(0, 0), full_year=False, leap=False, frequency='H'):
    """
    :param year:
    :param relative_pos: a tuple (int, int) of start time (hour) and end time (hour, inclusive)
    :param full_year:
    :param leap: True if a leap year is considered, False otherwise
    :param frequency:
    :return: a pandas DatetimeIndex
    """
    if full_year:
        start = pd.Timestamp(year=year, month=1, day=1, hour=0)
        end = pd.Timestamp(year=year, month=12, day=31, hour=23)
        full_year_range = pd.date_range(start, end, freq=frequency)
        if all([year % 4 == 0, leap]):
            time_steps = 8784
            return full_year_range[:time_steps]
        else:
            # skip the leap day
            time_steps = 8760
            full_year_range = full_year_range[~((full_year_range.month == 2) & (full_year_range.day == 29))]
            return full_year_range[:time_steps]
    start = pd.Timestamp(year=year, month=1, day=1, hour=0) + pd.to_timedelta(relative_pos[0], unit=frequency)
    # Skip the leap day
    if not leap and start >= pd.Timestamp(year=year, month=2, day=29):
        start = start + pd.Timedelta(1, unit='d')
    end = start + pd.to_timedelta(relative_pos[1], unit=frequency)
    time_range = pd.date_range(start, end, freq=frequency)
    return time_range


class SpineDBImporter:
    def __init__(self):
        self.objects = list()
        self.object_parameter_values = list()
        self.object_groups = list()
        self.relationships = list()
        self.relationship_parameter_values = list()
        self.alternatives = list()
        self.scenarios = list()
        self.scenario_alternatives = list()
        self.tool_feature_methods = list()

    def __add__(self, other):
        temp = SpineDBImporter()
        for k, v in self.__dict__.items():
            v += other.__getattribute__(k)
            temp.__setattr__(k, v)
        return temp

    def import_data(self, _output_db):
        """
        :param _output_db: a Spine database instance of class gdx2spinedb.spinedb.SpinedbIO
        :return: None
        """
        # alternatives must be imported as prerequisite to enable importing parameter values with alternatives
        _n_alternatives = _output_db.import_alternatives(self.alternatives)
        _n_objects = _output_db.import_objects(self.objects)
        _n_object_values = _output_db.import_object_parameter_values(self.object_parameter_values)
        _n_member_objects = _output_db.import_object_groups(self.object_groups)
        _n_relationships = _output_db.import_relationships(self.relationships)
        _n_parameter_values = _output_db.import_relationship_parameter_values(self.relationship_parameter_values)
        _n_scenarios = _output_db.import_scenarios(self.scenarios)
        _n_scenario_alternatives = _output_db.import_scenario_alternatives(self.scenario_alternatives)
        _n_tool_feature_methods = _output_db.import_tool_feature_methods(self.tool_feature_methods)

        # Commit changes
        _output_db.commit("Converted Backbone model")

        print(f" {_n_alternatives} alternatives in addition to the 'Base' are added")
        print(f" {_n_objects} objects")
        print(f" {_n_object_values} object_parameter_values")
        print(f" {_n_member_objects} objects added as the member of some groups")
        print(f" {_n_relationships} relationships")
        print(f" {_n_parameter_values} relationship_parameter_values")
        print(f" {_n_scenarios} scenarios")
        print(f" {_n_scenario_alternatives} combinations of scenario_alternatives")
        print(f" {_n_tool_feature_methods} tool_feature_methods defined")
        print("Done.")
        return None


# TODO: include functions below if necessary
class GdxHandler:
    def __init__(self, _gdx_file):
        self.gdx_file = _gdx_file


def domain2spineopt(_key):
    """
    :param _key: string
    :return: a dictionary mapping from gdx domain to spineopt object_class
    """
    __domain_mappings = dict()
    if _key == "ts_influx":
        __domain_mappings = dict(zip(["grid", "node", "f"], ["commodity", "node", "alternative"]))
    elif _key == "ts_cf":
        __domain_mappings = dict(zip(["flow", "node", "f"], ["commodity", "node", "alternative"]))
    # TODO: domain mapping for reserve below
    elif _key == "reserve":
        __domain_mappings = dict(zip(["restype", "up_down", "node", "f"], ["??", "??", "node", "alternative"]))
    else:
        __domain_mappings = None
    return __domain_mappings


def valid_key(_gdx_file, _key):
    try:
        __test = _gdx_file[_key]
    except KeyError as __error:
        print(f"KeyError: the key {__error} does not exist.")
        __symbols = list(_gdx_file.keys())
        print(f"keys contained in this database: {__symbols}")
        sys.exit(1)
    return None


def get_gdx_entry(_gdx_file, _key):
    """
    :param _gdx_file: a *.gdx file instance of class gdx2py.gdxfile.GdxFile
    :param _key: a string of symbol name
    :return: a list of elements if the _key refers to a gdx Set
             a dataframe with parameter values if the _key refers to a gdx Parameter
    """
    valid_key(_gdx_file, _key)
    if isinstance(_gdx_file[_key], gams.GAMSSet):  # a Set contains only elements
        __element_list = _gdx_file[_key].elements
        return __element_list
    elif isinstance(_gdx_file[_key], gams.GAMSParameter):
        return _gdx_file[_key].to_pandas()


def prepare_gdx_ts2spineopt(_gdx_file, _key, __domain_in_spine=None):
    """
    :param _gdx_file: a *.gdx file instance of class gdx2py.gdxfile.GdxFile
    :param _key: name of a symbol in "ts_cf", "ts_influx", "ts_reserveDemand"
    :param __domain_in_spine:
    :return: a dataframe organised under spine opt object_class, dimension (int)
    """
    __df = get_gdx_entry(_gdx_file, _key)
    __domain_mappings = domain2spineopt(_key)
    __dimension = _gdx_file[_key].dimension
    if __domain_mappings is None:
        print("The domain for SpineOpt needs specifying in key argument")
        __df = __df.unstack(level=-1)
        # the last dimension should be "t"
        __df.index.set_names(__domain_in_spine, inplace=True)
        __df.reset_index(inplace=True)
    else:
        if _gdx_file[_key].domain is not None:
            __domain_in_spine = [
                x for x in map(
                    lambda x: __domain_mappings[x] if x in __domain_mappings.keys() else x, _gdx_file[_key].domain
                )
            ]
            __df.index.set_names(__domain_in_spine, inplace=True)
            __df = __df.unstack(level=__domain_in_spine[-1]).reset_index()
            # the last item of domain_spine, i.e. domain_spine[-1], should be "t"
            __domain_in_spine.remove(__domain_in_spine[-1])
        else:
            __df = __df.unstack(level=-1)
            # the last dimension should be "t"
            __domain_in_spine = [x for x in list(__domain_mappings.values())]
            __df.index.set_names(__domain_in_spine, inplace=True)
            __df.reset_index(inplace=True)
    __dimension -= 1
    __df.columns.name = None

    return __df, __dimension


# TODO: finish variable description
def gdx_ts_influx2spineopt(_gdx_file, _key, commodity, node, _time_index,
                           _domain_in_spine=None, _has_base_alternative=True, _minima=None
                           ):
    """

    :param _gdx_file:
    :param _key:
    :param commodity:
    :param node:
    :param _time_index:
    :param _domain_in_spine:
    :param _has_base_alternative:
    :param _minima:
    :return:
    """
    __df, __dimension = prepare_gdx_ts2spineopt(_gdx_file, _key, __domain_in_spine=_domain_in_spine)
    _ts_influx_importer = SpineDBImporter()
    if "f00" not in __df["alternative"]:
        _has_base_alternative = False

    for i, row in __df.iterrows():
        if any(
                [commodity not in row["commodity"], node not in row["node"]]
        ):
            continue
        if ("commodity", row["commodity"]) not in _ts_influx_importer.objects:
            _ts_influx_importer.objects += [
                ("commodity", row["commodity"])
            ]
        if (row["alternative"]) not in _ts_influx_importer.alternatives:
            _ts_influx_importer.alternatives.append(row["alternative"])
        __position = __dimension
        while pd.isnull(row.iloc[__position]):
            __position += 1
        # Assume the length of all TimeSeries records are the same
        # Skip NaN value at the beginning
        _ts_influx = pd.Series([-x for x in list(row.iloc[__position:(__position + len(_time_index) + 1)])])
        # control accuracy
        if _minima is not None:
            _ts_influx[abs(_ts_influx) <= _minima] = 0.0
        # fill NaN value (can be obtained by np.nan)
        _ts_influx.fillna(0.0, inplace=True)
        _ts_influx = dict(zip(_time_index, _ts_influx.to_list()))
        _ts_influx_importer.objects += [
            (obj_class, row[obj_class]) for obj_class in ["commodity", "node"] if
            (obj_class, row[obj_class]) not in _ts_influx_importer.objects
        ]
        if any([
            _has_base_alternative and "f00" == row["alternative"],
            all([not _has_base_alternative, "f01" == row["alternative"]])
        ]):
            #  a copy of f00 is set to be the base alternative, f01 otherwise
            _ts_influx_importer.object_parameter_values += [
                ("node", row["node"], "demand",
                 {"type": "time_series", "data": _ts_influx, "index": {"repeat": True}},),
            ]
        _ts_influx_importer.object_parameter_values += [
            ("node", row["node"], "demand",
             {"type": "time_series", "data": _ts_influx, "index": {"repeat": True}}, row["alternative"]),
        ]
        _ts_influx_importer.relationships.append(("node__commodity", (row["node"], row["commodity"])))
    return _ts_influx_importer


# TODO: finish this block
def gdx_ts_cf2spineopt(_gdx_file, _key, commodity, node, _time_index, total_capacity,
                       _domain_in_spine=None, _has_base_alternative=True, _minima=None, is_source_node=True
                       ):
    """

    :param _gdx_file:
    :param _key:
    :param commodity:
    :param node:
    :param _time_index:
    :param total_capacity: unit_capacity * number_of_units
    :param _domain_in_spine:
    :param _has_base_alternative:
    :param _minima:
    :param is_source_node: True if the ts_cf data is to be modelled as a source node,
           where total_capacity should be provided,
           otherwise the ts_cf is to be modelled as parameter unit_conv_cap_to_flow of relationship unit__to_node
    :return:
    """
    __df, __dimension = prepare_gdx_ts2spineopt(_gdx_file, _key, __domain_in_spine=_domain_in_spine)
    _ts_cf_importer = SpineDBImporter()
    if "f00" not in __df["alternative"]:
        _has_base_alternative = False

    for i, row in __df.iterrows():
        if any(
                [commodity not in row["commodity"], node not in row["node"]]
        ):
            continue
        if ("commodity", row["commodity"]) not in _ts_cf_importer.objects:
            _ts_cf_importer.objects += [
                ("commodity", row["commodity"])
            ]
        if (row["alternative"]) not in _ts_cf_importer.alternatives:
            _ts_cf_importer.alternatives.append(row["alternative"])
        __position = __dimension
        while pd.isnull(row.iloc[__position]):
            __position += 1
        # Assume the length of all TimeSeries records are the same
        # Skip NaN value at the beginning
        _ts_cf = pd.Series([-x for x in list(row.iloc[__position:(__position + len(_time_index) + 1)])])
        # control accuracy
        if _minima is not None:
            _ts_cf[abs(_ts_cf) <= _minima] = 0.0
        # fill NaN value (can be obtained by np.nan)
        _ts_cf.fillna(0.0, inplace=True)
        # available inflow from source node
        _ts_influx = _ts_cf * total_capacity
        _ts_influx = dict(zip(_time_index, _ts_influx.to_list()))
        _ts_cf_importer.objects += [
            (obj_class, row[obj_class]) for obj_class in ["commodity", "node"] if
            (obj_class, row[obj_class]) not in _ts_cf_importer.objects
        ]
        if any([
            _has_base_alternative and "f00" == row["alternative"],
            all([not _has_base_alternative, "f01" == row["alternative"]])
        ]):
            #  a copy of f00 is set to be the base alternative, f01 otherwise
            _ts_cf_importer.object_parameter_values += [
                ("node", row["node"], "demand",
                 {"type": "time_series", "data": _ts_influx, "index": {"repeat": True}},),
            ]
        _ts_cf_importer.object_parameter_values += [
            ("node", row["node"], "demand",
             {"type": "time_series", "data": _ts_influx, "index": {"repeat": True}}, row["alternative"]),
        ]
        _ts_cf_importer.relationships.append(("node__commodity", (row["node"], row["commodity"])))
    return _ts_cf_importer


if __name__ == '__main__':

    def mass_import_influx(start_hour, temporal_step, start_hour_end,
                           key, commodity, node,
                           recreate_output=True, import_json=True,
                           work_dir="C:/HJY_projects/spine",
                           gdx_file_dir="/Case_study_B3/datasets/raw_data/VabisysData/ts_influx/",
                           output_spinesb_dir=
                           "sqlite:///backbone-to-spineopt\\Temp\\datasets\\backbone2spine_test_py.sqlite",
                           json_dir="/SpineOpt/data/spineopt_template.json"
                           ):
        os.chdir(work_dir)
        gdx_file_dir = work_dir + gdx_file_dir
        json_dir = work_dir + json_dir
        influx_importer = SpineDBImporter()
        ts_values = list()
        overall_time_index = list()
        while start_hour < start_hour_end:
            dir_bb_gdx = gdx_file_dir + f"t{start_hour:06d}.gdx"
            bb_gdx = io_config.open_gdx(dir_bb_gdx)
            _output_db = io_config.open_spinedb(output_spinesb_dir, is_output=recreate_output)
            if import_json:
                io_config.import_json(json_dir, _output_db)
            _time_index = generate_time_index(2020, relative_pos=(start_hour, temporal_step - 1))
            _time_index = [str(x) for x in _time_index]
            print(f"Converting value of {key} under {commodity} as the demand of node {node} "
                  f"from the {start_hour}th to {start_hour + temporal_step - 1}th hour")
            _temp_importer = gdx_ts_influx2spineopt(bb_gdx, key, commodity, node, _time_index)
            for attr in dir(influx_importer):
                if attr[:2] != "__":
                    setattr(influx_importer, attr, getattr(_temp_importer, attr))
            # list of values ordered with respect to alternatives
            ts_value_segment = [list(x[3]["data"].values()) for x in _temp_importer.object_parameter_values]
            _time_index = [list(x[3]["data"].keys()) for x in _temp_importer.object_parameter_values]
            if all([ts_values == [], overall_time_index == []]):
                ts_values += ts_value_segment
                overall_time_index += _time_index
            elif all([ts_values != [], overall_time_index != []]):
                ts_values = [(alternative + ts_value_segment[i]) for i, alternative in enumerate(ts_values)]
                overall_time_index = [
                    (alternative + _time_index[i]) for i, alternative in enumerate(overall_time_index)
                ]
            else:
                print("The time_index is inconsistent with the ts_values")
            bb_gdx.close()
            recreate_output = False
            import_json = False
            start_hour += temporal_step
        __data = [dict(zip(overall_time_index[i], alternative)) for i, alternative in enumerate(ts_values)]
        for i, alternative in enumerate(influx_importer.object_parameter_values):
            alternative[3]["data"] = __data[i]
        influx_importer.import_data(_output_db)
        return influx_importer


    importer = mass_import_influx(
        start_hour=0, temporal_step=24, start_hour_end=8760, key="ts_influx", commodity="elec", node="75FI"
    )

# # The following block can be used for testing
# start_hour = 8760
# temporal_range = 24
# recreate_output = True
# import_json = True
# base_dir = "C:/HJY_projects/spine/"
# folder_temp = base_dir + "backbone-to-spineopt/Temp/datasets/"
# folder_vabi = base_dir + "Case_study_B3/datasets/raw_data/VabisysData/ts_influx/"
# # the directory below is dedicated for checking NaN values
# # dir_bb_gdx = base_dir + "Case_study_B3/datasets/raw_data/VabisysData/inputData.gdx"
# dir_bb_gdx = folder_temp + f"t{start_hour:06d}.gdx"
# # different domain mappings: ts_cf, ts_influx, ts_reserveDemand
# key = "ts_influx"
# # dir_bb_gdx = base_dir + "Case_study_B3/datasets/raw_data/VabisysData/inputData.gdx"
# dir_output_db = "sqlite:///backbone-to-spineopt\\Temp\\datasets\\backbone2spine_test_py.sqlite"
# dir_json = base_dir + "SpineOpt/data/spineopt_template.json"
#
# try:
#     if sys.argv[0] == __file__:
#         bb_gdx, output_db = io_config.open_gdx2spine_io(io_config.get_argument(input_format="GDX"))
# except NameError:
#     bb_gdx = io_config.open_gdx(dir_bb_gdx)
#     output_db = io_config.open_spinedb(dir_output_db, is_output=recreate_output)
#     if import_json:
#         io_config.import_json(dir_json, output_db)
#
# # %%
# alternatives = list()
# objects = list()
# object_parameter_values = list()
# object_groups = list()
# relationships = list()
# relationship_parameter_values = list()
#
# time_index = generate_time_index(2020, relative_pos=(start_hour, start_hour + temporal_range - 1))
# time_index = [str(x) for x in time_index]
#
# # test approach 1
# importer = gdx_ts_influx2spineopt(bb_gdx, key, "elec", "75FI", time_index)
# importer.import_data(output_db)
# bb_gdx.close()
#
# # test approach 2
# df, dimension = prepare_gdx_ts2spineopt(bb_gdx, key)
# has_base_alternative = True
# if "f00" not in df["alternative"]:
#     has_base_alternative = False
#
# for i, row in df.iterrows():
#     if any(
#             ["elec" not in row["commodity"], "75FI" not in row["node"]]
#     ):
#         continue
#     if ("commodity", row["commodity"]) not in objects:
#         objects += [
#             ("commodity", row["commodity"])
#         ]
#     if (row["alternative"]) not in alternatives:
#         alternatives.append(row["alternative"])
#     position = dimension
#     while pd.isnull(row.iloc[position]):
#         position += 1
#     # Assume the length of all TimeSeries records are the same
#     # Skip na value
#     demand = pd.Series([-x for x in list(row.iloc[position:(position + len(time_index) + 1)])])
#     # control accuracy
#     c = None
#     if c is not None:
#         demand[abs(demand) <= c] = 0.0
#     # fill NaN value (can be obtained by np.nan)
#     demand.fillna(0.0, inplace=True)
#     demand = dict(zip(time_index, demand.to_list()))
#     objects += [
#         (obj_class, row[obj_class]) for obj_class in ["commodity", "node"] if
#         (obj_class, row[obj_class]) not in objects
#     ]
#     if any([
#         has_base_alternative and "f00" == row["alternative"],
#         all([not has_base_alternative, "f01" == row["alternative"]])
#     ]):
#         #  a copy of f00 is set to be the base alternative, f01 otherwise
#         object_parameter_values += [
#             ("node", row["node"], "demand",
#              {"type": "time_series", "data": demand, "index": {"repeat": True}},),
#         ]
#     object_parameter_values += [
#         ("node", row["node"], "demand",
#          {"type": "time_series", "data": demand, "index": {"repeat": True}}, row["alternative"]),
#     ]
#     relationships.append(("node__commodity", (row["node"], row["commodity"])))
#
# # %%
# bb_gdx.close()
#
# # %%
# n_alternatives = output_db.import_alternatives(alternatives)
# n_objects = output_db.import_objects(objects)
# n_object_values = output_db.import_object_parameter_values(object_parameter_values)
# n_member_objects = output_db.import_object_groups(object_groups)
# n_relationships = output_db.import_relationships(relationships)
# n_parameter_values = output_db.import_relationship_parameter_values(relationship_parameter_values)
#
# # Commit changes
# output_db.commit("Converted Backbone model")
#
# print(f" {n_objects} objects")
# print(f" {n_object_values} object_values")
# print(f" {n_member_objects} objects added as the member of some groups")
# print(f" {n_relationships} relationships")
# print(f" {n_parameter_values} parameter_values")
# print(f" {n_alternatives} alternatives net base")
# print("Done.")
