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
from urllib.parse import quote


from admin import reset_df
from admin import retrieve_df
from admin import retrieve_json
from admin import retrieve_list
from admin import retrieve_path
from admin import retrieve_ref


def geolocate_affs():
    """
    analyze data
    """

    print("running geolocate_affs")

    tasks = [1, 2, 3, 4]

    if 1 in tasks: list_missing({'reset': 'reset'})
    if 2 in tasks: list_all_affs()
    if 3 in tasks: compile_located()
    if 4 in tasks: openmaps_affs()
    if 3 in tasks: compile_located()

    print("completed geolocate_affs")


def organize_hardcoded_affs():
    """
    alphabetize hardcoded affs
    """

    all_path = retrieve_path("all_affs")
    with open(all_path, 'r') as file:
        all = json.loaf(file)

    affs = []
    for aff in all['affs']:
        affs.append(aff['name_original'])


    file_path = retrieve_path('affs_assigned')
    with open(file_path, 'r') as file:
        data = json.load(file)

    # Remove duplicates and sort
    data = sorted(list(set(data)))

    with open(file_path, 'w') as file:
        json.dump(data, file, indent=2)


def compile_located():
    """
    compile located as a local reference
    """

    compiled_affs = []

    for fil in os.listdir(retrieve_path('affs_json')):

        if '_located' not in fil: continue
        if 'compiled_' in fil: continue
        term = fil.split('_')[0]

        fil_src = os.path.join(retrieve_path('affs_json'), fil)

        json_src = retrieve_json(fil_src)

        for aff in json_src['affs']:

            if 'lat' not in aff.keys(): continue
            if aff in compiled_affs: continue
            compiled_affs.append(aff)

            json_affs = {}
            json_affs['count'] = len(compiled_affs)
            json_affs['affs'] = compiled_affs

            # save the dictionary as json
            fil_dst = os.path.join(retrieve_path('located_compiled'))
            #print('fil_dst = ' + str(fil_dst))
            with open(fil_dst, "w") as fp:
                json.dump(json_affs, fp, indent = 8)
                fp.close()


