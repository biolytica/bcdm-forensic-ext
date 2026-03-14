# BCDM Forensic Extension

This repository defines the **BCDM Forensic Extension**, a Frictionless Data-compatible set of field definitions, controlled vocabularies, mappings, and helper utilities for exchanging barcode data in forensic workflows.

It builds on the **Barcode Core Data Model (BCDM)** by retaining the shared core terms used for specimen, taxonomy, collection, and sequence data while adding the additional metadata needed in forensic settings. The goal is to support interoperability between systems that already understand BCDM and systems that also need forensic context such as evidence handling, biobanking, collector provenance, and identification confidence.

In practical terms, this repository is not the upstream BCDM README or core-only specification. It is the **forensic extension layer** for BCDM.

The model follows the [Frictionless Data](https://frictionlessdata.io) approach to structured, portable data packages and includes a package metadata template for downstream packaging and validation.

## Why This Extension Exists

Core BCDM terms are well suited to barcode-centered biodiversity data exchange, but forensic use cases often require more context than the base model provides. This extension adds fields that help preserve:

- sample and evidence identifiers
- biobank accessioning metadata
- collector affiliation and contact details
- sealed-bag and kit tracking information
- specimen tag and measurement metadata
- identification confidence and provisional field names
- chain-of-custody-oriented context such as `coc_start_coord`

This lets forensic applications exchange barcode records without losing the operational metadata that matters in investigative, compliance, or evidentiary workflows.

## Repository Contents

- [field_definitions.tsv](field_definitions.tsv): canonical field list for the model, including field name, data type, format, grouping, and definition
- [controlled_vocabularies.tsv](controlled_vocabularies.tsv): controlled terms used by selected BCDM and forensic-extension fields
- [mapping_BCDM_to_BOLD.tsv](mapping_BCDM_to_BOLD.tsv): mapping from BCDM fields to BOLD-oriented database fields
- [mapping_BOLD_to_BCDM.tsv](mapping_BOLD_to_BCDM.tsv): reverse mapping from BOLD exports into BCDM field names
- [mapping_BCDM_to_DWC.tsv](mapping_BCDM_to_DWC.tsv): alignment between BCDM fields and Darwin Core terms where equivalents exist
- [mapping_verbatim_to_BOLD.tsv](mapping_verbatim_to_BOLD.tsv): mapping for preserving verbatim source values alongside normalized values
- [package.metadata.template.json](package.metadata.template.json): starter template for describing a Frictionless Data package
- [registered_soverign_and_maritime_areas.tsv](registered_soverign_and_maritime_areas.tsv): reference list of sovereign states and maritime areas with ISO codes
- [tools/validation](tools/validation): helper scripts for acceptability and controlled-vocabulary validation
- [tools/conversion](tools/conversion): helper scripts for converting between BCDM, verbatim, and BOLD-style database payloads
- [tools/example_bcdm.jsonl](tools/example_bcdm.jsonl) and [tools/example_db.jsonl](tools/example_db.jsonl): example records

## Source of Truth

The standards content in this repository lives primarily in the TSV and JSON template artifacts, not in the Python utilities.

- Treat [field_definitions.tsv](field_definitions.tsv), [controlled_vocabularies.tsv](controlled_vocabularies.tsv), and the mapping files as the authoritative model definition.
- Treat [package.metadata.template.json](package.metadata.template.json) as the Frictionless-compatible packaging template for publishing or exchanging datasets that use this extension.
- Treat the scripts under [tools](tools) as reference implementation helpers for validation, normalization, and conversion.

## Data Model Scope

The current [field_definitions.tsv](field_definitions.tsv) file defines **109 fields** across the base model and extension-specific groups. These include:

- core BCDM groups for specimen, taxonomy, collection, sequence, and record organization
- forensic extension fields for accessioning, collector provenance, sealed bags, kit identifiers, and confidence metadata
- advanced forensic fields for specimen measurements and chain-of-custody-related capture context
- feature rollup fields for summary or derived record features

Examples of forensic-extension terms currently defined in this repository include:

- `saps_sample_reference_id`
- `biobank_catalog_number`
- `biobank_accessioning_date`
- `biobank_institution`
- `collector_affiliation`
- `collector_email`
- `collector_id`
- `collector_phone`
- `method_of_delivery`
- `reference_grade`
- `sealed_bag_contents`
- `sealed_bag_ids`
- `sample_collection_kit_id`
- `specimen_tag_id`
- `specimen_tag_type`
- `confidence_of_identification`
- `coc_start_coord`
- `field_provisional_name`

## Field Definition Format

The schema in [field_definitions.tsv](field_definitions.tsv) is the primary reference for supported fields.

| Column | Meaning |
| :-- | :-- |
| `field` | Canonical BCDM field name |
| `data_type` | Expected value type such as `string`, `integer`, `float`, `string:date`, `array`, `json`, or `geopoint` |
| `data_format` | Additional format constraint, such as a date format or pattern |
| `bold:field_group` | Logical grouping used in the model and related BOLD mappings |
| `definition` | Human-readable meaning of the field |

## Minimal Record Example

The following example shows the mix of core BCDM terms and forensic-extension terms that this repository is designed to support:

```json
{
  "sampleid": "CASE-2026-001",
  "processid": "FORENSIC-001.COI-5P",
  "marker_code": "COI-5P",
  "country/ocean": "South Africa",
  "collection_date_start": "2026-02-03",
  "biobank_catalog_number": "BIOBANK:000123",
  "saps_sample_reference_id": "SAPS-SEAL-77821",
  "sealed_bag_ids": ["BAG-01"],
  "sealed_bag_contents": ["biomaterial"],
  "confidence_of_identification": "high"
}
```

## Interoperability and Mappings

This extension is designed to keep forensic records compatible with broader biodiversity data exchange patterns.

- **BCDM to BOLD** mappings support transformation into BOLD-oriented database structures used by the conversion scripts.
- **BOLD to BCDM** mappings support normalization of exported BOLD data back into the shared BCDM field vocabulary.
- **BCDM to Darwin Core** mappings document where standard Darwin Core terms can be used for exchange with other biodiversity systems.
- **Verbatim mappings** preserve original submitted text or source values alongside normalized fields, which is especially useful when auditability or traceability matters.

Not every BCDM field has a Darwin Core equivalent, and not every forensic field maps cleanly into non-forensic exchange standards. Where no equivalent exists, the BCDM field remains the authoritative representation.

## Frictionless Packaging

The included [package.metadata.template.json](package.metadata.template.json) is intended as a starting point for building a Frictionless Data package descriptor around datasets that use this model. In practice, a published package should describe:

- package identity and version
- contributors and licensing
- one or more resources included in the package
- each resource schema, including field names, types, formats, and descriptions

For forensic exchange scenarios, the package metadata is also the right place to document provenance, responsible parties, and any workflow-specific notes that are broader than a single record.

## Validation and Conversion Tools

The repository includes Python utilities that operate on JSONL streams and support a typical submission pipeline:

1. [tools/validation/1_acceptability_check.py](tools/validation/1_acceptability_check.py) checks required fields, removes unsupported fields, and validates basic data type and format rules against [field_definitions.tsv](field_definitions.tsv).
2. [tools/validation/2_validate.py](tools/validation/2_validate.py) validates submitted values against controlled vocabularies and external registry files.
3. [tools/conversion/3_convert_BCDM_to_DB.py](tools/conversion/3_convert_BCDM_to_DB.py) converts validated BCDM submission objects into an intermediate BOLD-style database structure.
4. [tools/conversion/4_convert_to_verbatim.py](tools/conversion/4_convert_to_verbatim.py) adds or replaces normalized fields with verbatim fields using [mapping_verbatim_to_BOLD.tsv](mapping_verbatim_to_BOLD.tsv).
5. [tools/conversion/5_prep_for_db_load.py](tools/conversion/5_prep_for_db_load.py) resolves selected lookups and groups fields into table-level payloads ready for database loading.
6. [tools/conversion/convert_DB_to_BCDM.py](tools/conversion/convert_DB_to_BCDM.py) remaps exported database keys back into BCDM field names.

Example test inputs and sample commands are included under [tools/test_data](tools/test_data) and documented in [tools/test_data/Readme.MD](tools/test_data/Readme.MD).

## Getting Started

Install the Python dependencies used by the helper scripts:

```bash
python3 -m pip install -r tools/validation/requirement.txt
python3 -m pip install -r tools/conversion/requirement.txt
```

Run the first-stage acceptability check against the included test data:

```bash
cat tools/test_data/script1_good_data.jsonl | \
python3 tools/validation/1_acceptability_check.py \
  --bcdm-def field_definitions.tsv \
  --reqfields sampleid bold_recordset_code_arr country/ocean phylum inst \
  --atomicity any
```

This command writes accepted JSONL records to `stdout` and validation messages to `stderr`.

From there, records can move through controlled-vocabulary validation and the conversion scripts depending on the target system and submission workflow. Later validation and load-preparation steps expect additional registry files appropriate to the target environment.

## Intended Use

This repository is intended for developers, data managers, and integration teams who need to:

- model forensic barcode records using a shared vocabulary
- validate payloads before ingestion
- map data into BOLD-oriented database structures
- retain both normalized and verbatim values where traceability is important
- exchange records with systems that use BCDM, Darwin Core, or related biodiversity data conventions

## Status

The repository should be treated as the working specification and implementation scaffold for the BCDM forensic extension. The TSV definitions and mappings are the authoritative artifacts in this repository; the helper scripts provide a reference processing pipeline around them.

## License

This repository currently ships with the GNU GPL v3 license text in [LICENSE](LICENSE).
