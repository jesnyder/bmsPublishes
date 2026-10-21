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


def contact_list():
    """
    save a contact list
    """

    print("running contact_list")

    tasks = [1]
    if 1 in tasks: write_contacts()

    print("completed contact_list")



def write_contacts():
    """
    write a js variable describing the table
    """

    df = pd.DataFrame()
    for file in os.listdir(retrieve_path('crossref_json')):

        term = file.split('_')[0]
        table_name = term + '_table'

        table_pubs = []

        fil_src = os.path.join(retrieve_path('crossref_json'), file)
        json_src = retrieve_json(fil_src)

        for pub in json_src['results']:

            #index = list(json_src['results']).index(pub)
            #print(index)
            #print(pub.keys())

            try:
                lead_aff = list_affs(pub)[0]
            except:
                lead_aff  = ''

            if 'funder' in pub.keys():
                names = ''
                for funder in pub['funder']:
                    name = funder['name']
                    names = names + name + ' | '

                funder = names

            else:
                funder = {}

            try:
                journal = pub['container-title'][0]
            except:
                journal = " "

            try:
                lead_author =  pub['author'][0]['given'] + ' ' + pub['author'][0]['family']
                author_count = len(list(pub['author']))
                anchor_author = pub['author'][author_count-1]['given'] + ' ' + pub['author'][author_count-1]['family']

            except:
                lead_author = ''
                anchor_author = ''

            url = 'https://doi.org/' + pub['DOI']
            title = unidecode.unidecode(pub['title'][0])

            df_temp = pd.DataFrame()
            df_temp['contact?'] = ['No']

            df_temp['point_of_contact'] = [lead_author]
            df_temp['lead_author'] = [lead_author]
            df_temp['lead_aff'] = [lead_aff]
            df_temp['anchor_author'] = [anchor_author]

            email_subject = 'We appreciate your ' + str(journal) + ' paper'
            df_temp['email_subject'] = [str(email_subject)]

            #email_message = 'Good Day Dr. ' + str(pub['author'][0]['family']) + ', I found your 2022 paper - "' + str(title[:70]) + '... " - researching recent applications of RoosterBio products and expertise. Thank you for your fascinating paper. We compiled there published articles as a map and table, finding an increasing number exploring exosomes. You are invited to explore the map here: https://jesnyder.github.io/roosterAppreciates/ Would you join a short meeting to discuss your research findings and how we could help in your next steps? Please suggest a few times and we will accomodate. Continued success to you and your team. Best Regards, Jess '
            #df_temp['email_message'] = [str(email_message)]


            df_temp['pub_title'] = [title]
            df_temp['pub_url'] = [url]
            df_temp['published_by'] = [journal]
            df_temp['funded_by'] = [journal]
            df_temp['cites'] = [pub['is-referenced-by-count']]
            df_temp['pub_snippet'] = [unidecode.unidecode(pub['snippet'])]

            print("type(df_temp) = ")
            print(type(df_temp))

            for fil in os.listdir(retrieve_path('groups')):

                fil_name = str(fil.split('.')[0])
                df_temp[str('included_' + fil_name)] = [0]
                if fil_name  in list(pub['groups']):
                    df_temp[str('included_' + fil_name)] = [1]

            df = df._append(df_temp)
            df.to_csv(retrieve_path('contact_list'))
            df.to_csv(retrieve_path('pubs_xlsx'))
