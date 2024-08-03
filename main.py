import io
import json
import os
import re
from collections import defaultdict
from datetime import datetime, timezone

import PyPDF2
import requests
import tabula
from dotenv import load_dotenv

##########################
# Filename: main.py
# Project: Route Decoder
# Purpose: Collates Airservices Australia ERSA GEN FPR routes into a software friendly format
# Author: Rakshan Chandu
##########################

load_dotenv()

API_BASE_URL = os.getenv('API_BASE_URL')
API_KEY = os.getenv('API_KEY')
activeAirac = '07SEP2023' # default

# So to automate things a little, lets update this based upon the AIRAC dates that AsA publishes (This needs further work)

def getERSADates():
    content = requests.get('https://www.airservicesaustralia.com/industry-info/aeronautical-information-management/document-amendment-calendar/')
    matches = re.findall(r'ERSA (\d{2}\s[A-Z]{3}\s\d{4})', content.text)
    ERSADates = [x.replace(' ', '') for x in matches]
    return ERSADates

def checkAirac():
    airacDates = getERSADates()
    currentTime = datetime.now(timezone.utc)

    for i in range(0,len(airacDates)-1):
        if datetime.strptime(airacDates[i],'%d%b%Y').replace(tzinfo=timezone.utc) <= currentTime < datetime.strptime(airacDates[i+1],'%d%b%Y').replace(tzinfo=timezone.utc):
            cAirac = airacDates[i]
            break
    return cAirac
    
def validateRoute(data):
    adep = data['dept']
    ades = data['dest']
    route = data['route']
    notes = data['notes']

    if route[:3] == 'DCT' and route[-3:] == 'DCT':
        return [data, True]
    else:
        print(f'[Odd Route] {adep}-{ades}: {route}')
        amendedData = correctRoute(route)
        if amendedData == None:
            return [data, False]
        else:
            route = amendedData[0]
            if amendedData[1] != '':
                notes = f'{notes}. {amendedData[1]}.'
                data['notes'] = notes
            data['route'] = route
            return [data, True]

def correctRoute(route):
    corrected = False
    notes = ''

    # First look for any weird restrictions AsA has placed in the route
    substrs = re.split(r'((?:AT\s(?:OR|or)\sABV|BLW|BETWEEN\s(?:A|FL)\d*\s(?:AND|and))\s(?:A|FL)\d*\s)',route)
    if substrs[0] == '':
        substrs.pop(0)
        if len(substrs) == 2:
            notes = substrs[0][:-1]
            route = substrs[1]
            corrected = True

    # Is there a missing direct at the end?
    result = re.search(r'\s(\w+)$', route)
    if result != None:
        if result.group().strip() != 'DCT':
            route = f'{route} DCT'
            corrected = True

    # Same but for the front
    result = re.search(r'^(\w+)\s', route)
    if result != None:
        if result.group().strip() != 'DCT':
            route = f'DCT {route}'
            corrected = True

    # Sanity check
    if corrected:
        result = re.search(r'[^a-zA-Z\d\s\.]', route)
        if result != None:
            corrected = False

    if (corrected == True):
        print(f'[Validation] Route corrected: {route}')
        return [route, notes]
    else:
        return None

def getFpr(airac):
    fprUrl = "https://www.airservicesaustralia.com/aip/current/ersa/GUID_ersa-fac-2-2_{x}.pdf".format(x = airac)
    req = requests.get(fprUrl, allow_redirects=True)
    return io.BytesIO(req.content)

def getData(fpr):
    fprDomestic = '9. FLIGHT PLANNING OPTIONS' # Gotta hope AsA doesnt change this lol
    lookupStart = 0

    reader = PyPDF2.PdfReader(fpr)
    for pn in range(len(reader.pages)):
        pageText = reader.pages[pn].extract_text()
        if re.search(fprDomestic, pageText):
            lookupStart = pn
            break

    jdat = json.dumps(tabula.read_pdf(fpr, output_format='json', lattice=True, area=(24.665,22.325,560,401), pages=[str(lookupStart+1) + '-' + str(len(reader.pages))]), indent=None, separators=(',',':'))
    jdat = jdat.replace('%','Jet Only').replace('#','').replace('>', 'Non-Jet Only').replace('@','Jet Only (Mil)').replace('\\r',' ')
    jdat = re.sub(r'"(top|left|right|width|height|bottom)":(\d+\.?\d*),', '', jdat) # remove useless data like cropping and position info
    jdat = re.sub(r'"extraction_method":"lattice",', '', jdat) # remove more junk
    jdat = re.sub(r'\]\},\{"data":\[\[\{"text": ""\}\]\]\},\{"data":\[', ',', jdat) # reformatting mistakes made by the parser
    jdat = re.sub(r'\]\},\{"data":\[', ',', jdat) # more reformatting
    jdat = re.sub(r'\[\{"text": ""\}\],', '', jdat) # and some more 
    return jdat

