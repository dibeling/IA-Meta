import numpy as np
import pandas as pd
import json

import savReaderWriter as spss
from compute import compute_ipsatized
from constants import *

def read_sav(path):
    """Read .sav files, return pandas DataFrame"""
    raw_data = list(spss.SavReader(path, returnHeader = True))
    df = pd.DataFrame(raw_data)
    columns = list(df.loc[0])
    columns = [s.decode('utf-8') for s in columns]
    df.columns = columns
    df = df.iloc[1:].reset_index(drop=True) # sets column name to the first row

    return df


def load_var_name_dict(path, verbose=False):
    """Loads variable name dictionary csv"""
    var_name_dict = pd.read_csv(path)

    var_name_dict.index = var_name_dict['paper'].astype('str') +\
                                            '_' + var_name_dict['study']

    var_name_dict = var_name_dict.drop(['paper', 'study'], axis=1)

    if verbose:
        print("Loaded in variable name dictionary")

    return var_name_dict


def load_metadata(path):
    """Loads metadata from paper path"""
    path = path / "metadata.json"

    with open(path) as f:
        metadata = json.load(f)

    return metadata


def filter(df, study, metadata):
    """Filter df based on columns"""
    filter_cols = metadata['Filter'][study]
    for col, values in filter_cols.items():
        df = df.loc[df[col].isin(values)]

    return df


def recode(df, study, metadata):
    """Recodes columns of df"""
    recode_map = metadata['Recode'][study]
    for col, recode_col_map in recode_map.items():
        recode_col_map = {v:k for k, v in recode_col_map.items()}
        df[col] = df[col].replace(recode_col_map)

    return df


def replace(df, study, metadata):
    """Replace values of df"""
    replace_map = metadata['Replace'][study]
    replace_map = {v:(np.nan if k==NAN else k) for k, v in replace_map.items()}

    return df.replace(replace_map)


def rename_and_drop(df, study, var_name_dict, verbose=False):
    """Rename df using variable name dictionary"""
    # get rename map
    rename_map = dict(var_name_dict.loc[study, ~var_name_dict.loc[study].isnull()])
    rename_map = {v:k for k, v in rename_map.items()}

    if verbose:
        var_name_dict_cols = rename_map.keys()
        present = [col in list(df) for col in var_name_dict_cols]
        if all(present):
            print("    All columns found in variable name dictionary.")
        else:
            for col in var_name_dict_cols:
                if col not in list(df):
                    print("    WARNING: '{}' column in variable name dictionary missing.".format(col))

    # rename
    df = df.rename(columns=rename_map)

    # drop
    df = df[list(rename_map.values())]

    return df


def validate(df, study, metadata):
    """Validates reported subject number"""
    reported_N = metadata['Reported'][study]
    actual_N = df['ethn'].value_counts()

    allMatches = True
    for ethn, number in reported_N.items():
        if number != actual_N[ethn]:
            print("WARNING: reported {} {}, found {} {}".format(number, ethn, actual_N[ethn], ethn))
            allMatches = False

    if allMatches:
        print("    All subject numbers match.")

    return


def load_and_merge(meta_df, paper_paths, verbose=False):
    """Loads all datasets from paper paths and merge with meta_df"""

    var_name_dict = load_var_name_dict(VAR_NAME_DICT_DIR, verbose=verbose)

    for paper_path in paper_paths:
        metadata = load_metadata(paper_path)
        paper = metadata['Paper']
        if verbose:
            print("{}".format(paper))
            print("===============================")
        for study_dir in metadata['Usable']:

            df_path = paper_path / study_dir
            study = study_dir.split('.')[0]
            name = '_'.join([paper, study])

            if verbose:
                print("Processing {}...".format(study))

            # read each study
            df = read_sav(df_path)

            # basic preprocessing
            df = filter(df, study, metadata)
            df = recode(df, study, metadata)
            df = rename_and_drop(df, name, var_name_dict, verbose=verbose)
            df = replace(df, study, metadata)

            df = df.reset_index(drop=True)

            # validate final subject number
            validate(df, study, metadata)

            # compute
            df = compute_ipsatized(df, verbose=verbose)

            meta_df = meta_df.append(df, sort=False)

    return meta_df
