import argparse
import json, sys, os, csv, re
import pandas as pd

import urllib.parse

__ACCEPTED_RECORDID_FIELDS = ['processid', 'sampleid']
__EXCLUDED_FIELDS = ['record_id']

#### TODO: Add Validate field types (copy from script 3_convert_BCDM_to_DB.py)


## Main Functions
def look_up_and_replace (data_json, lookup_DFs):
    
    # set taxid to Null if no match; else the found taxon in the registry
    for db_table_field in data_json.keys():
        #print (f"Field: {db_table_field} Original Value: {data_json[db_table_field]['value']}")
        
        if db_table_field in __LOOKUP_FUNC_MAPPING:
            lookup_func = __LOOKUP_FUNC_MAPPING[db_table_field]
            lookup_DF = lookup_DFs [db_table_field]
            fk_id = lookup_func (data_json[db_table_field]['value'], lookup_DF)
            data_json[db_table_field]['value']= fk_id
            
        else: 
            if isinstance(data_json[db_table_field]['value'], dict) and len (data_json[db_table_field]['value']) == 1:
                data_json[db_table_field]['value'] = "".join ([value for value in data_json[db_table_field]['value'].values() if value is not None])
        
        #print (f"\tAfter: {data_json[db_table_field]['value']}")
    

def read_registry_file (file):
    #rank_to_bcdm_mapping = {'country': 'country/ocean', 'province': 'province/state'}
    df = pd.read_csv(file, sep='\t')
    return df
    #id	rank	entity	country	country_iso	country_iso3	province
    #data = { rank: dict (zip (subdf['taxon'], subdf['taxid'])) for rank, subdf in df.groupby('tax_rank')}
    
    # rename rank to corresponding bcdm field if found in rank_to_bcdm_mapping
    #return data # {rank_to_bcdm_mapping.get(key_lookup, key_lookup): v for key_lookup, v in data.items()}


def look_up_taxonomy (tax_dict, tax_DF):
    #print ("##### look_up_taxonomy", tax_dict)
    min_supporting_parent_ranks = 2
    ordered_rank = ['subspecies', 'species', 'genus', 'tribe', 'subfamily', 'family', 'order', 'class', 'phylum']
    
    # Find lowest rank submitted
    for rank in ordered_rank:
        if rank in tax_dict and tax_dict[rank]:
            lowest_rank = rank
            break
            
    # Look up taxid of the lowest rank
    taxid = None
    supporting_parent_rank_count = 0
    match_DF = tax_DF[(tax_DF['tax_rank']== lowest_rank) & (tax_DF['taxon'].str.lower()== tax_dict[lowest_rank].lower())]
    if match_DF.empty:
        pass
    elif lowest_rank == 'phylum':
        taxid = int(match_DF['taxid'].iloc[0])
        return taxid
            
    # Check for enough supporting parent rank
    for rank in ordered_rank[ordered_rank.index(lowest_rank)+1:]:
        if rank in tax_dict and tax_dict[rank]:
            lookup_value = tax_dict[rank]

            if not (match_DF[rank].str.lower()== lookup_value.lower()).any():
                #print (f"\t\tNot matching parent @ {rank}")
                break
            else:
                if supporting_parent_rank_count == min_supporting_parent_ranks or rank == 'phylum': 
                    #print (f"\t\tfound enough supporting parent @ {rank}")
                    taxid = int(match_DF['taxid'].iloc[0])
                    break
    
        supporting_parent_rank_count += 1
     
    return taxid
    
 
def look_up_geography (geo_dict, geo_DF):
    min_supporting_parent_ranks = 1
    ordered_rank = ['province/state', 'country/ocean']
    geoid = None
    
    # Find lowest rank submitted
    for rank in ordered_rank:
        if rank in geo_dict and geo_dict[rank]:
            lowest_rank = rank
            break

    if lowest_rank == 'province/state':
        match_DF = geo_DF[(geo_DF['rank']== 'province') & (geo_DF['entity'].str.lower()== geo_dict[lowest_rank].lower())]
        if not match_DF.empty:
            # check if country in match_DF matches submitted data
            lookup_value = geo_dict['country/ocean']
            if (match_DF['country'].str.lower()== lookup_value.lower()).any():
                geoid = int(match_DF['id'].iloc[0])
            
    else:
        match_DF = geo_DF[(geo_DF['rank']== lowest_rank) & (geo_DF['entity'].str.lower()== geo_dict[lowest_rank].lower())]
        if not match_DF.empty:
            geoid = int(match_DF['id'].iloc[0])
            
    return geoid 
    
