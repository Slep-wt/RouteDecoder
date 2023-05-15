from collections import defaultdict
import tabula
import PyPDF2 as pdf2
import re
import json

##########################
# Filename: main.py
# Project: Route Decoder
# Purpose: Collates Airservices Australia ERSA GEN FPR routes into a software friendly format
# Author: Rakshan Chandu
##########################

fprDomestic = '9. FLIGHT PLANNING OPTIONS'

lookupStart = 0

with open('FPR_23MAR2023.pdf','rb') as f:
    reader = pdf2.PdfReader(f)
    for pn in range(len(reader.pages)):
        pageText = reader.pages[pn].extract_text()
        if re.search(fprDomestic, pageText):
            lookupStart = pn
            break
    tabula.convert_into("https://www.airservicesaustralia.com/aip/current/ersa/GUID_ersa-fac-2-2_23MAR2023.pdf","latest_routes.json", output_format='json', lattice=True, stream=False, pages=[str(lookupStart+1) + '-' + str(len(reader.pages))])

dat = ''
jmod = {'data':[]}
with open('latest_routes.json', 'r') as f:
    dat = f.read()

with open('latest_routes.json', 'w') as f:
    dat = dat.replace('%','Jet Only').replace('#','').replace('\\u003e', 'Non-Jet').replace('@','Jet Only (Mil)').replace('\\r',' ')
    dat = re.sub(r'"(top|left|right|width|height|bottom)":(\d+\.?\d*),', '', dat) # remove useless data
    dat = re.sub(r'"(extraction_method)":"lattice",', '', dat) # remove more junk
    dat = re.sub(r'\]\},\{"data":\[\[\{"text":""\}\]\]\},\{"data":\[', ',', dat) # reformatting mistakes made by the parser
    dat = re.sub(r'\]\},\{"data":\[', ',', dat) # more reformatting
    dat = re.sub(r'\[\{"text":""\}\],', '', dat) # and some more
    jorg = json.loads(dat)

    pdep = ''
    pdes = ''

    noteFinder = re.compile(r'\s\([A-Z].*\)')

    for routedata in jorg[0]['data']: # rebuild the json from the ground up (so its not fucked)
        if (5 <= len(routedata) <= 6):
            jroute = defaultdict(dict)
            dep = str(routedata[0]['text'])
            des = str(routedata[1]['text'])
            notes = str(routedata[2]['text'])
            route = str(routedata[4]['text'])

            hasMatch = noteFinder.search(route) # check for any route notes
            if hasMatch:
                route = noteFinder.sub('', route)
                if notes != '':
                    notes += hasMatch.group(0)
                else:
                    notes = hasMatch.group(0)[1:]

            if dep == '': # is this an alternate approved route?
                dep = pdep
                des = pdes

            jroute['dep'] = dep
            jroute['des'] = des
            jroute['route'] = route
            jroute['notes'] = notes

            pdep = dep
            pdes = des
            jmod['data'].append(jroute)

    dat = json.dumps(jmod)
    f.write(dat)