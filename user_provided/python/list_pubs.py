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
import requests
import pandas as pd
import shutil
import statistics
from statistics import mean
import time


from admin import reset_df
from admin import retrieve_json
from admin import retrieve_list
from admin import retrieve_path
from admin import retrieve_ref


def list_pubs():
    """
    analyze data
    """

    print("running list_pubs")

    tasks = [1, 2, 3, 4, 5]
    #tasks = [2, 3, 4]



    if 1 in tasks:

        years = [2023]
        terms = []
        terms.append('"Blue+Marble+Space+Institute+of+Science"')
        #terms.append('Multivascular networks and functional intravascular topologies within biocompatible hydrogels')
        ref_json = {'years': years, 'terms': terms, 'name': 'compiled'}
        search_gscholar(ref_json)
        build_json_src_list(ref_json)

    """
    if 2 in tasks:
        ref_json = {'years': [2025], 'name': '2025'}
        build_json_src_list(ref_json)
    """

    """
    if 3 in tasks:
        ref_json = {'years': [2024, 2025], 'name': 'recent'}
        build_json_src_list(ref_json)
    """

    if 4 in tasks:
        ref_json = {'years': ['all'], 'name': 'all'}
        build_json_src_list(ref_json)

    """
    if 5 in tasks:
        ref_json = {'years': ['all'], 'name': 'compiled'}
        build_json_src_list(ref_json)
    """

    print("completed list_pubs")



def build_json_src_list(ref_json):
    """
    return json for
    provide a list of inclusive years
    """

    list_meta = []

    for fil in os.listdir(retrieve_path('gscholar_json_scrape')):

        #print('fil = ' + str(fil))
        fil_year = int(fil.split('_')[1])
        for year in ref_json['years']:

            if year == 'all': year = fil_year
            if fil_year != year: continue
            #print('fil = ' + str(fil))

            fol_src = os.path.join(retrieve_path('gscholar_json_scrape'), fil)
            print('fol_src = ' + str(fol_src))
            json_src = retrieve_json(fol_src)

            for pub in json_src['results']:

                if pub in list_meta: continue
                list_meta.append(pub)
                json_meta = {}
                json_meta['results_count'] = len(list_meta)
                json_meta['results'] = list_meta

                # save the dictionary as json
                try:
                    fil_dst = os.path.join(retrieve_path('gscholar_json_summary'), str(ref_json['name']) + '.json')
                except KeyError:
                    print("ref_json = ")
                    print(ref_json)
                    continue

                # print('fil_dst = ' + str(fil_dst))
                with open(fil_dst, "w") as fp:
                    json.dump(json_meta, fp, indent = 8)
                    fp.close()


def search_gscholar(ref_json):
    """
    Retrieve json year by year
    """

    num_range = np.arange(0, 1000, 1)

    for term in ref_json['terms']:

        print(term)

        print('searching gscholar for term = ' + term)

        #json_to_dataframe()
        now = datetime.now()

        # dd/mm/YY H:M:S
        dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
        print("date and time =", dt_string)


        """
        if '-/-/-' in term:
            term_split = term.split('-/-/-')
            year_range = [term_split[0]]
            num_range = [0]
            term = term_split[1]

        else:
            search_year_min = int(retrieve_format('search_year_min'))-1
            print('search_year_min = ' + str(search_year_min))
            year_range = range(int(date.strftime("%Y")), search_year_min, -1)
            num_range = np.arange(0, 100, 1, dtype=int)
        """

        for year in ref_json['years']:

            result_list = []

            #work_completed('begin_acquire_gscholar_json_' + str(year), 0)
            for num in num_range:

                print('term = ' + str(term))
                print('year = ' + str(year))
                print('start num = ' + str(num*10))

                num_str = str(num).zfill(3)
                url = 'https://scholar.google.com/scholar?'
                url = url + 'start=' + str(int(num*10))
                url = url + '&q=' + term
                #url = url + '&hl=en&as_sdt=0,5'
                url = url + '&hl=en&as_sdt=0,5'
                url = url + '&as_ylo=' + str(year)
                url = url + '&as_yhi=' + str(year)

                """
                # check if recently scraped
                if check_scraped(dataset, term, year, num_str):
                    print('found: ' + dataset + ' ' + term +  ' ' + str(year) + ' ' + num_str)
                    continue
                """

                soup = retrieve_html(url)
                print('soup = ')
                print(soup)

                #if error_check(soup) == True: continue

                data = html_to_json(soup)
                print('data = ')
                print(data)
                if data == []: break
                #if len(data) < 10 and year != int(date.strftime("%Y")):
                    #work_completed('begin_acquire_gscholar_json_' + str(year), 1)

                for item in data:
                    item['search_year'] = year
                    result_list.append(item)

                json_results = {}
                json_results['results_count'] = len(result_list)
                json_results['results'] = result_list

                # save the dictionary as json
                fil_dst = os.path.join(retrieve_path('gscholar_json_scrape'), term + '_' + str(year) + '_' + str(len(result_list)).zfill(3) + '.json')
                #print('fil_dst = ' + str(fil_dst))
                with open(fil_dst, "w") as fp:
                    json.dump(json_results, fp, indent = 8)
                fp.close()


def retrieve_html(url):
    """

    """

    print('url = ')
    print(url)

    headers = {
        'User-agent':
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36 Edge/18.19582"
        }

    proxies = {
        'http': os.getenv('HTTP_PROXY') # or just type proxy here without os.getenv()
        }

    #time_string = retrieve_datetime()
    time.sleep(60 + 60*random.random())
    #print('Wait: ' + str(round(wait_time,2)) + ' from '  + str(time_string))

    html = requests.get(url, headers=headers, proxies=proxies).text
    soup = BeautifulSoup(html, 'lxml')

    return(soup)


def html_to_json(soup):
    """

    """

    # Scrape just PDF links
    for pdf_link in soup.select('.gs_or_ggsm a'):
        pdf_file_link = pdf_link['href']
        print(pdf_file_link)

    # JSON data will be collected here
    data = []

    # Container where all needed data is located
    for result in soup.select('.gs_ri'):
        title = result.select_one('.gs_rt').text

        try:
            title_link = result.select_one('.gs_rt a')['href']
        except:
            title_link = ''

        publication_info = result.select_one('.gs_a').text
        snippet = result.select_one('.gs_rs').text
        cited_by = result.select_one('#gs_res_ccl_mid .gs_nph+ a')['href']
        related_articles = result.select_one('a:nth-child(4)')['href']

        # get the year of publication of each paper
        try:
            txt_year = result.find("div", class_="gs_a").text
            ref_year = re.findall('[0-9]{4}', txt_year)
            ref_year = ref_year[0]
        except:
            ref_year = 0

        # get number of citations for each paper
        try:
            txt_cite = result.find("div", class_="gs_fl").find_all("a")[2].string
            citations = txt_cite.split(' ')
            citations = (citations[-1])
            citations = int(citations)
        except:
            citations = 0

        try:
            all_article_versions = result.select_one('a~ a+ .gs_nph')['href']
        except:
            all_article_versions = None

        data.append({
            'year': ref_year,
            'title': title,
            'title_link': title_link,
            'publication_info': publication_info,
            'snippet': snippet,
            'citations': citations,
            'cited_by': f'https://scholar.google.com{cited_by}',
            'related_articles': f'https://scholar.google.com{related_articles}',
            'all_article_versions': f'https://scholar.google.com{all_article_versions}',
        })

    return(data)