def edit_aff(name):
    """
    return name with commas to be readable by openstreetmaps
    """


    # check hardcoded changes to affiliation names
    # saved in user_provided affs_assigned affs_assigned.json

    print(retrieve_path('affs_assigned'))
    for aff in retrieve_json('affs_assigned')['affs']:
        if aff['name'] != name: continue


        if 'replacement' not in aff.keys(): continue
        name = aff['replacement']
        if aff['match_type'] == 'exact': name = aff['replacement']
        return(name)

    if '(' in name:
        if ')' in name:
            i = name.index('(')
            j = name.index(')')
            name = str(name[0:i] + ', ' + name[j+1:])


    term = 'Universite de Montreal'
    if term in name:
        name = 'University of Montreal'

    term = 'Fischell Department of BioengineeringUniversity of MarylandCollege Park Maryland20742'
    if term in name:
        name = 'Fischell Department of Bioengineering, University of Maryland, College Park Maryland'
        return(name)

    term = 'Department of Biochemistry, National University of Singapore, 119260 Singapore'
    if term in name:
        name = 'Department of Biochemistry, National University of Singapore'
        return(name)

    # substitutions
    term = 'Southern California Research Center for ALPD and Cirrhosis  Los Angeles California USA'
    if term in name:
        name = 'Southern California Research Center for ALPD and Cirrhosis, 1975 Zonal Ave Los Angeles CA USA'
        return(name)

    term = 'Childrens Hospital Los Angeles'
    if term in name:
        name = 'Childrens Hospital Los Angeles, Los Angeles CA USA'
        return(name)

    term = 'The Veterans Affairs Portland Health Care System 97239  Portland OR USA'
    if term in name:
        name = 'The Veterans Affairs Portland Health Care System, Oregon Health & Science University Portland OR USA'
        return(name)

    term = 'The University of Chicago'
    if term in name:
        name = 'The University of Chicago, Chicago, IL, USA'
        return(name)

    term = 'Department of Oral and Maxillofacial Surgery and Special Dental Care University Medical Center Utrecht  Utrecht GA 3508 The Netherlands'
    if term in name:
        name = 'Department of Oral and Maxillofacial Surgery and Special Dental Care, University Medical Center, Heidelberglaan Utrecht, Netherlands'
        return(name)

    term = 'Guangdong Academy of Sciences Guangdong Provincial Engineering Technology Research Center of Biomaterials  Guangzhou China'
    if term in name:
        name = 'Guangdong Academy of Sciences Guangdong Provincial Engineering Technology Research Center of Biomaterials,  Guangzhou, China'
        return(name)

    term = 'Department of Biomedical Engineering University of Michigan Ann Arbor Michigan USA'
    if term in name:
        name = 'Department of Biomedical Engineering, University of Michigan, USA'
        return(name)

    term = 'Faculty of Chemistry, Warsaw University of Technology, Noakowskiego 3 St., 00-664 Warsaw, Poland'
    if term in name:
        name = 'Faculty of Chemistry, Warsaw University of Technology, Warsaw, Poland'
        return(name)

    term = 'Department of Orthopaedic Surgery San Antonio Military Medical Center  USAF 59th MDW San Antonio TX 78234 USA'
    if term in name:
        name = 'Department of Orthopaedic Surgery, San Antonio Military Medical Center, San Antonio TX USA'
        return(name)

    term = 'Department of Mining and Materials Engineering McGill University  Montreal H3A 0E9 Canada'
    if term in name:
        name = 'Department of Mining and Materials Engineering, McGill University Montreal Canada'
        return(name)

    term = 'Experimental Surgery McGill University  Montreal H3G 1A4 Canada'
    if term in name:
        name = 'Experimental Surgery, McGill University,  Montreal Canada'
        return(name)

    term = 'West Pharmaceutical Services Inc'
    if term in name:
        name = 'West Pharmaceutical Services Inc, United Kingdom'
        return(name)

    term = 'The University of Texas M. D. Anderson Cancer Center'
    if term in name:
        name = ' M. D. Anderson Cancer Center, The University of Texas'
        return(name)

    term = 'Theradep'
    if term in name:
        name = 'TheraDep, San Jose CA USA'
        return(name)

    term = 'Department of Pediatrics Division of Pediatric Hematology/Oncology Aflac Cancer Center &amp; Blood Disorders Service of Children\'s Healthcare of Atlanta Emory University School of Medicine  Atlanta GA 30322 USA'
    if term in name:
        name = 'Department of Pediatrics Division of Pediatric Hematology/Oncology Aflac Cancer Center &amp; Blood Disorders Service of Children\'s Healthcare of Atlanta, Emory University School of Medicine,  Atlanta GA USA'
        return(name)


    term = 'Coulter Department of Biomedical Engineering Georgia Institute of Technology &amp; Emory University  Atlanta GA 30332 USA'
    if term in name:
        name = 'Coulter Department of Biomedical Engineering, Georgia Institute of Technology, Emory University  Atlanta GA, USA'
        return(name)

    term = 'Department of Periodontology, Peking University School and Hospital of Stomatology, National Clinical Research Center for Oral Diseases, National Engineering Laboratory for Digital and Material Technology of Stomatology, Beijing Key Laboratory of Digital Stomatology, Beijing'
    if term in name:
        name = 'Peking University, Beijing'
        return(name)

    term = 'Fischell Department of BioengineeringUniversity of MarylandCollege Park Maryland20742'
    if term in name:
        name = 'Fischell Department of Bioengineering, University of Maryland, College Park Maryland'
        return(term)

    term = 'Harvard Stem Cell Institute Cambridge Massachusetts'
    if 'term' in name:
        name = 'Harvard Stem Cell Institute, 7 Divinity Ave Cambridge, MA'
        return(name)

    term = 'RoosterBio'
    if term in name:
        term = 'RoosterBio, 5295 Westview Dr, Frederick, MD'
        return(name)

    term = 'Broad Institute of Harvard and MIT Cambridge Massachusetts'
    if term in name:
        term = 'Broad Institute of Harvard and MIT Cambridge Massachusetts, 415 Main St Cambridge, MA'
        return(name)


    terms = []
    terms.append('Childrens Hospital Los Angeles')
    terms.append('Clemson University')
    terms.append('Colorado School of Mines')
    terms.append('Cornell University')

    terms.append('Georgia Institute of Technology')
    terms.append('King Abdulaziz University')

    terms.append('Old Dominion University')
    terms.append('Santa Ana California')
    terms.append('The Ottawa Hospital Research Institute')

    terms.append('Virginia Commonwealth University')

    terms.append('University of Arkansas ')
    terms.append('University of Colorado Anschutz Medical Campus')
    terms.append('University of Georgia')
    terms.append('University of New South Wales')
    terms.append('University of Maryland')
    terms.append('University Medical Center Utrecht')
    terms.append('University of Michigan  Ann Arbor')
    terms.append('University of Otago Christchurch')
    terms.append('University of Oregon')
    terms.append(' University of Ottawa ')
    terms.append('University of Oxford')
    terms.append(' University of Southern California ')
    terms.append(' University of Virginia ')

    terms.append('US Food and Drug Administration')
    terms.append('Weill Cornell Medical College')


    for term in terms:

        if term in name:
            comma_term = str(',' + term + ', ')
            name = re.sub(term, comma_term, name)

    if ';' in name: name = name.replace(';', ',')

    term = 'EngineeringUniversity'
    if term in name:
        name = name.replace(term, 'Engineering, University')

    term = 'MedicineBaltimoreMDUSA'
    if term in name:
        name = name.replace(term, 'Medicine, Baltimore, MD, USA')

    return(name)

