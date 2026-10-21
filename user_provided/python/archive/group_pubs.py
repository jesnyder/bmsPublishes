from bs4 import BeautifulSoup
import codecs
import datetime
from datetime import datetime
import json
import math
import numpy as np
import os
from random import random
import random
import re
import requests
import pandas as pd
import shutil
import statistics
from statistics import mean
import time


from admin import reset_df
from admin import retrieve_df
from admin import retrieve_json
from admin import retrieve_list
from admin import retrieve_path
from admin import retrieve_ref


def group_pubs():
    """
    analyze data
    """

    print("running meta_pubs")

    tasks = [1]

    if 1 in tasks: assign_groups()

    print("completed meta_pubs")


def find_pubs(pub):
    """
    return the list of assigned groups
    """

    assigned_groups = []

    groups = os.listdir(retrieve_path('groups'))
    for group in groups:

        group_name = group.split('.')[0]
        #print('group_name = ')
        #print(group_name)

        if check_group(pub, group) == False: continue
        assigned_groups.append(group_name)

    return(assigned_groups)


def assign_groups():
    """
    save json for each group
    """

    groups = os.listdir(retrieve_path('groups'))
    for group in groups:

        group_name = group.split('.')[0]
        print('group_name = ')
        print(group_name)

        groups_pubs = []

        src_fol = retrieve_path('crossref_json')
        for fil in os.listdir(src_fol):

            fil_name = fil.split('.')[0]

            fil_src = os.path.join(src_fol, fil)
            json_src = retrieve_json(fil_src)
            for pub in json_src['results']:

                if check_group(pub, group) == False: continue
                groups_pubs.append(pub)

                json_temp = {}
                json_temp['count'] = len(groups_pubs)
                json_temp['pubs'] = groups_pubs

                # save the dictionary as json
                fil_dst = os.path.join(retrieve_path('grouped'), fil_name  + '_' + group_name + '.json' )
                #print('fil_dst = ' + str(fil_dst))
                with open(fil_dst, "w") as fp:
                    json.dump(json_temp, fp, indent = 8)
                    fp.close()


def check_group(pub, group):
    """
    check if the group
    """

    keys = ['title', 'abstract', 'snippet']

    print('group = ' + str(group))

    if 'thesis' in str(group).lower(): keys = ['thesis']

    terms = list(retrieve_df(os.path.join(retrieve_path('groups'), group))['term'])

    for term in terms:

        term = term.replace('"', '')
        term = str(term).lower()

        for key in keys:

            if key not in pub.keys(): continue
            text = str(pub[key]).lower()

            if term in text: return(True)

    return(False)