__LOOKUP_FUNC_MAPPING = {
    'specimen.fk_tax': look_up_taxonomy, 
    'location.fk_geopol': look_up_geography
}

def convert_upload_single_package (data_json):

    df = pd.DataFrame([{**upload_info_dict} for uneeded_key, upload_info_dict in data_json.items()])
    
    # Group datahash based on db table and mapped to a dictionary of db_field and value to upload
    converted_dict = {}
    for table_group, fields_DF in df.groupby (by='db_table'):
        converted_dict [table_group] = dict(zip(fields_DF["db_field"], fields_DF["value"]))
        
    return converted_dict
    

########## Helper Functions ##########
def parse_datatype (bold_field_type):
    __SIMPLE_TYPES = ['timestamp without time zone', 'character', 'character varying', 'integer', 'point', 'real', 'date', 'jsonb']
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
    

def main(args):

    # Param processing
    if not os.path.exists(args.tax):
        print ( f"[ABORT] Mapping file path not found: {args.tax}", file=sys.stderr)
        sys.exit (1)
    if not os.path.exists(args.geo):
        print ( f"[ABORT] Mapping file path not found: {args.geo}", file=sys.stderr)
        sys.exit (1)
           
    count_rows = 0 #len(list(reader))
    error_records = []

    # Input Submission Processing (ALL or NOTHING)
    #bcdm_to_bold_mapping = get_bcdm_to_bold_mapping(__EXCLUDED_FIELDS)
    taxDF = read_registry_file (args.tax)
    geoDF = read_registry_file (args.geo) #read_geo_registry_file (args.geo)
    
    registry_DF = {'specimen.fk_tax': taxDF, 'location.fk_geopol':geoDF}
    #print ("Got the geoDF")
    
    # Validation 
    results = []        # Only use if all_or_nothing
    for line in sys.stdin:
            json_obj = json.loads(line.strip("\n"))
        #try:
            look_up_and_replace (json_obj, registry_DF)
            #print (json.dumps(json_obj))
            '''
            #look_up_and_replace (json_obj, bcdm_to_bold_mapping)
            #is_valid = validate_against_db_schema (json_obj, bcdm_to_bold_mapping)  # ASK: is this the right place
            '''
            
            # group by db table to data structure ready for db upload
            converted_obj = convert_upload_single_package (json_obj) 
            if not converted_obj: 
                raise Exception (f"[ERROR][Request {json_obj['id']}]Error converting bcdm record to upload json object")
            else:  
                if not args.all_or_nothing:
                    print (json.dumps(converted_obj))
                else:
                    results.append (json.dumps(converted_obj))
            
        #except Exception as e: 
        #    print (e, file=sys.stderr)
        #    if args.all_or_nothing:
        #        print (f"[ABORT] all-or-nothing: detected invalid record. ", file=sys.stderr)
        #        break
                
    if len(results) > 0:
        print ("\n".join (results))
        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="""This tool takes a data TSV in BCDM format and submits the specimen record to the BOLD Database via the Submission API.  
This tool can run any machine with access to internet.

Usage: python orchestrator_submission.py --data-tsv data_records.tsv --server-url 'http://localhost:8000" --username cwei --project CWEI --request-id TICKET#1234"
""")
    #parser.add_argument("--data", type=str, required=True, help="Path to the JSONL data file. All data will be url encoded")
    #parser.add_argument("--username", type=str, required=True, help="Username")
    #parser.add_argument("--update", default=False, action=argparse.BooleanOptionalAction, help="If set, record existence is required to proceed with the update. Otherwise, new record submission is requested.")
    #parser.add_argument("--mapping", type=str, required=True, help="File path for the BCDM field to BOLD DB field mapping")
    parser.add_argument("--tax", type=str, required=True, help="Path to the taxonomy registry file.")
    parser.add_argument("--geo", type=str, required=True, help="Path to the georgraphy registry file.")
    parser.add_argument("--all-or-nothing", action="store_true", help="True indicates all or nothing mode")

    args = parser.parse_args()
 
    main(args)
