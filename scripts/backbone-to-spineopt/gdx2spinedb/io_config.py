#!/usr/bin/env python  
# -*- coding:utf-8 _*-

# Author: Huang, Jiangyi <jiangyi.huang@vtt.fi>
# Created: 11:39 31/08/2020

import argparse
import sys
import json
from gdx2py import GdxFile
from gdx2spinedb.spinedb import SpinedbIO  # pylint: disable=import-error

# %%
DESCRIPTION = "Backbone2Spine"


# return an object of system arguments input from terminal
def get_argument(input_format):
    """
    :param input_format: "SpineDB", "GDX"
    :return: a parsed argument
    """
    # Set up argument parser and argument
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    if input_format == "SpineDB":
        parser.add_argument("input_spinedb",
                            help="Input database url, format: sqlite:///database_directory\\database_name.sqlite")
    elif input_format == "GDX":
        parser.add_argument("input_gdx", help="Input gdx file")
    parser.add_argument("output_db",
                        help="Output database url, format: sqlite:///database_directory\\database_name.sqlite")
    parser.add_argument(
        "--import-json",
        help="Import data from a JSON file first",
        default=None,
        metavar="JSON_FILE",
        dest="json_path",
    )
    parser.add_argument(
        "--force-recreate",
        help="Force re-create database from scratch",
        action="store_true",
        dest="create",
    )
    args = parser.parse_args()
    return args


# open needed data files per parsed system arguments
def open_gdx(arg):
    # %%
    # Open input gdx file
    print("Importing from gdx data file. . .")
    try:
        gdx = GdxFile(arg)
    except FileNotFoundError:
        print(f"Error: Could not find file '{arg}'")
        sys.exit(1)
    except OSError as e:
        print(f"Error: {e}, '{arg}'")
        sys.exit(1)
    return gdx


def open_spinedb(arg, create_new_db=False):
    """
    :param arg:
    :param create_new_db: True if to recreate a new spineopt db, default False
    :return:
    """
    # %%
    # Open spine database
    print(f"Opening Spine DB at '{arg}'. . .")
    try:
        output_db = SpinedbIO(arg, create_new_db)
    except RuntimeError as e:
        print(e)
        sys.exit(1)
    return output_db


def import_json(arg, target_db):
    # %%
    # Load configuration from json file if there is one
    try:
        with open(arg) as fp:
            data = json.load(fp)
    except FileNotFoundError:
        print(f"Error: Could not find file '{arg}'")
        sys.exit(1)
    n_imported = target_db.import_data(data)
    print(f"Imported {n_imported} entities from JSON.")
    target_db.commit("Import JSON data")


def open_gdx2spine_io(args):
    gdx = open_gdx(args.input_gdx)
    output_db = open_spinedb(args.output_db, create_new_db=args.create)
    if args.json_path:
        import_json(args.json_path, output_db)
    return gdx, output_db


def open_spine2spineopt_io(args):
    input_spinedb = open_spinedb(args.input_spinedb)
    output_db = open_spinedb(args.output_db, create_new_db=args.create)
    if args.json_path:
        import_json(args.json_path, output_db)
    return input_spinedb, output_db


def open_config_spineopt_model_io(args):
    source_spineopt_db = open_spinedb(args.input_spinedb)
    if args.input_spinedb == args.output_db:
        output_db = source_spineopt_db
    else:
        output_db = open_spinedb(args.output_db, create_new_db=args.create)
    if args.json_path:
        import_json(args.json_path, output_db)
    return source_spineopt_db, output_db
