# RouteDecoder

Discount pdf scalper that gets the ERSA approved routes from AsA, since they are too lazy to make their own api...

Oh yeah it requires java 8+ and Python 3.8+ to be installed.

Dependencies:
- tabula-py
- PyPDF2
- requests

if posting to the routes api which is in development, chuck the base url and api key in a .env file.

## Installation

First off install the dependencies through pip:
> `pip install -r requirements.txt`  

Once this is done, you can either run the code:
> `python main.py`  

or set up a docker container and cron job to run it when you need.