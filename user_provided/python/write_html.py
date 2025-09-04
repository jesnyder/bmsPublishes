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
import urllib.request


from admin import make_color
from admin import reset_df
from admin import retrieve_df
from admin import retrieve_json
from admin import retrieve_list
from admin import retrieve_path
from admin import retrieve_ref

from meta_pubs import list_affs


def write_html():
    """
    analyze data
    """

    print("running write_html")

    with open(retrieve_path('html_temp'), "w+") as f:

        for fol in os.listdir(os.path.join('docs', 'js')):

            if '.' in fol: continue
            print('fol = ' + str(fol))

            for fil in os.listdir(os.path.join('docs', 'js', fol)):

                if '.js' not in fil: continue

                f.write('\n')
                f.write("<script src=\"")
                f.write(os.path.join('js', fol, fil))
                f.write("\"></script>")
                #f.write('\n')


        f.close()


    print("completed write_html")



def save_geojson(src_pathname):
    """
    for each aff or each pub
    create a line of geojson
    """

    for fil in os.listdir(retrieve_path(src_pathname)):

        features = []

        fil_name = fil.split('.')[0]

        if 'compiled' in fil: continue
        if '_located' in fil: continue

        fil_src = os.path.join(retrieve_path(src_pathname), fil)
        if 'results' in retrieve_json(fil_src).keys(): key = 'results'
        elif 'pubs' in retrieve_json(fil_src).keys(): key = 'pubs'

        for pub in retrieve_json(fil_src)[key]:

            color = make_color()

            for aff in pub['affs']:

                found = retrieve_geolocated(aff)

                if found == {}: continue

                print('aff = ' + str(aff))

                print('found = ')
                print(found)

                if 'lat' not in found.keys(): continue


                geolocated = {}
                geolocated['lat'] = found['lat']
                geolocated['lon'] = found['lon']
                geolocated['display_name'] = found['display_name']
                geolocated['aff'] = aff
                geolocated['title'] = pub['title'][0]
                geolocated['url'] = pub['doi_url']
                geolocated['color'] = color
                geolocated['radius'] = 10 + 3*float(pub['is-referenced-by-count'])
                geolocated['opacity'] = 0.7
                geolocated['zindex'] = int(500 - geolocated['radius'])
                geolocated['paneName'] = 'pane_' + str(int(1000 - geolocated['radius']))
                #geolocated['journal'] = pub['container-title']

                feature = {}
                feature['type'] = 'Feature'
                feature['properties'] = make_prop(geolocated)
                feature['geometry'] = make_geo(geolocated)
                features.append(feature)


                geojson = {}
                geojson['type'] = 'FeatureCollection'
                geojson['features'] = features

                dst_json = os.path.join(retrieve_path('map_js'), fil_name + '.js')
                #print('dst_json = ' + str(dst_json))
                with open(dst_json, "w") as f:
                    f.write('var ' + ' ' + str(fil_name) + ' = ')
                    json.dump(geojson, f, indent = 6)
                    f.write(';')
                f.close()





def retrieve_geolocated(aff):
    """
    return json for found
    """

    print('fil_src = ')
    print(retrieve_path('all_located'))

    aff = unidecode.unidecode(aff)

    for found in retrieve_json('all_located')['affs']:

        if found['name'] != aff: continue

        print('aff = ')
        print(aff)

        print('found = ')
        print(found)

        return(found)

    return({})


def make_geo(geolocated):
    """
    return json for geometry
    """

    geo = {}
    geo['type'] = 'Point'
    geo['coordinates'] = [ float(geolocated['lon']), float(geolocated['lat'])]
    return(geo)


def make_prop(geolocated):
    """
    return json describing prop
    """
    prop = {}
    for key in geolocated.keys():
        prop[key] = geolocated[key]
    return(prop)
