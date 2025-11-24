import argparse
import json, sys, os, csv, re

import urllib.parse

__ACCEPTED_RECORDID_FIELDS = ['processid', 'sampleid']
#__EXCLUDED_FIELDS = ['record_id']

'''
#### Questions to clarify: 
1. how is array submitted in the jsonl?  Assume a list of valus
2. fk fields have integer as DB datatype but the submitted value is not.  This threw error when checking types.  
Should I convert to actual geo.id, tax.id THEN do validation?  Or should I just say if there is a fk involved, no field type/length check.  instead check against registry? However, what abbout notes which does need checkig.  
'''

## Main Function

def convert_upload_single_package (json_obj, bcdm_to_bold_mapping):
    data_json = json_obj['submission_packet']
    
    record_identifier = None
    for field in __ACCEPTED_RECORDID_FIELDS:
        if field in data_json and data_json[field]:
            record_identifier = data_json[field]
            break
    if record_identifier is None:
        raise Exception (f"[ERROR][Request {json_obj['id']}] {' or '.join (__ACCEPTED_RECORDID_FIELDS)} is required.")

    converted_obj = {}
    for bcdm_field in bcdm_to_bold_mapping:
        if bcdm_field in data_json:
            key = bcdm_to_bold_mapping[bcdm_field]['table']+"."+bcdm_to_bold_mapping[bcdm_field]['field']
            if key not in converted_obj:
                converted_obj [key]= {
                    'db_table':bcdm_to_bold_mapping[bcdm_field]['table'], 
                    'db_field':bcdm_to_bold_mapping[bcdm_field]['field'], 
                    'value': {} #data_json[bcdm_field], 
                }
            converted_obj[key]['value'][bcdm_field]=data_json[bcdm_field]

            if data_json[bcdm_field] == '':  
                converted_obj[key]['value'][bcdm_field]= None   # This translate to null in DB
    return converted_obj #{record_identifier:converted_obj}

########## Helper Functions ##########
def parse_datatype (bold_field_type):
    __SIMPLE_TYPES = ['timestamp without time zone', 'character', 'character varying', 'integer', 'point', 'real', 'date', 'jsonb', 'text']
    isArray = False
    max_length = None
    candidate_basic_type = bold_field_type.strip()
    if candidate_basic_type.endswith ("[]"):  # array
        isArray = True
        candidate_basic_type = candidate_basic_type.removesuffix("[]")
        #if not basic_type in __SIMPLE_TYPES:
        #    raise Exception (f"Invalid data type in mapping file for bold_field_type: {bold_field_type}")

    # single value
    if candidate_basic_type in __SIMPLE_TYPES:
        basic_type = candidate_basic_type
    elif candidate_basic_type.startswith("character varying") and candidate_basic_type.endswith(")") :
        basic_type = 'character varying'
        max_length = int(re.search (f'\((\d+)\)', candidate_basic_type).group(1))
    elif candidate_basic_type.startswith("character") and candidate_basic_type.endswith(")") :
        basic_type = 'character'
        max_length = int(re.search (f'\((\d+)\)', candidate_basic_type).group(1))
    else:
        raise Exception (f"Unexpected error processing bold_field_type: {bold_field_type}.")

    return basic_type, max_length, isArray
    
## TODO: revise for postgresql datatype check
## TODO: how to check array
def isvalid_value (value, expected_datatype, max_length = None):
    if value == "": return True
    
    #print (f"[DEBUG]IsValid Check on {value}, expected {expected_datatype} < {max_length} char", file=sys.stderr)
    # 1. Type check
    try:
        if expected_datatype in ['character', 'character varying']:
            str(value)
        elif expected_datatype in ['integer']:
            int(value)
        elif expected_datatype in ['real']:
            float(value)
        elif expected_datatype == ['timestamp without time zone', 'date']:
            str(value)
            dateparser.parse(value)
        #elif expected_datatype == 'char':
        #    if not isinstance (value, str) or not len(value)==1:
        #        return False
        elif expected_datatype == 'point':       # TODO: confirm input format
            temp_array = value.split(",")
            if len(temp_array) != 2:
                return False
        elif expected_datatype == 'array':
            value.split(",")
        elif expected_datatype == 'array of string':
            temp_array = value.split(",")
            for val in temp_array:
                str(val)
        elif expected_datatype == 'jsonb':
            json.loads(value)
        
    except Exception as e:
        #print (e, file=sys.stderr)
        return False
        
    # 2. Format check
    if max_length is not None: 
        if len (str(value)) > max_length:
            return False
    
    
    return True
    
