import sys, os
import pandas as pd
import io_config

# Always switch the working directory to the directory of this script
os.chdir(sys.path[0])
gdx, output_db = io_config.open_gdx2spine_io(io_config.get_argument(input_format="GDX"))

# %%
objects = list()
object_groups = list()
object_parameter_values = list()
relationships = list()
relationship_parameter_values = list()

print(len(gdx))
print(list(gdx.keys()))
print(gdx[1].dimension)
print(gdx[1].domain)
print(gdx[1].elements)


# %%
# Write nodes with demand (TimeSeries data)
def generate_time_index(year, time_steps=8760, leap=False):
    start = pd.Timestamp(year=year, month=1, day=1, hour=0)
    end = pd.Timestamp(year=year, month=12, day=31, hour=23)
    full_year_range = pd.date_range(start, end, freq='H')
    if leap:
        return full_year_range[:time_steps]
    else:
        full_year_range = full_year_range[~((full_year_range.month == 2) & (full_year_range.day == 29))]
        return full_year_range[:time_steps]


ts_influx = gdx["ts_influx"].to_pandas()
ts_influx.index.set_names(['commodity', 'node', 'f', 'time_step'], inplace=True)
time_index = generate_time_index(2020, len(ts_influx.index.get_level_values("time_step").drop_duplicates()))
time_index = [str(x) for x in time_index]

df = (
    ts_influx.xs("f00", level="f").unstack(level="time_step")
).reset_index()
df.columns.name = None

for i, row in df.iterrows():
    demand = [-x for x in list(row.iloc[2:])]
    demand = dict(zip(time_index, demand))
    if ("commodity", row["commodity"]) not in objects:
        objects.append(("commodity", row["commodity"]))
    if ("node", row["node"]) not in objects:
        objects.append(("node", row["node"]))
    object_parameter_values += [
        ("node", row["node"], "demand", {"type": "time_series", "data": demand, "index": {"repeat": True}}),
        ("node", row["node"], "has_state", True),
        ("node", row["node"], "node_state_cap", 432)
    ]
    relationships.append(("node__commodity", (row["node"], row["commodity"])))

# %%
# Unit inputs and outputs
p_gnu_io = gdx["p_gnu_io"].to_pandas()
p_gnu_io.index.set_names(['grid', 'node', 'unit', 'input_output', 'param_gnu'], inplace=True)
# TODO: No label for the level of MultiIndex is read from the *.gdx datafile
# The below docstring using position number is an alternative
# df = (
#     p_gnu_io.xs("output", level=3).xs("capacity", level=3)
# ).reset_index(name="value")

# Write parameter 'unit_capacity', 'unit_conv_cap_to_flow' and 'unit_operating_points'(array)
df = (
    p_gnu_io.xs("output", level="input_output").xs("capacity", level="param_gnu")
).reset_index(name="value")

for i, row in df.iterrows():
    unit_constraint_object = f'flow_eff-{row["unit"]}'
    objects.append(
        ("unit_constraint", unit_constraint_object)
    )
    relationships += [
        ("unit__to_node", (row["unit"], row["node"])),
        ("unit__to_node__unit_constraint", (row["unit"], row["node"], unit_constraint_object))
    ]
    relationship_parameter_values += [
        ("unit__to_node", (row["unit"], row["node"]), "unit_capacity", row["value"]),
        ("unit__to_node", (row["unit"], row["node"]), "unit_conv_cap_to_flow", row["value"]),
        ("unit__to_node", (row["unit"], row["node"]),
         "operating_points", {"type": "array", "value_type": "float", "data": [0.4, 0.6, 0.8, 1.0]}),
        ("unit__to_node__unit_constraint", (row["unit"], row["node"], unit_constraint_object),
         "unit_flow_coefficient", {"type": "array", "value_type": "float", "data": [-1, -1.1, -1.3, -1.8]})
    ]

# Add node group (a node object with existing nodes as members) for distHeat
node_group = "ng_distHeat"
if ("node", node_group) not in objects:
    objects.append(("node", node_group))
for i, row in df.loc[df['grid'] == 'distHeat'].iterrows():
    object_groups.append(
        ('node', node_group, row['node'])
    )

# %%
# Write transfer links
p_gnn = gdx["p_gnn"].to_pandas()
p_gnn.index.names = ["grid", "from_node", "to_node", "param_gnn"]

df = p_gnn.unstack().reset_index()

for i, row in df.iterrows():
    connection_name = "--".join(sorted([row["from_node"], row["to_node"]]))
    objects.append(("connection", connection_name))
    for node_type in ["from_node", "to_node"]:
        relationship_class = f"connection__{node_type}"
        obj_list = [connection_name, row[node_type]]
        relationships.append((relationship_class, obj_list))
        relationship_parameter_values.append(
            (relationship_class, obj_list, "connection_capacity", row["transferCap"])
        )
    relationship_class = "connection__node__node"
    obj_list = [connection_name, row["from_node"], row["to_node"]]
    relationships.append((relationship_class, obj_list))
    relationship_parameter_values.append(
        (
            relationship_class,
            obj_list,
            "fix_ratio_out_in_connection_flow",
            1 - row["transferLoss"],
        )
    )
# %%
gdx.close()

# %%
n_objects = output_db.import_objects(objects)
n_object_values = output_db.import_object_parameter_values(object_parameter_values)
n_member_objects = output_db.import_object_groups(object_groups)
n_relationships = output_db.import_relationships(relationships)
n_parameter_values = output_db.import_relationship_parameter_values(relationship_parameter_values)

# Commit changes
output_db.commit("Converted Backbone model")

print(f" {n_objects} objects")
print(f" {n_object_values} object_values")
print(f" {n_member_objects} objects added as the member of some groups")
print(f" {n_relationships} relationships")
print(f" {n_parameter_values} parameter_values")
print("Done.")
