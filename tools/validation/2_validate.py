import sys, os
import argparse
import json 
import pandas as pd

_MIN_REQUIRED_FIELDS = {
    'specimen:update': [tuple(['sampleid', 'processid'])],
    'specimen:new':['bold_recordset_code_arr', 'sampleid']
}

def read_control_vocab_file (file):
    df = pd.read_csv(file, sep='\t')
    data = { field: dict (zip (subdf['term'], subdf['term_id'])) for field, subdf in df.groupby('field')}
    return data
        
def read_geo_registry_file (file):
    rank_to_bcdm_mapping = {'country': 'country/ocean', 'province': 'province/state'}   # registry rank spelling vs bcdm fieldname
    df = pd.read_csv(file, sep='\t')    #id	rank	entity	country	country_iso	country_iso3	province
    data = { rank: dict (zip (subdf['entity'], subdf['id'])) for rank, subdf in df.groupby('rank')}
    
    # rename rank to corresponding bcdm field if found in rank_to_bcdm_mapping
    return {rank_to_bcdm_mapping.get(key_lookup, key_lookup): v for key_lookup, v in data.items()}

def read_tax_registry_file (file):
    df = pd.read_csv(file, sep='\t')
    data = { rank: dict (zip (subdf['taxon'], subdf['taxid'])) for rank, subdf in df.groupby('tax_rank')}
    return data 

    
#TODO: test tax & geo.  
# TODO: test mode
def validate_submission_obj (json_obj, allowed_ctrl_vocab_dict, ruleset_DF = None):
    isValid = True
    msgs = []
    
    # control vocab check
    submitted_fields = json_obj['submission_packet'].keys()
    fields_to_check = [ field for field in submitted_fields if field in allowed_ctrl_vocab_dict ]

    invalid_fields = []
    for field in fields_to_check:
        if not json_obj['submission_packet'][field]:
            continue
            
        if (json_obj['submission_packet'][field]) not in allowed_ctrl_vocab_dict[field]:
            print (f"[WARNING][Request {json_obj['id']}] Invalid term {json_obj['submission_packet'][field]} found for controlled field {field}", file = sys.stderr)
            invalid_fields.append (field)
        #else:
        #    print (f"[DEBUG][Request {json_obj['id']}] GOOD term found for controlled field {field}", file = sys.stderr)
   
    # Rule set check
    
    # Invalid field handling: warning or drop    
    if len(invalid_fields) > 0 and args.mode == 'filter':
        print (f"[ERROR][Request {json_obj['id']}] Invalid fields dropped ", invalid_fields, file = sys.stderr)
        for invalid_field in invalid_fields:
            del(json_obj['submission_packet'][invalid_field])


        
    
    return isValid, msgs

def main(args):
    error_count = 0

    # Validate params
    if not os.path.exists(args.ctrl_vocab):
        print ( f"[ABORT] Control Vocab file path not found: {args.ctrl_vocab}", file=sys.stderr)
        sys.exit (1)
            
    allowed_ctrl_vocab_dict = read_control_vocab_file (args.ctrl_vocab)
    allowed_ctrl_vocab_dict.update (read_geo_registry_file (args.geo))
    allowed_ctrl_vocab_dict.update (read_tax_registry_file (args.tax))

    # Process Input Data Jsonl
    results = []
    for line in sys.stdin:
        json_obj = json.loads(line.strip("\n"))
        isValid, msgs = validate_submission_obj (json_obj, allowed_ctrl_vocab_dict)
        if not isValid: 
            print ( "\n".join (msgs), file=sys.stderr)
            error_count+=1
        else:
            if not args.atomicity == 'all-or-nothing': 
                print (json.dumps(json_obj))
            else:
                results.append (json.dumps(json_obj))

    if error_count > 0 and args.atomicity == 'all-or-nothing': 
        print (f"[ABORT] all-or-nothing atomicity: {error_count} records invalid. ", file=sys.stderr)
        sys.exit (1)
    elif error_count== 0 and args.atomicity == 'all-or-nothing': 
        print ("\n".join (results))

    '''
    if error_count > 0:
        print (f"[ABORT] all-or-nothing: {error_count} records invalid. ", file=sys.stderr)
        sys.exit (1)
    elif len(error_count)== 0 and args.all_or_nothing:
        print ("\n".join (results))
    '''

if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="""This tool takes a data JSONL in valid submission package format and checks if submitted data conforms to BCDM data types.  If all-or-nothing flag is not set, 
        only the valid submission objects will be written to stdout.  All error messages should be captured in stderr.  

Usage: cat data_bcdm.jsonl | python 2_validate.py --ctrl-vocab /path/controlled_vocab.tsv --tax $bcdm/controlled_vocabulary_taxonomy.tsv --geo $bcdm/controlled_vocabulary_geopol.tsv --atomicity all-or-nothing > /file/path/filtered.jsonl 2> /file/path/err.log;"
""")
    #parser.add_argument("--batch-size", type=int, required=False, help="If set, the all-or-nothing applies to each batch.  Alternatively, all records submitted will be validated in single batch.")
    parser.add_argument("--atomicity", type = str, required=False, choices = ["all-or-nothing", "any"], default="all-or-nothing", help="any means that records are checks invididually; all-or-nothing means that all records must be valid to be accepted")
    parser.add_argument("--mode", type = str, required=False, choices = ["warning", "filter"], default="filter", help="If filter is specified, invalid term will be removed from the submission object")
    parser.add_argument("--ctrl-vocab", type=str, required=True, help="Path to the control vocab file.")
    parser.add_argument("--tax", type=str, required=True, help="Path to the taxonomy registry file.")
    parser.add_argument("--geo", type=str, required=True, help="Path to the georgraphy registry file.")
    
    #parser.add_argument("--rules", type=str, required=False, help="Path to the Validation rule set file")
    
    args = parser.parse_args()

    # Enforce dependency
    #if args.batch_size is not None and not args.atomicity == 'all-or-nothing':
    #    parser.error("--batch-size requires --atomicity all-or-nothing")

    main(args)