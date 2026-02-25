# Created on : Nov 25, 2025, 11:32:10 p.m.
# Author     : cwei
import re 
import sys

def save_error (errors, line_index, data_obj, tag, error):
    title = f"#### Line {line_index}, {data_obj['specimen']['sampleid']},  {data_obj['seqentry']['processid']}"
    if title not in errors: errors[title]= []
    errors[title].append (f"\t{tag}:{error}")

def get_formatted_errors (errors):
    concat_str = ""
    for title, msgs in errors.items():
        concat_str =+ title + "\n"
        concat_str =+ "\n".join (msgs) + "\n"
    return concat_str  
    
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
    if value == "": return True, None
    
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
                return False, "Invalid point format: expected 2 comma separated values"
            for val in temp_array:
                float(val)
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
        return False, e # f"Invalid value for type {expected_datatype}"
        
    # 2. Format check
    if max_length is not None: 
        if len (str(value)) > max_length:
            return False, f"Exceed allowed max length {max_length}"
    
    return True, None