def aff_hardcoded(aff):
    """
    return the hardcoded address for an affiliation
    refer to a list in the user provided folder
    remove all special characters before passing back
    """

    hardcoded_affs = list(retrieve_json('affs_assigned')['affs'])

    for hardcode in hardcoded_affs:

        if hardcode['name_original'] != aff: continue
        aff = hardcode['name_simple']

    #aff = re.sub(r'[^a-zA-z0-9\s_\']+', ' ', aff)
    aff = re.sub(r'[^a-zA-z\s_\']+', ' ', aff)

    return(aff)


def openmaps_affs():
    """

    """
    located_affs = []

    json_src = retrieve_json('all_affs')
    for aff in json_src['affs']:

        #aff['name_edit'] = edit_aff(aff['name'])
        #aff["name_simple"] = re.sub(r'[^a-zA-z\s_\']+', ' ', aff['name'])

        response = {}

        try:
            found_json = retrieve_json('located_compiled')
            for found in found_json['affs']:
                if found['name_original'] == aff['name']:
                    response = found
                    continue
        except:
            print('not working')




        if response == {}: response = lookup_openmaps(aff)


        print('response = ')
        print(response)

        if 'lat' not in response.keys():
            print("lat missing")
            list_missing(aff)

        for key in response.keys():
            aff[key] = response[key]

        located_affs.append(aff)

        located_json = {}
        located_json['count'] = len(located_affs)
        located_json['affs'] = located_affs

        # save the dictionary as json
        fil_dst = os.path.join(retrieve_path('all_located'))
        #print('fil_dst = ' + str(fil_dst))
        with open(fil_dst, "w") as fp:
            json.dump(located_json, fp, indent = 8)
            fp.close()



def query_openmaps():
    """
    create geolocated.csv
    create geolocated.json
    create locations_missing.csv
    """

    # reset the list of missing locations
    report_missing('reset')

    responses = []

    # establish locations df
    df = retrieve_df('location')

    found_locs = []
    lats = []
    lons = []

    locations = list(df['location'])
    for loc in locations:

        lat, lon, response = lookup_openmaps(loc)


        found_locs.append(str(loc))
        lats.append(lat)
        lons.append(lon)

        df_temp = pd.DataFrame()
        df_temp['location'] = found_locs
        df_temp['lat'] = lats
        df_temp['lon'] = lons
        df_temp.to_csv(retrieve_path('geolocated'))

        save_value('location geolocated count', len(list(df_temp['location'])))


        if lat == 0: report_missing(loc)

        responses.append(response)
        response_dict = {}
        response_dict['item_count'] = len(responses)
        response_dict['response'] = responses
        save_json(response_dict, 'geolocated_json')