def get_bcdm_to_bold_mapping (excluded_fields=None):   
    """
    This function returned a dictionary of db_field mapping where the keys are the universal fields.  If the optional param excluded_fields 
    is provided, the fields matching to ones in this list will NOT be returned.
    """
    delimiter = '__'
    filepath = args.mapping
    db_mapping = {}

    with open (filepath ) as mapping_file:
        rows = csv.DictReader(mapping_file, delimiter="\t")
        for row in rows:
            if len(row)==0: continue
            if not excluded_fields or row['bcdm_field'] not in excluded_fields:        # Remove this after testing. 
                info = row['bold_field'].split('.')
                
                # schema data type (as appeared in mapping)
                basic_type, max_length, is_array = parse_datatype(row['bold_field_type'])
                db_mapping [row['bcdm_field']]= {
                    'db': 'newdb12', 'table': info[0], 'field': info [1], 
                    'field_datatype': tuple([basic_type, is_array]) ,  'max_length': max_length,
                    'fk_table_field': row['sub_table_field'],
                    'fk_constraint': row['constraint'],
                    'policy':row['policy']
                }
                if row['sub_field_type']:
                    basic_type, max_length, is_array = parse_datatype(row['sub_field_type'])
                    db_mapping [row['bcdm_field']]['sub_field_datatype']= tuple([basic_type, is_array])
                    db_mapping [row['bcdm_field']]['sub_field_max_length'] = max_length

    return db_mapping

# TODO: add logic for mode? 
def validate_against_db_schema (json_obj, bcdm_to_bold_mapping, mode = 'warning'):
    data_json = json_obj['submission_packet']
    is_valid = True
    errors = []
    for bcdm_field in bcdm_to_bold_mapping:
    
        if bcdm_field in data_json and data_json[bcdm_field]:
            value = data_json[bcdm_field]
            
            if 'sub_field_datatype' in bcdm_to_bold_mapping[bcdm_field]:  #Foreign key invovled
                #print (f"    [CWEI] foreign key found for field {bcdm_field}", file=sys.stderr)
                #print (bcdm_to_bold_mapping[bcdm_field]['sub_field_datatype'])
                expected_datatype, expected_array = bcdm_to_bold_mapping[bcdm_field]['sub_field_datatype']
                expected_dataformat = bcdm_to_bold_mapping[bcdm_field]['sub_field_max_length']
            else:
                expected_datatype, expected_array = bcdm_to_bold_mapping[bcdm_field]['field_datatype']
                expected_dataformat = bcdm_to_bold_mapping[bcdm_field]['max_length']
            
            if type(value) is list: # Found list
                if not expected_array:
                    is_valid = False
                else:   
                    for single_value in value:                    
                        if not isvalid_value (single_value, expected_datatype, expected_dataformat):
                            is_valid = False
                            errors.append (f"[WARNING][Invalid Data Type]Field:{bcdm_field}; Value:{single_value}]")
                                
            else:   # Found Single value 
                if expected_array:  
                    is_valid = False
                else:
                    if not isvalid_value (value, expected_datatype, expected_dataformat):
                        is_valid = False
                        errors.append (f"[WARNING][Invalid Data Type 2]Field:{bcdm_field}; Value:{value}; Expect Type {expected_datatype}")
                            
    return is_valid, errors
    
def main(args):

    # Param processing
    if not os.path.exists(args.mapping):
        print ( f"[ABORT] Mapping file path not found: {args.mapping}", file=sys.stderr)
        sys.exit (1)

    count_rows = 0 #len(list(reader))
    error_records = []

    # Input Submission Processing (ALL or NOTHING)
    bcdm_to_bold_mapping = get_bcdm_to_bold_mapping() #__EXCLUDED_FIELDS)
    
    # Validation 
    results = []        # Only use if all_or_nothing
    for line in sys.stdin:
        json_obj = json.loads(line.strip("\n"))
        try:
            
            isValid, errors = validate_against_db_schema (json_obj, bcdm_to_bold_mapping)
            if not isValid:
                print ("\n".join (errors), file=sys.stderr)
                
            converted_obj = convert_upload_single_package (json_obj, bcdm_to_bold_mapping) 
            if not converted_obj: 
                raise Exception (f"[ERROR][Request {json_obj['id']}]Error converting bcdm record to upload json object")
            else:  
                if not args.atomicity == 'all-or-nothing':
                    print (json.dumps(converted_obj))
                else:
                    results.append (json.dumps(converted_obj))
        except Exception as e: 
            print (e, file=sys.stderr)
            if args.atomicity == 'all-or-nothing':
                print (f"[ABORT] all-or-nothing: detected invalid record. ", file=sys.stderr)
                break
                
    if len(results) > 0:
        print ("\n".join (results))
        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="""This tool takes validated BCDM objects in jsonl format and converts to an intermediate format. 
This tool can run any machine with access to internet.

Usage: python orchestrator_submission.py --data-tsv data_records.tsv --server-url 'http://localhost:8000" --username cwei --project CWEI --request-id TICKET#1234"
""")
    #parser.add_argument("--update", default=False, action=argparse.BooleanOptionalAction, help="If set, record existence is required to proceed with the update. Otherwise, new record submission is requested.")
    parser.add_argument("--mapping", type=str, required=True, help="File path for the BCDM field to BOLD DB field mapping")
    parser.add_argument("--atomicity", type = str, required=False, choices = ["all-or-nothing", "any"], default="all-or-nothing", help="any means that records are checks invididually; all-or-nothing means that all records must be valid to be accepted")

    #parser.add_argument ("--append", default=False, action=argparse.BooleanOptionalAction, help="If specified, append collapsed field instead of replace original")
    args = parser.parse_args()
 
    main(args)
