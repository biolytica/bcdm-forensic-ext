import argparse
import json, sys, os, csv, re
import pandas as pd

import urllib.parse

from conversion_util import isvalid_value, parse_datatype


__ACCEPTED_RECORDID_FIELDS = ['processid', 'sampleid']
__EXCLUDED_FIELDS = ['record_id']

#### TODO: Add Validate field types (copy from script 3_convert_BCDM_to_DB.py)


## Main Functions
def look_up_and_replace (data_json, lookup_DFs):

    errors = []
    
    # set taxid to Null if no match; else the found taxon in the registry
    for db_table_field in data_json.keys():
        #print (f"Field: {db_table_field} Original Value: {data_json[db_table_field]['value']}")
        
        if db_table_field in __LOOKUP_FUNC_MAPPING:
            lookup_func = __LOOKUP_FUNC_MAPPING[db_table_field]
            lookup_DF = lookup_DFs [db_table_field]
            if any (v in (None, "") for v in data_json[db_table_field]['value'].values()): # If there is non-blank values in submitted data
                fk_id = lookup_func (data_json[db_table_field]['value'], lookup_DF)
                if fk_id is not None:
                    data_json[db_table_field]['value']= fk_id
                else:
                    #print (data_json[db_table_field]['value'], file=sys.stderr)
                    errors.append (f"Failed to look up {db_table_field} with values")
                    #raise Exception (f"Failed to look up {db_table_field} with values")
            else: # If submitted values are all blank, allow clearing of foreign key ## TODO: confirm if this is desired behavior
                data_json[db_table_field]['value']= None
        else: 
            #print (f"Where am I? look_up_and_replace - Point 2A {db_table_field}]")
            if isinstance(data_json[db_table_field]['value'], dict):
                values = list(data_json[db_table_field]['value'].values())
                if len (values) == 1:
                    
                    #print (f"Where am I? look_up_and_replace - Point 2B {db_table_field}")
                    
                    # Handling single value vs array values
                    #print (data_json[db_table_field]['value'])
                    #data_json[db_table_field]['value'] = data_json[db_table_field]['value'].values()[0]
                    
                    
                    if type(values[0]) != list:  # Single value 
                        #data_json[db_table_field]['value'] = data_json[db_table_field]['value'][0]
                        data_json[db_table_field]['value'] = "".join ([value for value in values if value is not None])
                        if data_json[db_table_field]['value'] == "":    # set empty string to null
                            data_json[db_table_field]['value'] = None
                    else:       # List Values
                        data_json[db_table_field]['value'] = values[0]
                    
                    
                    #print (f"Where am I? Point 2C {db_table_field}]")
                else:
                    #print (f"Where am I? Point 2D {db_table_field}]")
                    #print (data_json[db_table_field]['value'], file=sys.stderr)
                    errors.append (f"Unexpected array detected for field {db_table_field}")    
                    #raise Exception (f"Unexpected array detected for field {db_table_field}")
    return errors
                 
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
        return taxid
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
    lowest_rank = None
    for rank in ordered_rank:
        if rank in geo_dict and geo_dict[rank]:
            lowest_rank = rank
            break
            
    # Case insensitive perfect match against registry
    if lowest_rank == 'province/state':
        match_DF = geo_DF[(geo_DF['rank']== 'province') & (geo_DF['entity'].str.lower()== geo_dict[lowest_rank].lower())]
        if not match_DF.empty:
            # check if country in match_DF matches submitted data
            lookup_value = geo_dict['country/ocean']
            if (match_DF['country'].str.lower()== lookup_value.lower()).any():
                geoid = int(match_DF['id'].iloc[0])
            
    else:
        match_DF = geo_DF[(geo_DF['rank']== 'country') & (geo_DF['entity'].str.lower()== geo_dict[lowest_rank].lower())]
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

def get_bold_field_type_from_mapping (excluded_fields=None):   
    """
    This function returned a dictionary of db_field mapping where the keys are the universal fields.  If the optional param excluded_fields 
    is provided, the fields matching to ones in this list will NOT be returned.
    """
    filepath = args.mapping
    db_mapping = {}

    with open (filepath ) as mapping_file:
        rows = csv.DictReader(mapping_file, delimiter="\t")
        for row in rows:
            if len(row)==0: continue
            if not excluded_fields or row['bold_field'] not in excluded_fields:
                info = row['bold_field'].split('.')
                                
                # schema data type (as appeared in mapping)
                basic_type, max_length, is_array = parse_datatype(row['bold_field_type'])
                db_mapping [row['bold_field']]= {
                    'db': 'newdb12', 'table': info[0], 'field': info [1], 
                    'field_datatype': tuple([basic_type, is_array]) ,  'max_length': max_length,
                    'fk_table_field': row['sub_table_field'],
                    'fk_constraint': row['constraint'],
                    'policy':row['policy']
                }
                '''if row['sub_field_type']:
                    basic_type, max_length, is_array = parse_datatype(row['sub_field_type'])
                    db_mapping [row['bcdm_field']]['sub_field_datatype']= tuple([basic_type, is_array])
                    db_mapping [row['bcdm_field']]['sub_field_max_length'] = max_length'''

    return db_mapping
    