def createJSON(dat, airac):
    jmod = {'valid':'','data':[],'invalid':[]}
    
    jmod['valid'] = airac

    validRouteCount = 0
    invalidRouteCount = 0

    #with open('latest_routes_'+airac+'.json', 'w') as f:
    jorg = json.loads(dat)
    pdep = ''
    pdes = ''

    noteFinder = re.compile(r'\s\([A-z].*\)') # It does what it says
    #noteFinder = re.compile(r'\((.*?)\)')
    crappyFormatFinder = re.compile(r'(?<=DCT)\s(?=DCT)') # so does this
    crappyRestrictedAreaFinder = re.compile(r'\s[ifIF].\s[A-z0-9\s]*\:\s') # I'm coming for you AIS-AF. You cant keep getting away with crappy formatting!!!

    for routedata in jorg[0]['data']: # rebuild the json from the ground up (so its not fucked)
        if (5 <= len(routedata) <= 6):

            routeArr = []
            jroute = defaultdict(dict)
            jsecRoute = defaultdict(dict)



            dept = str(routedata[0]['text'])
            dest = str(routedata[1]['text'])
            notes = str(routedata[2]['text'])
            route = str(routedata[4]['text'])
            secRoute = ''
            acft = 'Any'

            if (len(dept) <= 4 and len(dest) <= 4):
                if notes != '':
                    acft = notes
                    notes = ''

                hasNote = noteFinder.search(route) # check for any route notes
                if hasNote:
                    route = noteFinder.sub('', route)
                    notes = hasNote.group(0)[1:]
                
                hasNote = noteFinder.search(notes)

                if dept == '' and dest == '': # is this an alternate approved route?
                    dept = pdep
                    dest = pdes

                hasCrappyFormat = crappyFormatFinder.search(route) # and is this route fucked?
                hasCookedDefenceFormat = crappyRestrictedAreaFinder.search(route)
                if hasCrappyFormat or hasCookedDefenceFormat:
                    altnotes = notes
                    if (hasCrappyFormat):
                        splitRoutes = crappyFormatFinder.split(route) # ah shit its fucked... time to fix it
                        route = splitRoutes[0]
                        secRoute = splitRoutes[1]
                    else:
                        reResult = crappyRestrictedAreaFinder.search(route)
                        splitRoutes = crappyRestrictedAreaFinder.split(route)
                        route = splitRoutes[0]
                        secRoute = splitRoutes[1]
                        if altnotes == '' and reResult != None:
                            altnotes = f'{reResult.group().strip()[:-1]}.'
                        else:
                             altnotes = f'{reResult.group().strip()[:-1]}. {altnotes}.'
                    noteHasNote = noteFinder.search(altnotes)
                    if (noteHasNote):
                        jTertRoute = defaultdict(dict)
                        tertroute = noteFinder.sub('', altnotes)
                        tertnotes = hasNote.group(0)[1:]

                    jsecRoute['dept'] = dept
                    jsecRoute['dest'] = dest
                    jsecRoute['route'] = secRoute
                    jsecRoute['acft'] = acft
                    jsecRoute['notes'] = altnotes
                    routeArr.append(jsecRoute)


                jroute['dept'] = dept
                jroute['dest'] = dest
                jroute['route'] = route
                jroute['acft'] = acft
                jroute['notes'] = notes

                pdep = dept
                pdes = dest

                validatedData = validateRoute(jroute)

                if validatedData[1]:
                    jmod['data'].append(validatedData[0])
                    validRouteCount = validRouteCount + 1
                else:
                    jmod['invalid'].append(jroute)
                    invalidRouteCount = invalidRouteCount + 1

                if len(jsecRoute) != 0:
                    validatedData = validateRoute(jsecRoute)
                    if validatedData[1]:
                        jmod['data'].append(validatedData[0])
                        validRouteCount = validRouteCount + 1
                    else:
                        jmod['invalid'].append(jsecRoute)
                        invalidRouteCount = invalidRouteCount + 1
                    
    dat = json.dumps(jmod,indent=None, separators=(',',':'))
    print(f"[RouteDecoder] Found {validRouteCount} valid and {invalidRouteCount} invalid routes!")
    return dat
    
def writeData(filename, data):
    with open(filename, 'w', encoding='utf-8') as f:
        f.writelines(data)
    print(f"Routes written to {filename}")


def postData(data):
    r = requests.post(f'{API_BASE_URL}/routes', data=data, headers={'content-type':'application/json', 'X-API-KEY': API_KEY}, timeout=60)
    print(f"Data posted to {API_BASE_URL}")
    print(r.status_code, r.text)
        
# Aight time to do cool shit

def main():
    activeAirac = checkAirac()
    fpr = getFpr(activeAirac)
    rawData = getData(fpr)
    data = createJSON(rawData, activeAirac)
    filename = "latest_routes_" + activeAirac + ".json"
    if not os.path.exists(filename):
        try:
            writeData(filename, data)
        except Exception as e:
            print(f'Could not write to file: {e}')
        if API_BASE_URL is not None:
            postData(data) 
    else:
        print("File for this airac already exists, exiting.")
    

if __name__ == '__main__':
    main()