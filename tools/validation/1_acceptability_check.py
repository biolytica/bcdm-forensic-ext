import sys, os
import argparse
import json
import re
import dateparser
from datetime import datetime
import pandas as pd

_ACCEPTED_SUB_TYPES = ['specimen']
'''_MIN_REQUIRED_FIELDS = {
    'specimen:update': [tuple(['sampleid', 'processid'])],
    'specimen:new':['bold_recordset_code_arr', 'sampleid']
}'''

PLACEHOLDER_REGEX = {
    "%s": ".+",          # any non-empty string
    "%d": r"\d+",        # integer number
    "%f": r"[-+]?\d*\.?\d+",  # float number
}

def convert_placeholder_to_regex (value, match_empty_string = False):
    regex_str = re.escape(value)  # escape all special characters
    if match_empty_string:
        PLACEHOLDER_REGEX["%s"]=".*"
    for placeholder, replacement in PLACEHOLDER_REGEX.items():
        # replace the escaped placeholder with the regex pattern
        regex_str = regex_str.replace(re.escape(placeholder), replacement)
    return re.compile(regex_str)

def read_mapping (file):
    return pd.read_csv(file, sep='\t') #, index_col="field")

def isvalid_value (value, expected_datatype, expected_dataformat):
    if value == "": return True
    # 1. Type check
    try:
        if expected_datatype == 'string':
            str(value)
        elif expected_datatype in ['int', 'integer']:
            int(value)
        elif expected_datatype in ['float', 'number']:
            float(value)
        elif expected_datatype == ['string:date', 'date']:
            str(value)
            dateparser.parse(value)
        elif expected_datatype == 'char':
            if not isinstance (value, str) or not len(value)==1:
                return False
        elif expected_datatype == 'geopoint':       # TODO: confirm input format
            temp_array = value.split(",")
            if len(temp_array) != 2:
                return False
        elif expected_datatype == 'array':
            value.split(",")
        elif expected_datatype == 'array of string':
            temp_array = value.split(",")
            for val in temp_array:
                str(val)
        elif expected_datatype == 'json':
            json.loads(value)
        
    except Exception as e:
        #print (e, file=sys.stderr)
        return False
        
    # 2. Format check
    
    try: 
        if expected_dataformat != 'default':
            #print (f"Value:{value}; Type:{expected_datatype}; Format:{expected_dataformat} Checking...")
            if expected_datatype =='string:date':
                #blah = dateparser.parse(value, date_formats=[expected_dataformat], settings={'STRICT_PARSING': True})
                parsed_date = datetime.strptime(value, expected_dataformat)
                if parsed_date.strftime(expected_dataformat) != date_str:
                    #print (value, file=sys.stderr)
                    #print (parsed_date, file=sys.stderr)
                    #print (parsed_date.strftime(expected_dataformat), file=sys.stderr)
                    return False

            elif expected_datatype == 'string':
                regex_format = convert_placeholder_to_regex (expected_dataformat)
                if not re.fullmatch(regex_format, value):
                    #print ("WHY", value, expected_dataformat, regex_format)
                    return False
                
    except Exception as e:
        #print (e, file=sys.stderr)
        return False
    return True
            