# TODO: Continue from here 
# TODO: for foreign key fieldß, should not blindly check for integer as specified in bold_field_type column. 
#   if policy != lookup for field with sub_field_type, check data against sub_field_type.  
def validate_against_db_schema (data_json, bold_field_types_mapping):
    is_valid = True
    errors = []
    
    for db_table_field in data_json.keys():
        value = data_json[db_table_field]['value']
        if db_table_field in bold_field_types_mapping and value:
            expected_datatype, expected_array = bold_field_types_mapping[db_table_field]['field_datatype']
            expected_dataformat = bold_field_types_mapping[db_table_field]['max_length']
        
            if type(value) is list: # Found list
                #print (f"Found list for field {db_table_field}")
                #ßprint (value)
                if not expected_array:              
                    is_valid = False
                    errors.append (f"Array found for non-array field (Field: {db_table_field}; Value:{value})")
                else:   
                    for single_value in value:                    
                        is_value_valid, reason = isvalid_value (single_value, expected_datatype, expected_dataformat)
                        if not is_value_valid: 
                            is_valid = False
                            errors.append (f"Invalid Field {db_table_field} (Value:{single_value}; Reason:{reason})")
                                
            else:   # Found Single value 
                if expected_array:  
                    is_valid = False
                    errors.append (f"Non-array data found for array field (Field: {db_table_field}; Value:{value})")
                else:
                    is_value_valid, reason = isvalid_value (value, expected_datatype, expected_dataformat)
                    if not is_value_valid: 
                        is_valid = False
                        errors.append (f"Invalid Field {db_table_field} (Value:{value}; Reason:{reason})")
                            
    return is_valid, errors
    
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
    bold_field_types_mapping = get_bold_field_type_from_mapping(__EXCLUDED_FIELDS)
    taxDF = read_registry_file (args.tax)
    geoDF = read_registry_file (args.geo) #read_geo_registry_file (args.geo)
    
    registry_DF = {'specimen.fk_tax': taxDF, 'location.fk_geopol':geoDF}
    
    # Validation 
    results = []        # Only use if all_or_nothing
    line_idx = 0
    for line in sys.stdin:
        json_obj = json.loads(line.strip("\n"))
        try:
        
            # Foreign key replace 
            errors = look_up_and_replace (json_obj, registry_DF)
            if len (errors)> 0:
                raise Exception (f"Foreign key lookup failed: \n\t"+"\n\t".join (errors))

            # Validate against expected database data type 
            is_valid, errors = validate_against_db_schema (json_obj, bold_field_types_mapping)  # ASK: is this the right place
            if not is_valid:
                raise Exception (f"Invalid Data Type/Format: \n\t"+"\n\t".join (errors))
                               
            # Convert Data: group by db table to data structure ready for db upload
            converted_obj = convert_upload_single_package (json_obj) 
            if not converted_obj: 
                raise Exception (f"Error converting bcdm record to upload json object")
            else:  
                if not args.atomicity == 'all-or-nothing':
                    print (json.dumps(converted_obj))
                else:
                    results.append (json.dumps(converted_obj))
            
        except Exception as e: 
            print (f"[ERROR Exception][Line {line_idx}] {e}", file=sys.stderr)
            if args.atomicity == 'all-or-nothing':
                print (f"[ABORT] all-or-nothing: detected invalid record. ", file=sys.stderr)
                break
        line_idx+= 1
               
    if len(results) > 0:
        print ("\n".join (results))
        
if __name__ == "__main__":
    
    parser = argparse.ArgumentParser(
        description="""This tool takes a data TSV in BCDM format and submits the specimen record to the BOLD Database via the Submission API.  
This tool can run any machine with access to internet.

Usage: python 5_prep_for_db_load.py --tax $bcdm/controlled_vocabulary_taxonomy.tsv --geo $bcdm/controlled_vocabulary_geopol.tsv  --atomicity all-or-nothing > /file/path/db_format.jsonl 2>> /file/path/err.log;
""")
    parser.add_argument("--mapping", type=str, required=True, help="File path for the BCDM field to BOLD DB field mapping")
    parser.add_argument("--tax", type=str, required=True, help="Path to the taxonomy registry file.")
    parser.add_argument("--geo", type=str, required=True, help="Path to the georgraphy registry file.")
    parser.add_argument("--atomicity", type = str, required=False, choices = ["all-or-nothing", "any"], default="all-or-nothing", help="any means that records are checks invididually; all-or-nothing means that all records must be valid to be accepted")

    args = parser.parse_args()
 
    main(args)
