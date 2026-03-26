# Testing for Submission Pipeline

## Test Data
For each scripts, its corresponding test files will be prefixed with script number that matched the script names

  |**Script Name** | **Test File Prefix**|
  | :----------|:---------|
  |1_acceptability_check.py|script1_|
  |2_validate.py|script2_|
  |3_convert_BCDM_to_BOLD.py|script3_|
  |4_convert_to_verbatim.py|script4_|
  |5_prep_for_db_load.py|script5_|

## Example Commands
```bash

bcdm="../.."  # path to bcdm-forensic-ext repo root (relative to this test_data directory)
testDir="$bcdm/tools/test_data/"

conda activate
cat $testDir/script1_<test_case_name>.jsonl | python3 $bcdm/tools/validation/1_acceptability_check.py --bcdm-def $bcdm/field_definitions.tsv --reqfields sampleid bold_recordset_code_arr country/ocean phylum inst --atomicity any > $testDir/script1_validated.jsonl 2> $testDir/err.log;
cat $testDir/script2_<test_case_name>.jsonl | python3 $bcdm/tools/validation/2_validate.py --ctrl-vocab $bcdm/controlled_vocabularies.tsv --tax $testDir/controlled_vocabulary_taxonomy.tsv --geo $testDir/controlled_vocabulary_geopol.tsv --atomicity all-or-nothing  > $testDir/script2_validated.jsonl 2>> $testDir/err.log;
cat $testDir/script3_<test_case_name>.jsonl | python3 $bcdm/tools/conversion/3_convert_BCDM_to_DB.py --mapping $bcdm/mapping_BCDM_to_BOLD.tsv > $testDir/script3_<test_case>_OUT.jsonl 2>> $testDir/err.log;
cat $testDir/script4_<test_case_name>.jsonl | python3 $bcdm/tools/conversion/4_convert_to_verbatim.py --mapping-verbatim $bcdm/mapping_verbatim_to_BOLD.tsv --mode add --atomicity all-or-nothing > $testDir/script4_<test_case_name>_added_verbatim.jsonl 2>> $testDir/err.log;
cat $testDir/script5_<test_case_name>.jsonl | python3 $bcdm/tools/conversion/5_prep_for_db_load.py --tax $bcdm/controlled_vocabulary_taxonomy.tsv --geo $bcdm/controlled_vocabulary_geopol.tsv  --atomicity any > test.out 2>> $testDir/err.log;
```

## TODO
- BF-1: need SR to review the mapping (sub_table_field & constrating...)
    what will the constraint being used for?  For registries like tax & geo, currently look up is by the registry file.   
- Script 2: atomicty is not implemented properly. or did i misunderstood mode meaning? 
- Script 3: need test case for jsonb, timestamp without time zone, point
- Script 3: BF-4 did not implement #2) Add mapped fields while keeping original fields as an option
     can't remember why and what it is for.  
- Script 5: error formatting without any convention
- Script 5: if foreign key look up against registry files aren't successfully, an exception will be raised. 
    - null will wiped the field in db.  Is this allowed? 
- Script 5: verbatim data type isn't validated.  Only live fields are.  Because there is no mapping file showing db schema data type for verbatim fields
- Script 5: for certain FK field, should not blindky check for integer.  use policy to determine what to do?  For example, notes field.