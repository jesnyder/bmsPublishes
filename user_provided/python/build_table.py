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
import unidecode


from admin import reset_df
from admin import retrieve_df
from admin import retrieve_json
from admin import retrieve_list
from admin import retrieve_path
from admin import retrieve_ref

from meta_pubs import list_affs


def build_table():
    """
    write js to build table of pub data
    """

    print("running build_table")

    tasks = [1]
    if 1 in tasks: write_js()

    print("completed build_table")



def write_js():
    """
    write a js variable describing the table
    """

    for file in os.listdir(retrieve_path('crossref_json')):

        term = file.split('.')[0]
        table_name = term + '_table'

        table_pubs = []

        fil_src = os.path.join(retrieve_path('crossref_json'), file)
        json_src = retrieve_json(fil_src)

        for pub in json_src['results']:

            #index = list(json_src['results']).index(pub)
            #print(index)
            #print(pub.keys())

            print("pub = ")
            print(pub)

            print("pub.keys() = ")
            print(pub.keys())

            temp = {}
            temp['url'] = pub['URL']

            try:
                temp['lead_aff'] = list_affs(pub)[0]
                print('list_affs[0] = ')
                print(list_affs(pub)[0])
            except:
                temp['lead_aff'] = ''


            temp['snippet'] = unidecode.unidecode(pub['snippet'])
            temp['cites'] = pub['is-referenced-by-count']
            temp['title'] =  unidecode.unidecode(pub['title'][0])
            temp['doi'] = pub['DOI']
            temp['doi_url'] = 'https://doi.org/' + pub['DOI']
            temp['groups'] = pub['groups']

            try:
                if 'author' in pub.keys():
                    if 'family' in pub['author'][0].keys():
                        temp['author_lead'] = pub['author'][0]['family'] + ', ' + pub['author'][0]['given']
                        author_count = len(list(pub['author']))
                        temp['author_anchor'] = pub['author'][author_count-1]['family'] + ', ' + pub['author'][author_count-1]['given']

            except:
                temp['author_lead'] = ''
                temp['author_anchor'] = ''

            for fil in os.listdir(retrieve_path('groups')):

                fil_name = str(fil.split('.')[0])
                #temp[str('g_' + fil_name)] = 'False'
                if fil_name  in list(pub['groups']):
                    temp[str('g_' + fil_name)] = 1


            try:
                if 'funder' in pub.keys():
                    names = ''
                    for funder in pub['funder']:
                        name = funder['name']
                        names = names + name + ' | '

                    temp['funder'] = names

            except:
                temp['funder'] = ''

            try:
                temp['journal'] = pub['container-title'][0]
            except:
                temp['journal'] = pub['publication_info']


            table_pubs.append(temp)

                    # save the group as js
            descriptor_line = 'var table' + str(table_name) + ' = '
            dst_json = os.path.join(retrieve_path('tables_var'), table_name + '.js')

            with open(dst_json, "w") as f:

                f.write(descriptor_line + '\n' + '[' + '\n')

                for line in table_pubs:
                    print(line)
                    f.write(str(line) + ' , ' + '\n')
                #json.dump(lines, f, indent = 4)
                #f.write(');')
                f.write( ']' + '\n')

            f.close()
