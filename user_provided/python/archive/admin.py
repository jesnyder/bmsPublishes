import csv
import codecs
import datetime
import json
import math
import matplotlib
from matplotlib import cm
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
import numpy as np
import os
from random import random
import random
import pandas as pd
import plotly
from plotly.tools import FigureFactory as ff
import shutil
import time



def display_df(df_name, df):
    """
    formatted display of df
    """

    print(df_name + ' = ')
    print(df)

    print(df_name + '.columns = ')
    print(df.columns)


def list_unique(df, colname):
    """
    return a list of unique
    """

    types = []
    for item in list(df[colname]):
        if item not in types:
            types.append(item)
    return(types)


def lookup_type(company):
    """
    look up the type of a given company
    """
    df_agg = retrieve_df('df_agg')
    df = df_agg[df_agg.company == company]
    types = list(df['types'])
    type = types[0]
    return(type)


def make_color():
    """
    return a list of colors formatted as rgb
    according to the color type and scaled
    """

    norm = 255*random.random()
    print('norm = ' + str(norm))

    #norm = 255*(value_max - value)/(value_max - value_min)

    mods = [0.5, 0.5, 0.5]
    r = int(255 - 255*random.random()*mods[0])
    g = int(255 - 255*random.random()*mods[1])
    b = int(255 - 255*random.random()*mods[2])

    color_str = str('rgb( ' + str(r) + ' , ' +  str(g) + ' , ' + str(b) + ' )')
    return(color_str)


def print_progress(item, item_list, counter):
    """
    print the progress
    """

    i = item_list.index(item)
    len_list = len(item_list)
    progress = i/len_list*100
    progress = round(progress,2)

    if counter < progress:
        print(str(progress) + ' % complete.')
        counter = counter + 5

    return(counter)


def reset_df(df):
    """
    reset the index column
    """

    df = df.reset_index()

    for col in df.columns:

        if 'index' in col:
            del df[col]

        if 'Unnamed:' in col:
            del df[col]

    return(df)


def retrieve_calculated(name_ref):
    """
    retrieve value from saved file
    """

    df = retrieve_df('calculated_refs')

    df_ref = df[df.name == name_ref]
    metrics = list(df_ref['value'])
    calculated_value = metrics[0]

    try:
        calculated_value = round(calculated_value, 3)
    except:
        print('tried.')

    return(calculated_value)


def retrieve_df(name):
    """
    return a df
    from a pathname
    """


    if '.xlsx' in name or '.xls' in name:

        #print('name = ' + str(name))
        df = pd.read_excel(name)
        #print('excel file df = ')
        #print(df)
        return(df)

    encodings = ['utf-16', "utf-8-sig", "utf-8", "cp1252", "latin1", 'utf-8-sig', ]

    # find the path
    if '.' in str(name): df_path = name
    else: df_path = retrieve_path(name)

    #print('df_path = ')
    #print(df_path)

    try:
        df = pd.read_csv(df_path)

    except:

        try:
            for encoding in encodings:
                df = pd.read_csv(retrieve_path(name), encoding=encoding)
                continue
        except:

            f = open(df_path,"r")
            lines = f.readlines()
            f.close()

            df = pd.DataFrame()
            df['list'] = lines


    for col in df.columns:
        if 'Unnamed:' in col:
            del df[col]

    return(df)


def retrieve_json(path):
    """
    return json
    provide path name
    """


    if '.json' in path:
        f = open(path)
        file_json = json.load(f)
        f.close()

    else:
        #print('path = ' + str(path))
        f = open(retrieve_path(path))
        #print('f = ' + str(f))
        file_json = json.load(f)
        f.close()

    return(file_json)


def retrieve_list(filename):
    """
    Return a list
    Saved in a file
    Referred to by the provided filename
    """

    f_path = retrieve_path(filename)
    with open(f_path) as f:
        alist = [line.rstrip() for line in f]

    """
    f_path = retrieve_path(filename)
    f = open(f_path, 'r')
    lines = f.readlines()
    f.close()
    """

    alist = alist[1:]
    return(alist)


def retrieve_path(name):
    """
    return the path
    given a path name
    """

    src_file = os.path.join('user_provided', 'admin', 'paths' + '.csv')
    df = pd.read_csv(src_file)

    try:
        df = df[df['name'] == name]
    except:
        return('None found.')

    path_retrieved = list(df['path'])[0]
    path_split = path_retrieved.split(' ')

    # build the path
    path_list = []
    for sub in path_split:
        path_list.append(sub)
        path = os.path.join(*path_list)

        # do not check for specific files
        if '.' in sub: continue

        # create the folder, if it doesnt exist
        if os.path.exists(path) == False: os.mkdir(path)

    #print('path = ' + str(path))

    return(path)


