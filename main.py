from collections import defaultdict
from datetime import datetime, timezone
from dotenv import load_dotenv
import tabula
import PyPDF2
import re
import io
import requests
import json
import os

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

# So to automate things a little, lets update this based upon the AIRAC dates that AsA publishes
def checkAirac():
    airacDates = ['07SEP2023','30NOV2023','21MAR2024','13JUN2024','05SEP2024','28NOV2024'] # good until the end of 2024
    currentTime = datetime.now(timezone.utc)

    for i in range(0,len(airacDates)-1):
        if datetime.strptime(airacDates[i],'%d%b%Y').replace(tzinfo=timezone.utc) <= currentTime < datetime.strptime(airacDates[i+1],'%d%b%Y').replace(tzinfo=timezone.utc):
            cAirac = airacDates[i]
            break
    return cAirac

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
    jmod = {'valid':'','data':[]}
    
    jmod['valid'] = airac

    with open('latest_routes.json', 'w') as f:
        jorg = json.loads(dat)
        pdep = ''
        pdes = ''

        noteFinder = re.compile(r'\s\([A-z].*\)') # It does what it says
        crappyFormatFinder = re.compile(r'(?<=DCT)\s(?=DCT)') # so does this

        for routedata in jorg[0]['data']: # rebuild the json from the ground up (so its not fucked)
            if (5 <= len(routedata) <= 6):
                jroute = defaultdict(dict)
                jsecRoute = defaultdict(dict)
                dept = str(routedata[0]['text'])
                dest = str(routedata[1]['text'])
                notes = str(routedata[2]['text'])
                route = str(routedata[4]['text'])
                acft = 'Any'

                if (len(dept) <= 4 and len(dest) <= 4):
                    if notes != '':
                        acft = notes
                        notes = ''

                    hasNote = noteFinder.search(route) # check for any route notes
                    if hasNote:
                        route = noteFinder.sub('', route)
                        notes = hasNote.group(0)[1:]

                    if dept == '' and dest == '': # is this an alternate approved route?
                        dept = pdep
                        dest = pdes

                    hasCrappyFormat = crappyFormatFinder.search(route) # and is this route fucked?
                    if hasCrappyFormat:
                        splitRoutes = crappyFormatFinder.split(route) # ah shit its fucked... time to fix it
                        route = splitRoutes[0]
                        secRoute = splitRoutes[1]
                        jsecRoute['dept'] = dept
                        jsecRoute['dest'] = dest
                        jsecRoute['route'] = secRoute
                        jsecRoute['acft'] = acft
                        jsecRoute['notes'] = notes

                    jroute['dept'] = dept
                    jroute['dest'] = dest
                    jroute['route'] = route
                    jroute['acft'] = acft
                    jroute['notes'] = notes

                    pdep = dept
                    pdes = dest
                    
                    jmod['data'].append(jroute)
                    if (len(jsecRoute) != 0):
                        jmod['data'].append(jsecRoute)

        dat = json.dumps(jmod,indent=None, separators=(',',':'))
        f.write(dat) # done, got no clue if something will break this due to the limited data to test it on, but oh well
        return dat
    
def postData(data):
    requests.post(f'{API_BASE_URL}/routes', data=data, headers={'content-type':'application/json', 'X-API-KEY': API_KEY})
        
# Aight time to do cool shit

def main():
    activeAirac = checkAirac()
    fpr = getFpr(activeAirac)
    rawData = getData(fpr)
    data = createJSON(rawData, activeAirac)
    if API_BASE_URL is not None:
        postData(data) 

if __name__ == '__main__':
    main()