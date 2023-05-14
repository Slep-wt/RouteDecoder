import tabula
import PyPDF2 as pdf2
import re


fpr_domestic = '9. FLIGHT PLANNING OPTIONS'

lookupStart = 0

with open('FPR_23MAR2023.pdf','rb') as f:
    reader = pdf2.PdfReader(f)
    for pn in range(len(reader.pages)):
        pagetext = reader.pages[pn].extract_text()
        #if (pagetext cont)
        if re.search(fpr_domestic, pagetext):
            lookupStart = pn
            break
    tabula.convert_into("https://www.airservicesaustralia.com/aip/current/ersa/GUID_ersa-fac-2-2_23MAR2023.pdf","latest_routes.csv", output_format='csv', lattice=True, stream=False, pages=[str(lookupStart+1) + '-' + str(len(reader.pages))])

csvdat = ''
with open('latest_routes.csv', 'r') as f:
    csvdat = f.read().replace('%','Jet Only').replace('#','').replace('>', 'Non-Jet').replace('@','Jet Only (Mil)')
    

with open('latest_routes.csv', 'w') as f:
    csvdat = re.sub(r'\([R-r]efer GEN-FPR(,|\n|\s)(\n|\s|)para \d\)', '', csvdat).replace('(refer requirements)', '')
    f.write(csvdat)
 
#with open('FPR_23MAR2023.pdf','rb') as f:
#    reader = pdf2.PdfReader(f)
#    start = False
#    for pn in range(len(reader.pages)):
#        pagetext = reader.pages[pn].extract_text()
#        #if (pagetext cont)
#        if re.search(fpr_domestic, pagetext):
#            start = True
#        if start:
#            fw.write(pagetext)