def retrieve_ref(name):
    """
    return saved variable
    from a variable name
    """

    # retrieve the list of variables
    df = pd.read_csv(retrieve_path('ref_variable'))

    try:
        df = df[df['name'] == name]
    except:
        return('None found.')

    term_retrieved = list(df['term'])[0]

    # if the term is a list, split
    if '$$$' in term_retrieved:
        term = term_retrieved.split('$$$')

        # try to convert list to floats
        try:
            for i in range(len(term)):
                term[i] = float(term[i])
        except:
            term = term

    else:

        term = term_retrieved

        # try to convert list to floats
        try:
            if '.' in term:
                term = float(term)
            else:
                term = int(term)
        except:
            term = term

    return(term)


def rgb_to_hexcolorcode(rgb):
    """
    convert an rgb list to a
    hex color code as a string
    """

    rgb_orig = rgb
    for i in range(len(rgb)):

        rgb[i] = rgb[i]*255
        rgb[i] = int(rgb[i])

    rgb_par = (rgb[0], rgb[1], rgb[2])

    hex_str = '#%02x%02x%02x' % rgb_par
    hex_str = str(hex_str).upper()

    return(hex_str)


def save_df(df, fil_dst, col_sort):
    """
    reset the dataframe and save
    """

    try:
        df = df.sort_values(by = col_sort)
    except:
        col_sort = df.columns[0]
        df = df.sort_values(by = col_sort)

    df = reset_df(df)

    if '.csv' in fil_dst:
        df.to_csv(fil_dst)

    else:
        df.to_csv(retrieve_path(fil_dst))



def save_json(file_json, path):
    """
    save json to path
    """


    if '.json' in path:
        with open(path, "w") as f:
            json.dump(file_json, f, indent = 7)
        f.close()

    else:
        dst_json = (retrieve_path(path))
        with open(dst_json, "w") as f:
            json.dump(file_json, f, indent = 7)
        f.close()


def save_value(name, value):
    """
    save a value with a timestamp
    """

    df_temp = pd.DataFrame()
    df_temp['name'] = [name]
    df_temp['value'] = [value]
    df_temp['saved'] = [datetime.datetime.today()]

    try:
        df = retrieve_df('saved_values')

    except:
        df = pd.DataFrame()
        df['name'] = []
        df['value'] = []
        df['saved'] = []

    df = df[df['name'] != name]
    df = df.append(df_temp)
    df = df.sort_values(by = 'name', ascending='true')
    df = reset_df(df)
    df.to_csv(retrieve_path('saved_values'))


def send_to_df(list, name, file_dst):
    """
    save a list as a sorted df
    """
    df = pd.DataFrame()
    df[name] = list
    #df = df.sort_values(by=name, ascending=True)
    #df = reset_df(df)
    df.to_csv(retrieve_path(file_dst))


def str_list(str_src):
    """
    Return a string from a list
    """

    temp_var = '-0987654321poiuytrewqasdfghjkl`okijhjhgfds'
    str_dst = temp_var

    for element in str_src:
        if str_dst == temp_var:
            str_dst = str(element)
        else:
            str_dst = str_dst + ' , ' + str(element)

    return(str_dst)


def unique_dfcol(ref_list):
    """
    return a list of unique values
    from a dataframe a column name
    """

    if len(ref_list) == 0:
        return([])

    types = []
    for item in list(ref_list):
        if item not in types:
            types.append(item)

    assert len(types) > 0
    return(types)


def write_calculated(name, value):
    """
    save a metric to be referenced later
    """

    # create a temp df
    df_temp = pd.DataFrame()
    df_temp['name'] = [name]
    df_temp['value'] = [value]

    try:
        df = retrieve_df('calculated_refs')
    except:
        df = pd.DataFrame()
        df['name'] = ['test']
        df['value'] = ['test']
        df.to_csv(retrieve_path('calculated_refs'))
        df = retrieve_df('calculated_refs')

    if name in list(df['name']):
        df = df[df.name != name]

    df = df.append(df_temp)
    #df = df.sort_values(by=['name'], ascending=True)
    #df = reset_df(df)
    display_df('df', df)
    df.to_csv(retrieve_path('calculated_refs'))
