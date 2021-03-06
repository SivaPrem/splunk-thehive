import os
import sys
import json
import uuid
import gzip
import csv

from string import Template
from subprocess import call
from thehiveapi.api import TheHiveApi
from thehiveapi.models import Alert, AlertArtifact, Case, CaseObservable


def get_config(config, csv_rows):

    url = config.get('url') # Get TheHive URL from Splunk configuration
    api_key = config.get('api_key') # Get TheHive API key from Splunk configuration

    api = TheHiveApi(url, api_key)

    # Get the payload for the case from the config, use defaults if they are not specified
    title = config.get('title')
    description = config.get('description', "No description provided.")
    severity = int(config.get('severity', 1))
    owner = config.get('owner')
    tlp = int(config.get('tlp', 2))
    tags = [] if config.get('tags') is None else config.get('tags').split(",")

    create_case(api, title, description, tlp, tags, csv_rows)

def create_case(api, title, description, tlp, tags, csv_rows):

    print('Create case')
    print('-----------------------------')
    case = Case(title=title, description=description, tlp=tlp, tags=tags)
    print(case.jsonify())

    response = api.create_case(case)
    if response.status_code == 201:
        print(json.dumps(response.json(), indent=4, sort_keys=True))
        print('')
        id = response.json()['id']
    else:
        print('Error: {} - {}'.format(response.status_code, response.text))
        sys.exit(0)

    create_observable(api, id, csv_rows)

def create_observable(api, id, csv_rows):

    # Filter empty multivalue fields
    parsed_rows = {key: value for key, value in csv_rows.iteritems() if not key.startswith("__mv_")}

    print('Create observable')
    print('-----------------------------')

    for (key, value) in parsed_rows.items():
        observ = CaseObservable(dataType=key,
                                data=[value],
                                tags=['Splunk'],
                                message='Created automatically by Splunk'
                                )
        print(observ)

        response = api.create_case_observable(id, observ)
        if response.status_code == 201:
            print(json.dumps(response.json(), indent=4, sort_keys=True))
            print('')
        else:
            print('ko: {}/{}'.format(response.status_code, response.text))
            sys.exit(0)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--execute": # make sure we have the right number of arguments - more than 1; and first argument is "--execute"
        payload = json.loads(sys.stdin.read()) # read the payload from stdin as a json string
        config = payload.get('configuration') # extract the config from the payload
        results_file = payload.get('results_file') # extract the file path from the payload
        if os.path.exists(results_file): # test if the results file exists
            try: # file exists - try to open it; fail gracefully
                with gzip.open(results_file) as file: # open the file with gzip lib, start making alerts
                    reader = csv.DictReader(file)
                    for csv_rows in reader:
                        get_config(config, csv_rows) # make the alert with predefined function; fail gracefully
                sys.exit(0)
            except IOError as e:
                print >> sys.stderr, "FATAL Results file exists but could not be opened/read"
                sys.exit(3)
        else:
            print >> sys.stderr, "FATAL Results file does not exist"
            sys.exit(2)
    else:
        print >> sys.stderr, "FATAL Unsupported execution mode (expected --execute flag)"
        sys.exit(1)