def validate_submission_obj (json_obj, bcdm_mapping):
    isValid = True
    msgs = []
    
    if json_obj['submission_type'] not in _ACCEPTED_SUB_TYPES:
        msgs.append ( f"[ERROR] Invalid submission type: Expected {','.join (_ACCEPTED_SUB_TYPES)}, received {json_obj['submission_type']}")
        isValid = False

    # min required field checks
    for req_field in args.reqfields:
        if (bcdm_mapping['field'] != req_field).all():  #ignore if field is not bcdm
            continue
            
        if req_field not in json_obj['submission_packet'] or json_obj['submission_packet'][req_field] in ('', None) :
            msgs.append ( f"[ERROR][Request {json_obj['id']}] Required column {req_field} is missing or empty")
            isValid = False

    # data model validator
    submitted_fields = json_obj['submission_packet'].keys()
    #print ("[DEBUG] submitted_fields: ", submitted_fields)
    
    # Remove non-BCDM data from submission 
    invalid_fields = [ field for field in submitted_fields if (bcdm_mapping['field'] != field).all() ]
    if len(invalid_fields) > 0:
        for invalid_field in invalid_fields:
            del(json_obj['submission_packet'][invalid_field])
        print (f"[WARNING][Request {json_obj['id']}] Invalid fields found ", invalid_fields, file = sys.stderr)
    print (f"[LOG][Request {json_obj['id']}] Accepted fields: {','.join(json_obj['submission_packet'].keys())}", file = sys.stderr)

    # datmatype check against mapping
    invalid_fields = []
    for bcdm_field in json_obj['submission_packet']:
        if json_obj['submission_packet'][bcdm_field] and (bcdm_mapping['field'] == bcdm_field).any():    # only if data submitted and also valid fields
            #print (f"[DEBUG] Check type for {bcdm_field}")
            row = bcdm_mapping[bcdm_mapping['field']== bcdm_field].iloc[0]
            if not isvalid_value (json_obj['submission_packet'][bcdm_field], row['data_type'], row['data_format']):
                print (f"[DEBUG] Bad type for {bcdm_field}; value:{json_obj['submission_packet'][bcdm_field]}; type:{row['data_type']}; format:{row['data_format']}", file=sys.stderr)
                invalid_fields.append (bcdm_field)

    if len(invalid_fields)>0:
        isValid = False
        msgs.append (f"[ERROR][Request {json_obj['id']}] Invalid data type/format for {len(invalid_fields)} fields: {','.join (invalid_fields)}")
    return isValid, msgs

def main(args):
    error_count = 0

    # Validate params
    if not os.path.exists(args.bcdm_def):
        print ( f"[ABORT] Mapping file path not found: {args.bcdm_def}", file=sys.stderr)
        sys.exit (1)
    bcdm_mapping = read_mapping (args.bcdm_def)
    
    # Process Input Data Jsonl
    results = []
    for line in sys.stdin:
        line = line.strip("\n")
        isValid, msgs = validate_submission_obj (json.loads(line), bcdm_mapping)
        if not isValid: 
            print ( "\n".join (msgs), file=sys.stderr)
            error_count+=1
        else:
            if not args.atomicity == 'all-or-nothing': 
                print (line)
            else:
                results.append (line)

    if error_count > 0 and args.atomicity == 'all-or-nothing': 
        print (f"[ABORT] all-or-nothing atomicity: {error_count} records invalid. ", file=sys.stderr)
        sys.exit (1)
    elif error_count== 0 and args.atomicity == 'all-or-nothing': 
        print ("\n".join (results))

if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description="""This tool takes a data JSONL in BCDM format and checks whether submission objects are in valid format.  If all-or-nothing is set for atomicity, 
        all submission objects must be valid before they will be written to stdout.  All error messages should be captured in stderr.  

Usage: cat data_bcdm.jsonl | python acceptability_check.py  --bcdm_def /file/path/field_definitions.tsv --update --atomicity all-or-nothing > /file/path/filtered.jsonl 2> /file/path/err.log;
""")
    #parser.add_argument("--username", type=str, required=True, help="Username")
    parser.add_argument("--bcdm-def", type=str, required=True, help="Path to the BCDM definition file.")
    parser.add_argument("--atomicity", type = str, required=False, choices = ["all-or-nothing", "any"], default="all-or-nothing", help="any means that records are checks invididually; all-or-nothing means that all recotds must be valid to be accepted")
    parser.add_argument("--reqfields", type=str, nargs='+', required=False,default=["sampleid","country","phylum"], help="list of bcdm fields that are required for submission")
    args = parser.parse_args()
    main(args)