def list_missing(aff):
    """

    """
    fil_dst = os.path.join(retrieve_path('affs_missing'))

    affs = []
    print('aff = ')
    print(aff)

    if 'reset' not in aff.keys():

        if os.path.exists(fil_dst):

            missing_affs = retrieve_json('affs_missing')
            affs = retrieve_json('affs_missing')['affs']
            affs.append(aff)

    affs_missing = {}
    affs_missing['count'] = len(affs)
    affs_missing['affs'] = affs

    with open(fil_dst, "w") as fp:
        json.dump(affs_missing, fp, indent = 8)
        fp.close()


def lookup_openmaps(aff):
    """
    return lat and lon
    """

    loc = aff['name_simple']

    print('loc = ')
    print(loc)

    if ' ' in loc:
        terms = loc.split(' ')
    else:
        terms = [loc]

    for i in range(len(terms)):

        address = terms[i:]
        address = str(' '.join(address))
        #address = re.sub(r'[^a-zA-z0-9\s_]+', ' ', address)
        address = re.sub(r'[^a-zA-z0-9\s_]+', ' ', address)

        print(str(i) + ' address = ')
        print(address)

        #encoded_address = quote(address)

        # Basic URL format
        base_url = "https://nominatim.openstreetmap.org/search"

        # Format your address
        # address2 = "1600 Pennsylvania Avenue Washington DC"
        print("address = ")
        print(address)
        encoded_address = quote(address)

        # Complete URL
        specific_url = f"{base_url}?q={encoded_address}&format=json"

        #specific_url = "https://nominatim.openstreetmap.org/search" + urllib.parse.quote(address) +'?format=json'
        print(specific_url)
        #url_response = requests.get(specific_url)

        # Make the request
        #time.sleep(1)
        headers = {'User-Agent': 'MyApp/1.0'}
        response = requests.get(specific_url, headers=headers)

        print(f"Status code: {response.status_code}")


        data = response.json()

        print('specific_url = ')
        print(specific_url)

        try:
            text = response.text
            response = json.loads(text)

            print('response = ')
            print(response)
            return(response[0])

        except:
            continue




    return({})


def list_all_affs():
    """
    save affs as a json list
    """

    affs = []

    for fil in os.listdir(retrieve_path('crossref_json')):

        if 'all' not in fil: continue

        if '_' in fil: term = fil.split('_')[0]
        elif '.' in fil: term = fil.split('.')[0]
        else: term = fil

        fil_src = os.path.join(retrieve_path('crossref_json'), fil)
        print('fil_src = ' + str(fil_src))
        json_src = retrieve_json(fil_src)

        print(len(json_src['results']))

        for pub in json_src['results']:

            aff_json = {}

            print(pub.keys())

            if 'affs' not in pub.keys(): continue

            print(pub['affs'])

            if len(pub['affs']) == 0:
                aff_json['name'] = ""
                aff_json['name_original'] = ""
                aff_json['name_simple'] = ""

            for aff in pub['affs']:

                print("aff = ")
                print(aff)

                aff = unidecode.unidecode(aff)

                aff_json = {}
                aff_json['name'] = aff
                aff_json['name_original'] = aff
                aff_json['name_simple'] = aff_hardcoded(aff)

                if aff_json in affs: continue

                affs.append(aff_json)

                affs_json = {}
                affs_json['aff_count'] = len(affs)
                affs_json['affs'] = affs

                print("affs_json = ")
                print(affs_json)

            #print("affs_json = ")
            #print(affs_json)

            affs_json = {}
            affs_json['aff_count'] = len(affs)
            affs_json['affs'] = affs

            # save the dictionary as json
            fil_dst = os.path.join(retrieve_path('all_affs'))
            #print('fil_dst = ' + str(fil_dst))
            with open(fil_dst, "w") as fp:
                json.dump(affs_json, fp, indent = 8)
                fp.close()
