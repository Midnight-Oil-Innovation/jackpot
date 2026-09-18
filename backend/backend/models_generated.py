from __future__ import annotations
from datetime import datetime, date
from enum import Enum

from decimal import Decimal
from typing import List, Dict, Optional, Any, Union
from pydantic import BaseModel as BaseModel, ConfigDict,  Field, field_validator
import re
import sys
if sys.version_info >= (3, 8):
    from typing import Literal
else:
    from typing_extensions import Literal


metamodel_version = "None"
version = "4.4"

class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra = 'forbid',
        arbitrary_types_allowed=True,
        use_enum_values = True)

    pass



class OrganismNameEnum(str, Enum):
    """
    Controlled vocabulary of pathogen organism names. Derived from a configurable reportable communicable diseases list (defaults to the host jurisdiction's official list). Anchored to NCBI Taxonomy for BioSample/SRA/GenBank/GISAID compatibility.

    """
    # Use for metagenomic samples with no specific pathogen targeted or identified. NCBI BioSample convention for metagenomics.

    metagenome = "metagenome"
    # Anthrax
    Bacillus_anthracis = "Bacillus anthracis"
    # Pertussis (whooping cough)
    Bordetella_pertussis = "Bordetella pertussis"
    # Relapsing fever — tick-borne (Southwest US)
    Borrelia_hermsii = "Borrelia hermsii"
    # Relapsing fever — tick-borne (Southwest US)
    Borrelia_turicatae = "Borrelia turicatae"
    # Brucellosis — bovine
    Brucella_abortus = "Brucella abortus"
    # Brucellosis — canine
    Brucella_canis = "Brucella canis"
    # Brucellosis — goat/sheep
    Brucella_melitensis = "Brucella melitensis"
    # Brucellosis — swine
    Brucella_suis = "Brucella suis"
    # Glanders
    Burkholderia_mallei = "Burkholderia mallei"
    # Melioidosis
    Burkholderia_pseudomallei = "Burkholderia pseudomallei"
    # Botulism
    Clostridium_botulinum = "Clostridium botulinum"
    # Tetanus
    Clostridium_tetani = "Clostridium tetani"
    # Diphtheria
    Corynebacterium_diphtheriae = "Corynebacterium diphtheriae"
    # Q fever
    Coxiella_burnetii = "Coxiella burnetii"
    # Cronobacter infection (infant)
    Cronobacter_sakazakii = "Cronobacter sakazakii"
    # Shiga toxin-producing E. coli (STEC); hemolytic uremic syndrome. Use serotype field for specific serovar (e.g. O157:H7, O111:H8).

    Escherichia_coli = "Escherichia coli"
    # Tularemia
    Francisella_tularensis = "Francisella tularensis"
    # Chancroid
    Haemophilus_ducreyi = "Haemophilus ducreyi"
    # Invasive Haemophilus influenzae disease
    Haemophilus_influenzae = "Haemophilus influenzae"
    # Leptospirosis
    Leptospira_interrogans = "Leptospira interrogans"
    # Listeriosis
    Listeria_monocytogenes = "Listeria monocytogenes"
    # Hansen's disease (leprosy)
    Mycobacterium_leprae = "Mycobacterium leprae"
    # Tuberculosis — active or latent
    Mycobacterium_tuberculosis = "Mycobacterium tuberculosis"
    # Tuberculosis — bovine-associated
    Mycobacterium_bovis = "Mycobacterium bovis"
    # Gonorrhea
    Neisseria_gonorrhoeae = "Neisseria gonorrhoeae"
    # Invasive meningococcal disease
    Neisseria_meningitidis = "Neisseria meningitidis"
    # Epidemic typhus
    Rickettsia_prowazekii = "Rickettsia prowazekii"
    # Rocky Mountain spotted fever (RMSF)
    Rickettsia_rickettsii = "Rickettsia rickettsii"
    # Murine (endemic) typhus
    Rickettsia_typhi = "Rickettsia typhi"
    # Non-typhoidal Salmonella. Use serotype field for serovar (e.g. Typhimurium, Enteritidis, Newport, Heidelberg).

    Salmonella_enterica = "Salmonella enterica"
    # Typhoid fever (Salmonella enterica serovar Typhi)
    Salmonella_Typhi = "Salmonella Typhi"
    # Toxic shock syndrome; MRSA — use strain field for MRSA/MSSA
    Staphylococcus_aureus = "Staphylococcus aureus"
    # Streptococcal toxic shock syndrome; Group A Streptococcus
    Streptococcus_pyogenes = "Streptococcus pyogenes"
    # Syphilis
    Treponema_pallidum = "Treponema pallidum"
    # Cholera
    Vibrio_cholerae = "Vibrio cholerae"
    # Plague — bubonic, septicemic, or pneumonic
    Yersinia_pestis = "Yersinia pestis"
    # Candida auris — multidrug-resistant fungal pathogen
    Candida_auris = "Candida auris"
    # Valley fever (coccidioidomycosis) — California strain. Optional regional addition; not on the standard reportable list.

    Coccidioides_immitis = "Coccidioides immitis"
    # Valley fever (coccidioidomycosis) — Southwestern US strain. Predominant species in arid regions. Optional regional addition; not on the standard reportable list.

    Coccidioides_posadasii = "Coccidioides posadasii"
    # Chikungunya fever
    Chikungunya_virus = "Chikungunya virus"
    # Crimean-Congo hemorrhagic fever (CCHF)
    Crimean_Congo_hemorrhagic_fever_orthonairovirus = "Crimean-Congo hemorrhagic fever orthonairovirus"
    # Dengue fever. Use serotype field for DENV-1 through DENV-4.

    Dengue_virus = "Dengue virus"
    # Ebola virus disease (viral hemorrhagic fever)
    Ebola_virus = "Ebola virus"
    # Hantavirus pulmonary syndrome (HPS) — unspecified hantavirus. Use Sin Nombre orthohantavirus when species is confirmed.

    Hantavirus = "Hantavirus"
    # HIV infection; HIV-1
    Human_immunodeficiency_virus_1 = "Human immunodeficiency virus 1"
    # HIV infection; HIV-2
    Human_immunodeficiency_virus_2 = "Human immunodeficiency virus 2"
    # Influenza — type A. Use strain field for subtype (H1N1, H3N2, H5N1).

    Influenza_A_virus = "Influenza A virus"
    # Influenza — type B. Use strain field for lineage (Victoria, Yamagata).

    Influenza_B_virus = "Influenza B virus"
    # Lassa fever (viral hemorrhagic fever)
    Lassa_virus = "Lassa virus"
    # Lymphocytic choriomeningitis (LCM)
    Lymphocytic_choriomeningitis_virus = "Lymphocytic choriomeningitis virus"
    # Marburg virus disease (viral hemorrhagic fever)
    Marburg_virus = "Marburg virus"
    # Measles (rubeola)
    Measles_virus = "Measles virus"
    # Middle East respiratory syndrome coronavirus
    MERS_CoV = "MERS-CoV"
    # Mpox (formerly monkeypox). Use strain field for clade (hMPXV Clade I or hMPXV Clade II).

    Mpox_virus = "Mpox virus"
    # Mumps
    Mumps_virus = "Mumps virus"
    # Poliomyelitis. Use serotype field for type (1, 2, 3). Use strain field for wild vs. vaccine-derived.

    Poliovirus = "Poliovirus"
    # Rabies. Use strain field for variant (e.g. bat variant, skunk variant, fox variant).

    Rabies_lyssavirus = "Rabies lyssavirus"
    # RSV — typically included under 'Respiratory disease (outbreak)' on reportable lists. Use strain field for RSV-A or RSV-B.

    Respiratory_syncytial_virus = "Respiratory syncytial virus"
    # Rubella (German measles)
    Rubella_virus = "Rubella virus"
    # Severe acute respiratory syndrome (SARS, 2003)
    SARS_CoV = "SARS-CoV"
    # COVID-19 (novel coronavirus infection). NCBI standard name for SARS-CoV-2. Use pango_lineage field for Pangolin lineage designation.

    Severe_acute_respiratory_syndrome_coronavirus_2 = "Severe acute respiratory syndrome coronavirus 2"
    # Hantavirus pulmonary syndrome — Sin Nombre virus (Southwest US)
    Sin_Nombre_orthohantavirus = "Sin Nombre orthohantavirus"
    # St. Louis encephalitis
    StFULL_STOP_Louis_encephalitis_virus = "St. Louis encephalitis virus"
    # Vaccinia-related adverse event (smallpox vaccine)
    Vaccinia_virus = "Vaccinia virus"
    # Smallpox
    Variola_virus = "Variola virus"
    # Varicella (chickenpox); herpes zoster (shingles)
    Varicella_zoster_virus = "Varicella-zoster virus"
    # West Nile virus disease
    West_Nile_virus = "West Nile virus"
    # Yellow fever
    Yellow_fever_virus = "Yellow fever virus"
    # Zika virus infection
    Zika_virus = "Zika virus"
    # Primary amoebic meningoencephalitis (PAM). Free-living protozoan parasite found in warm freshwater.

    Naegleria_fowleri = "Naegleria fowleri"
    # Taeniasis — beef tapeworm
    Taenia_saginata = "Taenia saginata"
    # Taeniasis and cysticercosis — pork tapeworm
    Taenia_solium = "Taenia solium"
    # Toxoplasmosis; parasitic encephalitis
    Toxoplasma_gondii = "Toxoplasma gondii"
    # Trichinosis
    Trichinella_spiralis = "Trichinella spiralis"
    # Reportable category typically: 'Emerging or exotic disease'. Use when a novel pathogen is identified but has no stable NCBI Taxonomy name yet. Platform Admin assigns permanent name when NCBI Taxonomy provides one.

    novel_pathogen = "novel pathogen"

    Plasmodium_falciparum = "Plasmodium falciparum"

    Plasmodium_vivax = "Plasmodium vivax"

    Plasmodium_malariae = "Plasmodium malariae"

    Plasmodium_ovale_curtisi = "Plasmodium ovale curtisi"

    Plasmodium_ovale_wallikeri = "Plasmodium ovale wallikeri"

    Plasmodium_knowlesi = "Plasmodium knowlesi"

    Leishmania_donovani = "Leishmania donovani"

    Leishmania_major = "Leishmania major"

    Leishmania_infantum = "Leishmania infantum"

    Leishmania_tropica = "Leishmania tropica"

    Leishmania_braziliensis = "Leishmania braziliensis"

    Leishmania_mexicana = "Leishmania mexicana"

    Trypanosoma_cruzi = "Trypanosoma cruzi"

    Trypanosoma_brucei_gambiense = "Trypanosoma brucei gambiense"

    Trypanosoma_brucei_rhodesiense = "Trypanosoma brucei rhodesiense"

    Trypanosoma_congolense = "Trypanosoma congolense"

    Trypanosoma_vivax = "Trypanosoma vivax"

    Schistosoma_mansoni = "Schistosoma mansoni"

    Schistosoma_haematobium = "Schistosoma haematobium"

    Schistosoma_japonicum = "Schistosoma japonicum"

    Schistosoma_mekongi = "Schistosoma mekongi"

    Schistosoma_intercalatum = "Schistosoma intercalatum"

    Ascaris_lumbricoides = "Ascaris lumbricoides"

    Ascaris_suum = "Ascaris suum"

    Trichuris_trichiura = "Trichuris trichiura"

    Necator_americanus = "Necator americanus"

    Ancylostoma_duodenale = "Ancylostoma duodenale"

    Ancylostoma_ceylanicum = "Ancylostoma ceylanicum"

    Strongyloides_stercoralis = "Strongyloides stercoralis"

    Wuchereria_bancrofti = "Wuchereria bancrofti"

    Brugia_malayi = "Brugia malayi"

    Brugia_timori = "Brugia timori"

    Cryptosporidium_parvum = "Cryptosporidium parvum"

    Cryptosporidium_hominis = "Cryptosporidium hominis"

    Cryptosporidium_meleagridis = "Cryptosporidium meleagridis"

    Giardia_intestinalis = "Giardia intestinalis"

    Entamoeba_histolytica = "Entamoeba histolytica"

    Entamoeba_dispar = "Entamoeba dispar"



class SourceTypeEnum(str, Enum):

    # Clinical or surveillance sample from a human host
    Human = "Human"
    # Sample from a wild animal
    Wildlife = "Wildlife"
    # Sample from a pet or companion animal
    CompanionAnimal = "CompanionAnimal"
    # Sample from a farm or agricultural animal
    Livestock = "Livestock"
    # Sample from a disease-transmitting arthropod
    Vector = "Vector"
    # Sample from a wastewater system
    Wastewater = "Wastewater"
    # Sample from a non-wastewater water source
    Water = "Water"
    # Airborne/aerosol sample
    Air = "Air"
    # Sample from a soil matrix
    Soil = "Soil"
    # Surface swab sample
    Surface = "Surface"
    # Sample from a food product
    Food = "Food"
    # Sample from an agricultural crop
    ProduceAg = "ProduceAg"

    Other = "Other"



class ExperimentTypeEnum(str, Enum):

    # Whole genome sequencing
    WGS = "WGS"
    # Whole exome sequencing
    WES = "WES"
    # RNA sequencing
    RNAseq = "RNAseq"
    # Shotgun metagenomic sequencing
    shotgun_DNA_sequencing = "shotgun_DNA_sequencing"
    # Targeted amplicon sequencing (16S, ARTIC, etc.)
    amplicon_sequencing = "amplicon_sequencing"
    # Other targeted sequencing
    targeted_sequencing = "targeted_sequencing"



class CaseTypeEnum(str, Enum):

    # Part of a named outbreak investigation
    outbreak = "outbreak"
    # Genomic or epidemiological cluster, not yet a named outbreak
    cluster = "cluster"
    # Single case with no known epidemiological links
    sporadic = "sporadic"
    # Routine surveillance — no specific case being investigated
    surveillance = "surveillance"
    # Sample collected as part of contact tracing
    contact_investigation = "contact_investigation"
    # Sentinel surveillance site sample
    sentinel = "sentinel"



class SectorEnum(str, Enum):

    # Human clinical diagnosis or treatment context
    clinical = "clinical"
    # Animal health — companion, livestock, or zoo animals
    veterinary = "veterinary"
    # Food production — crops, produce, food processing
    agricultural = "agricultural"
    # Environmental monitoring — water, soil, air, surfaces
    environmental = "environmental"
    # Community-level wastewater surveillance (NWSS)
    wastewater = "wastewater"
    # Wild animal surveillance
    wildlife = "wildlife"
    # Research sample not part of active public health surveillance
    research = "research"



class SurveillanceOverrideCategoryEnum(str, Enum):

    # Reportable organism present but sample is outside surveillance scope. Requires governance board approval (TRUE → FALSE override).
    reportable_organism_exception = "reportable_organism_exception"
    # Untargeted metagenome conservatively flagged TRUE, but sample is confirmed research-only with no surveillance purpose. Lab Director self-approval permitted.
    untargeted_metagenome_research = "untargeted_metagenome_research"
    # Non-reportable organism or research sample voluntarily brought under surveillance oversight (FALSE → TRUE override). No approval required.
    voluntary_opt_in = "voluntary_opt_in"



class QualityStatusEnum(str, Enum):

    # Tier 1 — minimum viable metadata present. Sample is immediately ingested and available for pipeline runs and basic search. May lack date precision, geographic detail, or source-type fields.
    PRELIMINARY = "PRELIMINARY"
    # Tier 2 — sufficient metadata for epidemiological analysis including time-series (date to at least month precision) and geographic aggregation. Eligible for MMWR epiweek computation.
    ANALYZABLE = "ANALYZABLE"
    # Tier 3 — meets full NCBI BioSample, GISAID, and NWSS requirements. All required fields present, dates to full ISO 8601 day precision, all source-type-specific fields populated. Automated submission workflows enabled.
    SUBMITTABLE = "SUBMITTABLE"
    # Failed automated or manual QC checks. Retained in the system for audit purposes but excluded from analyses and not shown in the catalog by default.
    QC_FAILED = "QC_FAILED"
    # Flagged for human review — automated QC result is inconclusive. Excluded from analyses pending review outcome.
    UNDER_REVIEW = "UNDER_REVIEW"
    # Previously released data that has been withdrawn by the submitting lab or Platform Admin. Not shown in catalog; audit record preserved.
    RETRACTED = "RETRACTED"



class DatePrecisionEnum(str, Enum):

    # Full ISO 8601 date known (YYYY-MM-DD). Default when date is entered in full. Required for Tier 3 (SUBMITTABLE) quality status.
    day = "day"
    # Only year and month known. Store date_collected as YYYY-MM-01. Epiweek computation uses mid-month estimate with warning. Sufficient for Tier 2 (ANALYZABLE) monthly aggregation.
    month = "month"
    # Only year known. Store date_collected as YYYY-01-01. Epiweek computation suppressed. Sufficient for Tier 1 (PRELIMINARY) annual surveillance counts.
    year = "year"



class ReadTypeEnum(str, Enum):

    # Illumina or Ion Torrent — reads <1000bp
    short_read = "short_read"
    # ONT or PacBio — reads >1000bp, typically 10–100kb
    long_read = "long_read"
    # Combined short and long read data for the same sample. Used for hybrid assembly pipelines (e.g. Unicycler, Dragonflye).
    hybrid = "hybrid"
    # ONT ultra-long reads >100kb — used for complete chromosome assembly
    ultra_long = "ultra_long"



class AssemblyTypeEnum(str, Enum):

    # Single organism isolate — standard WGS assembly from pure culture. Coverage depth and genome completeness QC apply.
    isolate = "isolate"
    # Metagenome-assembled genome — binned from metagenomic data. CheckM2 completeness and contamination QC apply instead of coverage/VADR metrics.
    mag = "mag"
    # Single-amplified genome — from single-cell genomics. Lower completeness expected; CheckM2 QC applies.
    sag = "sag"
    # Amplicon or reference-guided consensus genome (e.g. SARS-CoV-2 ARTIC protocol). VADR and Nextclade QC apply.
    consensus = "consensus"
    # RNA-based metagenomic assembly — transcriptome from community.
    metatranscriptome = "metatranscriptome"



class DataUseTermsEnum(str, Enum):

    # No restrictions — submitter does not retain rights. Data may be freely used, shared, and republished with attribution.
    open_access = "open_access"
    # Access subject to a Data Use Agreement (DUA). Submitter protections apply. Users must agree to DUA terms before accessing data.
    controlled_access = "controlled_access"
    # Internal use only — not for external sharing. Overrides sharing_level for external requests.
    restricted = "restricted"
    # Under publication embargo. Data is accessible internally but embargo_release_date controls when external access is permitted.
    embargo = "embargo"



class SharingLevelEnum(str, Enum):

    # Owner and Lab Director only
    PRIVATE = "PRIVATE"
    # All members of the owning Lab
    LAB = "LAB"
    # Metadata visible to all authenticated users; files require an access request
    DISCOVERABLE = "DISCOVERABLE"
    # Data available to any researcher who registers and agrees to the data use agreement (DUA). More open than DISCOVERABLE (no per-request approval), more controlled than PUBLIC (requires identity verification and DUA acceptance). Compatible with GA4GH Passport-controlled access. Appropriate for: multi-institution data sharing agreements, CDC/WHO federated surveillance networks, international genomics consortia. Access gate: authenticated user + accepted DUA. No Lab Director approval required per-request, but terms must be accepted once.
    REGISTERED_ACCESS = "REGISTERED_ACCESS"
    # Metadata and files open to all authenticated users
    PUBLIC = "PUBLIC"



class ScrubStatusEnum(str, Enum):


    PENDING = "PENDING"

    IN_PROGRESS = "IN_PROGRESS"

    COMPLETE = "COMPLETE"

    FAILED = "FAILED"
    # Non-human sample; scrubber not applicable
    SKIPPED = "SKIPPED"



class PIIScanStatusEnum(str, Enum):


    PENDING = "PENDING"

    COMPLETE = "COMPLETE"

    PII_DETECTED = "PII_DETECTED"

    FAILED = "FAILED"
    # Flagged for PII, then released by a Lab Director holding sample:pii_override. Distinct from COMPLETE, which means the scan found nothing
    OVERRIDDEN = "OVERRIDDEN"



class VADRStatusEnum(str, Enum):

    # Passes VADR — eligible for NCBI submission
    PASS = "PASS"
    # Fails VADR — review alerts before submitting
    FAIL = "FAIL"
    # Not applicable (non-viral or short amplicon)
    SKIP = "SKIP"
    # VADR not yet run
    PENDING = "PENDING"



class SubmissionStatusEnum(str, Enum):


    NOT_SUBMITTED = "NOT_SUBMITTED"

    PENDING = "PENDING"

    SUBMITTED = "SUBMITTED"

    ACCEPTED = "ACCEPTED"

    FAILED = "FAILED"

    WITHDRAWN = "WITHDRAWN"



class IngestMethodEnum(str, Enum):


    gui = "gui"

    csv = "csv"

    rsync = "rsync"

    curl = "curl"

    globus = "globus"



class ProjectStatusEnum(str, Enum):


    ACTIVE = "ACTIVE"

    ARCHIVED = "ARCHIVED"



class SequencingPlatformEnum(str, Enum):


    Illumina = "Illumina"

    Oxford_Nanopore = "Oxford_Nanopore"

    PacBio = "PacBio"

    Ion_Torrent = "Ion_Torrent"

    Other = "Other"



class LibraryLayoutEnum(str, Enum):


    PAIRED = "PAIRED"

    SINGLE = "SINGLE"



class BiologicalSexEnum(str, Enum):


    Male = "Male"

    Female = "Female"
    # DSD
    Differences_of_Sex_Development = "Differences_of_Sex_Development"

    unknown = "unknown"



class AgeUnitEnum(str, Enum):


    years = "years"

    months = "months"

    days = "days"



class BiospecimenTypeEnum(str, Enum):


    nasopharyngeal_swab = "nasopharyngeal_swab"

    oropharyngeal_swab = "oropharyngeal_swab"

    saliva = "saliva"

    blood = "blood"

    serum = "serum"

    plasma = "plasma"

    urine = "urine"

    stool = "stool"

    skin_biopsy = "skin_biopsy"

    tissue_biopsy = "tissue_biopsy"

    bronchoalveolar_lavage = "bronchoalveolar_lavage"

    lung_tissue = "lung_tissue"
    # For avian samples
    cloacal_swab = "cloacal_swab"

    feather = "feather"
    # For vectors — whole arthropod homogenate
    homogenized = "homogenized"
    # For vectors — saliva/excreta
    non_destructive_extraction = "non_destructive_extraction"

    other = "other"



class ReasonForCollectionEnum(str, Enum):

    # Obtained during clinical care
    clinical = "clinical"
    # Collected as part of a research study
    research = "research"
    # Collected as part of public health surveillance
    surveillance = "surveillance"



class VaccineStatusEnum(str, Enum):


    never_vaccinated = "never_vaccinated"

    current = "current"

    overdue = "overdue"

    unknown = "unknown"



class SymptomaticEnum(str, Enum):


    true = "True"

    false = "False"

    uncertain = "uncertain"



class CompanionAnimalLocationEnum(str, Enum):


    residence_indoor = "residence_indoor"

    residence_outdoor_enclosure = "residence_outdoor_enclosure"

    shelter = "shelter"

    roaming = "roaming"

    other = "other"



class LivestockLocationEnum(str, Enum):

    # Concentrated Animal Feeding Operation
    CAFO = "CAFO"

    open_pasture = "open_pasture"

    broiler_house = "broiler_house"

    hoop_barn = "hoop_barn"

    free_range = "free_range"

    feedlot = "feedlot"

    other = "other"



class LivestockProductEnum(str, Enum):


    meat = "meat"

    dairy = "dairy"

    eggs = "eggs"

    textile_fibers = "textile_fibers"

    other = "other"



class AntibioticUseEnum(str, Enum):


    current = "current"

    recent = "recent"

    never = "never"

    unknown = "unknown"



class VectorBiospecimenTypeEnum(str, Enum):

    # Whole arthropod homogenate — single specimen
    homogenized = "homogenized"
    # Multiple arthropods homogenized together as a surveillance pool (e.g. mosquito pool). Record number of individuals in pool_size_min/pool_size_max.
    pooled_homogenate = "pooled_homogenate"
    # Saliva/excreta without destroying specimen
    non_destructive_extraction = "non_destructive_extraction"

    other = "other"



class WastewaterSampleTypeEnum(str, Enum):


    grab = "grab"

    composite_24hr_flow_weighted = "composite_24hr_flow_weighted"

    composite_24hr_time_weighted = "composite_24hr_time_weighted"

    other = "other"



class SampleMatrixEnum(str, Enum):


    raw_wastewater = "raw_wastewater"

    post_grit_removal = "post_grit_removal"

    primary_sludge = "primary_sludge"

    primary_effluent = "primary_effluent"

    secondary_sludge = "secondary_sludge"

    secondary_effluent = "secondary_effluent"

    septage = "septage"

    holding_tank = "holding_tank"



class PretreatmentEnum(str, Enum):


    none = "none"

    chlorine = "chlorine"

    ozone = "ozone"

    UV = "UV"

    other = "other"



class ConcentrationMethodEnum(str, Enum):


    none = "none"

    ceres_nanotrap = "ceres_nanotrap"

    membrane_filtration_MgCl2 = "membrane_filtration_MgCl2"

    ultrafiltration = "ultrafiltration"

    polyethylene_glycol_precipitation = "polyethylene_glycol_precipitation"

    ultracentrifugation = "ultracentrifugation"

    other = "other"



class WaterSourceEnum(str, Enum):


    municipal_tap = "municipal_tap"

    irrigation_line = "irrigation_line"

    pond = "pond"

    lake = "lake"

    stream = "stream"

    canal = "canal"

    desert_wash = "desert_wash"

    glacier = "glacier"

    groundwater = "groundwater"

    reclaimed_water = "reclaimed_water"

    other = "other"



class AirSourceEnum(str, Enum):


    cooling_tower = "cooling_tower"

    internal_vent = "internal_vent"

    urban = "urban"

    plane = "plane"

    hospital_room = "hospital_room"

    HEPA_exhaust = "HEPA_exhaust"

    other = "other"



class FoodLocationTypeEnum(str, Enum):


    residence = "residence"

    store = "store"

    in_transit = "in_transit"

    warehouse = "warehouse"

    manufacturing_plant = "manufacturing_plant"

    restaurant = "restaurant"

    other = "other"



class FoodProductTypeEnum(str, Enum):


    fresh_produce = "fresh_produce"

    meat = "meat"

    poultry = "poultry"

    seafood = "seafood"

    dairy_products = "dairy_products"

    eggs = "eggs"

    processed_foods = "processed_foods"

    deli_meats = "deli_meats"

    grains = "grains"

    other = "other"



class ProduceWaterSourceEnum(str, Enum):


    irrigation_lines = "irrigation_lines"

    reclaimed_water = "reclaimed_water"

    freshwater = "freshwater"

    municipal = "municipal"

    rainwater = "rainwater"

    other = "other"



class FertilizerTypeEnum(str, Enum):


    organic = "organic"

    inorganic = "inorganic"

    compost = "compost"

    manure = "manure"

    none = "none"



class DistributionScaleEnum(str, Enum):


    local = "local"

    county = "county"

    state = "state"

    national = "national"

    global_export = "global_export"



class SampleAssociationTypeEnum(str, Enum):

    # Both samples from same household
    same_household = "same_household"
    # Both samples from same outbreak cluster
    same_outbreak = "same_outbreak"
    # Vector sample and its host sample
    host_vector = "host_vector"
    # Human sample and companion animal sample
    human_pet = "human_pet"
    # Food sample linked to clinical case
    food_source_clinical = "food_source_clinical"
    # Environmental sample linked to human case
    environmental_clinical = "environmental_clinical"
    # Serial samples from the same host over time
    longitudinal = "longitudinal"
    # Source sample is upstream of the target sample in the sewershed (directional; B-CWB-SCHEMA-2)
    wastewater_upstream_of = "wastewater_upstream_of"

    other = "other"



class SampleFileTypeEnum(str, Enum):
    """
    File type for sample_files table. Derived from file extension.
    """
    # .fastq or .fq (with optional .gz or .bz2 compression)
    FASTQ = "FASTQ"
    # .fasta, .fa, or .fna (with optional .gz compression)
    FASTA = "FASTA"
    # Any file type not covered by FASTQ or FASTA
    OTHER = "OTHER"



class SampleFileLayoutEnum(str, Enum):
    """
    Read layout for an individual file in sample_files. Distinct from the sample-level library_layout field.

    """
    # This file is one of a paired-end pair. The partner file is identified by paired_file_id.

    PAIRED = "PAIRED"
    # This file was expected to be part of a pair but no partner was found. Treated as unpaired by downstream tools.

    SINGLE = "SINGLE"
    # Genuinely single-end read or a nanopore/multi-file chunk. Not expected to have a partner.

    UNPAIRED = "UNPAIRED"



class ReadDirectionEnum(str, Enum):
    """
    Read direction for paired-end files.
    """
    # Forward read. Detected from: _R1, _1, _reads_1, _forward naming conventions (case-insensitive).

    R1 = "R1"
    # Reverse read. Detected from: _R2, _2, _reads_2, _reverse naming conventions (case-insensitive).

    R2 = "R2"



class FileStorageState(str, Enum):
    """
    Lifecycle ownership of a file referenced by sample_files. Determines whether JACKPOT controls the bytes (MANAGED, STAGED), references them in place (EXTERNAL), keeps a managed copy alongside an external original (MIRRORED), or has lost access (BROKEN). Default for ingest is EXTERNAL — JACKPOT does not copy bytes on registration. See Critical Rule 57.

    """
    # URI is not under JACKPOT storage control; JACKPOT references the file in place and never copies or deletes it. Default for ingest.

    EXTERNAL = "EXTERNAL"
    # File lives in JACKPOT-controlled storage. JACKPOT owns the full lifecycle including retention enforcement and deletion.

    MANAGED = "MANAGED"
    # JACKPOT-owned managed copy backed by an external original. Both copies exist; original_uri identifies the external source.

    MIRRORED = "MIRRORED"
    # Temporary copy made for a specific pipeline run. Cleaned up by the staging-cleanup job after the run completes plus a retention window. staged_for_run_id identifies the owning run.

    STAGED = "STAGED"
    # External file is no longer accessible (404, permission denied, host unreachable). Terminal state — the row is retained for audit but the bytes cannot be read.

    BROKEN = "BROKEN"



class AgeRangeEnum(str, Enum):
    """
    Age expressed as a decade bracket for privacy-preserving surveillance reporting. Populated automatically from host_age at ingest. Standard CDC/NNDSS/ArboNET age grouping.
    """
    # Infant — less than 12 months
    LESS_THAN_SIGN_1_year = "< 1 year"
    # Toddler/preschool
    number_1_4_years = "1-4 years"
    # School age
    number_5_14_years = "5-14 years"
    # Young adult
    number_15_24_years = "15-24 years"

    number_25_34_years = "25-34 years"

    number_35_44_years = "35-44 years"

    number_45_54_years = "45-54 years"

    number_55_64_years = "55-64 years"

    number_65_74_years = "65-74 years"

    number_75_84_years = "75-84 years"
    # Oldest old — highest risk for many pathogens
    number_85PLUS_SIGN_years = "85+ years"

    unknown = "unknown"



class CollectionMethodEnum(str, Enum):
    """
    Method used to collect the biological specimen. Standard PHA4GE and NCBI BioSample field. Required for Tier 2 and above.
    """
    # NP swab — gold standard for respiratory pathogens
    nasopharyngeal_swab = "nasopharyngeal_swab"
    # Anterior nares / mid-turbinate swab
    nasal_swab = "nasal_swab"
    # Throat swab
    oropharyngeal_swab = "oropharyngeal_swab"
    # Saliva collection — lower sensitivity than NP for some pathogens
    saliva = "saliva"
    # BAL fluid — lower respiratory tract
    bronchoalveolar_lavage = "bronchoalveolar_lavage"
    # Standard for TB and other lower respiratory pathogens
    induced_sputum = "induced_sputum"
    # Used for TB in children who cannot produce sputum
    gastric_aspirate = "gastric_aspirate"
    # Venipuncture blood draw
    blood = "blood"
    # Serum separated from whole blood
    serum = "serum"
    # Cerebrospinal fluid — lumbar puncture
    csf = "csf"
    # Urine culture or PCR
    urine = "urine"
    # Stool sample — GI pathogens, polio surveillance
    stool = "stool"
    # Alternative to stool for GI pathogens
    rectal_swab = "rectal_swab"
    # Swab of lesion — mpox, herpes, other dermotropic pathogens
    skin_lesion_swab = "skin_lesion_swab"
    # Fluid from skin vesicle — mpox, varicella
    vesicle_fluid = "vesicle_fluid"
    # Wound or abscess swab
    wound_swab = "wound_swab"
    # Tissue biopsy — post-mortem or surgical
    tissue_biopsy = "tissue_biopsy"
    # Non-clinical environmental surface swab
    environmental_swab = "environmental_swab"
    # Collection method not listed — describe in comments
    other = "other"



class PangoQCStatusEnum(str, Enum):
    """
    Pangolin lineage assignment QC status. Surveillance decisions should not be made on 'fail' or 'ambiguous' calls without manual review.
    """
    # High confidence lineage assignment
    pass_qc = "pass_qc"
    # Low confidence — do not use for surveillance without review
    fail = "fail"
    # Multiple equally valid lineage calls — pango_conflict > 0
    ambiguous = "ambiguous"
    # Pangolin not yet run or not applicable (non-SARS-CoV-2)
    not_run = "not_run"



class MLSTConfidenceEnum(str, Enum):
    """
    Confidence level of the MLST sequence type assignment. Distinguishes confident surveillance-grade calls from uncertain ones.
    """
    # All alleles matched exactly — high confidence ST call
    perfect = "perfect"
    # All alleles matched but one or more may be novel alleles
    good = "good"
    # One or more alleles missing or novel — uncertain ST
    low = "low"
    # Insufficient data for MLST — not applicable or failed
    unknown = "unknown"



class OutbreakStatusEnum(str, Enum):

    # Investigation ongoing — new cases still being identified
    active = "active"
    # No new cases for ≥2 incubation periods — pending formal closure
    contained = "contained"
    # Formally closed — investigation_close_date populated
    closed = "closed"
    # Cluster resolved; enhanced surveillance continues
    surveillance_only = "surveillance_only"



class ExecutorTypeEnum(str, Enum):
    """
    Which Nextflow executor a profile drives. LOCAL runs Nextflow against the API host; the remaining values map to the well-known Nextflow executor names. See Critical Rule 59.
    """
    # Nextflow runs in-process on the API host.
    LOCAL = "LOCAL"
    # Nextflow submits jobs to a Slurm cluster.
    SLURM = "SLURM"
    # Nextflow submits jobs to PBS / OpenPBS / Torque.
    PBS = "PBS"
    # Nextflow submits jobs to IBM Spectrum LSF.
    LSF = "LSF"
    # Nextflow submits jobs to Google Cloud Batch.
    GCP_BATCH = "GCP_BATCH"
    # Nextflow submits jobs to AWS Batch.
    AWS_BATCH = "AWS_BATCH"
    # Nextflow submits jobs to a Kubernetes cluster.
    KUBERNETES = "KUBERNETES"



class ContainerEngineEnum(str, Enum):
    """
    Container runtime used to materialize pipeline processes for a profile. APPTAINER and SINGULARITY are listed separately because their CLI flags and Nextflow configuration differ; choose APPTAINER on modern HPC systems and SINGULARITY only when the operator's site has not migrated. NONE means processes run as native binaries on the host.
    """
    # Docker engine — typical for laptops and cloud.
    DOCKER = "DOCKER"
    # Apptainer — typical for modern HPC clusters.
    APPTAINER = "APPTAINER"
    # SingularityCE — legacy HPC sites.
    SINGULARITY = "SINGULARITY"
    # No container — processes run as native binaries.
    NONE = "NONE"



class DeletionStatusEnum(str, Enum):


    ACTIVE = "ACTIVE"

    DELETION_REQUESTED = "DELETION_REQUESTED"

    TOMBSTONED = "TOMBSTONED"

    VACUUMED = "VACUUMED"



class PipelineEngineEnum(str, Enum):


    nextflow = "nextflow"

    snakemake = "snakemake"

    wdl = "wdl"

    manifest = "manifest"



class PipelineSourceTypeEnum(str, Enum):


    git = "git"

    git_private = "git_private"

    tarball = "tarball"

    docker = "docker"



class PipelineStatusEnum(str, Enum):


    SUBMITTED = "SUBMITTED"

    VALIDATING = "VALIDATING"

    SANDBOX_PENDING = "SANDBOX_PENDING"

    SANDBOX_RUNNING = "SANDBOX_RUNNING"

    ACTIVE = "ACTIVE"

    DEACTIVATED = "DEACTIVATED"

    ARCHIVED = "ARCHIVED"

    VALIDATION_FAILED = "VALIDATION_FAILED"

    SANDBOX_FAILED = "SANDBOX_FAILED"

    SANDBOX_TIMEOUT = "SANDBOX_TIMEOUT"



class DataTypeEnum(str, Enum):


    paired_end_short_read = "paired_end_short_read"

    single_end_short_read = "single_end_short_read"

    long_read = "long_read"

    assembly = "assembly"

    raw_signal = "raw_signal"

    metagenomic = "metagenomic"



class ParasiteDevelopmentalStageEnum(str, Enum):


    ring = "ring"

    trophozoite = "trophozoite"

    schizont = "schizont"

    gametocyte = "gametocyte"

    sporozoite = "sporozoite"

    merozoite = "merozoite"

    cyst = "cyst"

    trophozoite_amoebic = "trophozoite_amoebic"

    egg = "egg"

    miracidium = "miracidium"

    cercaria = "cercaria"

    adult = "adult"

    larva_l1 = "larva_l1"

    larva_l2 = "larva_l2"

    larva_l3 = "larva_l3"

    microfilaria = "microfilaria"

    bradyzoite = "bradyzoite"

    tachyzoite = "tachyzoite"



class SamplePreservationMethodEnum(str, Enum):


    fresh = "fresh"

    frozen_minus_20 = "frozen_minus_20"

    frozen_minus_80 = "frozen_minus_80"

    ethanol_70 = "ethanol_70"

    ethanol_95 = "ethanol_95"

    rnalater = "rnalater"

    whatman_card = "whatman_card"

    dried_blood_spot = "dried_blood_spot"

    formalin_fixed_paraffin_embedded = "formalin_fixed_paraffin_embedded"

    nucleic_acid_only = "nucleic_acid_only"



class Organization(ConfiguredBaseModel):

    display_name: str = Field(...)
    default_approve_analytical_dataset_requests: Optional[bool] = Field(None, description="""Auto-approve dataset access requests from this org""")



class Lab(ConfiguredBaseModel):
    """
    A research lab or operational unit within an Organization.
    """
    display_name: str = Field(...)
    organization: str = Field(...)
    description: Optional[str] = Field(None)



class Project(ConfiguredBaseModel):
    """
    A specific study or surveillance effort within a Lab.
    """
    display_name: str = Field(...)
    lab: str = Field(...)
    pathogen_scope: Optional[List[str]] = Field(default_factory=list)
    status: Optional[ProjectStatusEnum] = Field(None)



class Sample(ConfiguredBaseModel):
    """
    Base class for all sequenced samples. Pathogen-agnostic. Every URI maps to GenEpiO, NCBI BioSample, MIxS, or OBI where a standard term exists.

    """
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class HumanSample(Sample):
    """
    Clinical or surveillance sample from a human host. Maps to GA4GH Phenopacket Individual + Disease elements.

    """
    external_case_id: str = Field(..., description="""Operator-issued anonymized identifier or exemption code for a human sample. Either (1) an anonymized ID linking to the host jurisdiction's case-management system, or (2) an exemption code obtained for the study if the sample does not originate from surveillance. Validation: cross-checked against the operator's authoritative ID list when that list becomes available. Currently free text. Distinct from case_id (used by samples whose case identifier comes from a different surveillance system).
""")
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    reason_for_collection: List[ReasonForCollectionEnum] = Field(default_factory=list, description="""Whether sample was obtained during clinical care or research study.
""")
    host_sex: Optional[BiologicalSexEnum] = Field(None)
    host_age: Optional[int] = Field(None, description="""Validation: integer, range [0, 120]. Unit: years.
""")
    host_age_unit: Optional[AgeUnitEnum] = Field(None, description="""Unit for host_age when age < 1 year""")
    host_species: Optional[str] = Field(None, description="""Auto-populated as 'Homo sapiens' for HumanSample. Not user-entered.
""")
    host_disease: List[str] = Field(default_factory=list, description="""not the host is symptomatic). Match defined allowable entries.
""")
    isolation_source: Optional[str] = Field(None, description="""Auto-populated as 'human clinical specimen' for HumanSample.
""")
    vaccination_status: Optional[str] = Field(None, description="""e.g. fully vaccinated, unvaccinated, boosted, partially vaccinated, unknown.
""")
    clinical_outcome: Optional[str] = Field(None, description="""e.g. hospitalized, ICU, deceased, outpatient, asymptomatic, unknown.
""")
    underlying_conditions: Optional[List[str]] = Field(default_factory=list, description="""Relevant comorbidities, e.g. diabetes, immunocompromised, chronic lung disease, obesity.
""")
    date_of_symptom_onset: Optional[date] = Field(None, description="""Date the patient first experienced symptoms of the disease. Standard field on WHO case investigation forms, NNDSS reports, and ArboNET surveillance. Distinct from date_collected (when the sample was taken). The lag between these dates drives incubation period estimates and time-to-detection metrics. ISO 8601 format. Optional — not all cases are symptomatic (asymptomatic cases may have no onset date).""")
    travel_history_country: Optional[List[str]] = Field(default_factory=list, description="""Countries visited by the patient in the 14 days before symptom onset or sample collection (whichever is earlier). NCBI BioSample standard field. WHO situation reports routinely distinguish travel-linked from locally-acquired cases for internationally relevant pathogens (MPOX, Ebola, cholera, H5N1, MERS-CoV). Free text — INSDC country names preferred but not enforced here. Multiple values permitted (multiple countries in travel history).""")
    travel_history_days: Optional[int] = Field(None, description="""Days since return from travel when sample was collected. Used alongside travel_history_country to calculate exposure window. Integer. Optional — only populated when travel_history_country is provided.""")
    host_age_range: Optional[AgeRangeEnum] = Field(None, description="""Age of the human host expressed as a decade bracket for privacy-preserving public surveillance reporting. NNDSS, ArboNET, and CDC public surveillance datasets use age brackets rather than exact ages. host_age (exact integer) is retained for internal analysis; host_age_range is the shareable tier. Populated automatically from host_age at ingest. Reviewers and external users see age range; Lab Directors and above see both.""")
    collection_method: Optional[CollectionMethodEnum] = Field(None, description="""Method used to collect the specimen. Different collection methods for the same biospecimen type have different sensitivity profiles (e.g. nasopharyngeal swab vs. saliva vs. mid-turbinate swab for SARS-CoV-2; induced sputum vs. BAL fluid vs. gastric aspirate for TB). Standard PHA4GE and NCBI BioSample field. Required for Tier 2 (ANALYZABLE) and above. Maps to NCBI collection_method attribute.""")
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class WildlifeSample(Sample):
    """
    Sample from a wild animal host.

    """
    host_species: str = Field(..., description="""genus only acceptable. Match defined allowable entries. Examples: Eptesicus fuscus, Canis latrans, Odocoileus virginianus.
""")
    wildlife_subject_id: Optional[str] = Field(None, description="""Optional alphanumeric field identifier for the animal""")
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    host_disease: List[str] = Field(default_factory=list)
    isolation_source: Optional[str] = Field(None, description="""Auto-derived from host species + biospecimen type""")
    isolate: Optional[str] = Field(None)
    travel_origin_region: Optional[str] = Field(None, description="""For migratory or translocated wildlife — the geographic region of origin or most recent stopover before the animal was sampled. Equivalent to travel_history for humans. Particularly relevant for migratory bird HPAI (H5N1) surveillance where flyway routes determine exposure risk. Free text. Examples: 'Atlantic Flyway', 'East Asia Pacific Flyway', 'Mongolia', 'Central Valley CA'.""")
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class CompanionAnimalSample(Sample):
    """
    Sample from a companion (pet) animal host.

    """
    host_species: str = Field(..., description="""Examples: felis catus, canis familiaris.
""")
    companion_subject_id: Optional[str] = Field(None, description="""Optional alphanumeric field identifier for the animal""")
    location_type: Optional[CompanionAnimalLocationEnum] = Field(None)
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    vaccine_status_against_pathogen: Optional[VaccineStatusEnum] = Field(None)
    host_disease: List[str] = Field(default_factory=list)
    symptomatic: Optional[SymptomaticEnum] = Field(None, description="""Whether animal was symptomatic at time of collection""")
    isolation_source: Optional[str] = Field(None)
    isolate: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class LivestockSample(Sample):
    """
    Sample from a livestock or agricultural animal host.

    """
    host_species: str = Field(..., description="""Examples: Gallus gallus domesticus, Sus domesticus, Lama glama.
""")
    livestock_subject_id: Optional[str] = Field(None, description="""Optional field identifier for the individual animal""")
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    livestock_products: List[LivestockProductEnum] = Field(default_factory=list)
    location_type: Optional[LivestockLocationEnum] = Field(None)
    distribution_scale: Optional[List[DistributionScaleEnum]] = Field(default_factory=list)
    antibiotic_use: Optional[AntibioticUseEnum] = Field(None)
    host_disease: List[str] = Field(default_factory=list)
    isolation_source: Optional[str] = Field(None)
    isolate: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class VectorSample(Sample):
    """
    Sample from a disease vector (arthropod).

    """
    vector_species: str = Field(..., description="""Examples: Aedes aegypti, Culex tarsalis, Rhipicephalus sanguineus, Dermacentor andersoni.
""")
    vector_host_species: Optional[str] = Field(None, description="""Host animal the vector was collected from, if known""")
    biospecimen_type: VectorBiospecimenTypeEnum = Field(...)
    pool_size_min: Optional[int] = Field(None, description="""Minimum number of individual arthropods in this pool. For an exact count, set pool_size_min = pool_size_max. Required when biospecimen_type = pooled_homogenate. Used for Minimum Infection Rate (MIR) calculations. CDC standard pool size is <= 50 arthropods.
""")
    pool_size_max: Optional[int] = Field(None, description="""Maximum number of individual arthropods in this pool. For an exact count, set pool_size_min = pool_size_max. Required when biospecimen_type = pooled_homogenate.
""")
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class EnvironmentalSample(Sample):
    """
    Base class for all environmental samples. Do not instantiate directly — use the specific environmental subclasses below.

    """
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class WastewaterSample(EnvironmentalSample):
    """
    Sample from a wastewater collection or treatment system. mandatory reporting fields. Reference: https://www.cdc.gov/nwss/reporting.html

    """
    wwtp_name: Optional[str] = Field(None, description="""Wastewater facility name or upstream sewer location. Examples: 'Example Water Reclamation Facility', 'undisclosed sewer line upstream of 5th Ave'.
""")
    nwss_sewershed_id: Optional[str] = Field(None, description="""CDC NWSS-assigned identifier for this wastewater sampling site. Links JACKPOT wastewater data to CDC's authoritative sewershed geometry layer (catchment area polygon, population denominator, WWTP capacity). Enables unambiguous matching when JACKPOT data is reported to CDC NWSS. Format: integer or NWSS site code. Reference: https://www.cdc.gov/nwss/reporting.html Optional — not all sites are registered in NWSS at time of sample collection, but should be populated at Tier 2 and above.""")
    sample_location_zipcode: Optional[str] = Field(None, description="""US ZIP code of wastewater sampling location (5-digit)""")
    county_names: Optional[List[str]] = Field(default_factory=list, description="""Counties served by this sampling site, by name or FIPS code. System cross-maps name ↔ FIPS. Multiple entries permitted. Examples: 'Some County', '04013', 'Another County'.
""")
    population_served: int = Field(..., description="""served by this sampling site. Validation: positive integer.
""")
    sample_type: WastewaterSampleTypeEnum = Field(...)
    sample_matrix: SampleMatrixEnum = Field(..., description="""the sample was collected.
""")
    pretreatment: List[PretreatmentEnum] = Field(default_factory=list, description="""Flag if 'none' co-occurs with any other value.
""")
    concentration_method: ConcentrationMethodEnum = Field(...)
    flow_rate_mgd: float = Field(..., description="""Wastewater volumetric flow rate in million gallons per day. Validation: positive float. Unit: MGD.
""")
    sample_collect_time: Optional[str] = Field(None, description="""NWSS: 'sample_collect_time'. Local 24-hr time (HH:MM). For composite samples: start time.
""")
    pcr_target: Optional[str] = Field(None, description="""NWSS: 'pcr_target'. PCR quantification target. e.g. sars-cov-2, influenza-a, mpox, hMPXV Clade I. See NWSS value set vs_pcr_target.
""")
    pcr_gene_target: Optional[str] = Field(None, description="""NWSS: 'pcr_gene_target'. PCR gene for quantification. Must align with pcr_target selection.
""")
    pcr_gene_target_ref: Optional[str] = Field(None, description="""NWSS: Publication or URL for the PCR gene target used""")
    pcr_type: Optional[str] = Field(None, description="""NWSS: 'pcr_type'. Type of PCR used. Non-sars-cov-2/mpox targets must use a digital PCR type.
""")
    quant_stan_type: Optional[str] = Field(None, description="""NWSS: Type of nucleic acid used as quantification standard""")
    stan_ref: Optional[str] = Field(None, description="""NWSS: Publication/description of quantitative standard""")
    lod_ref: Optional[str] = Field(None, description="""NWSS: Publication/description of limit of detection method""")
    inhibition_method: Optional[str] = Field(None, description="""NWSS: Method to evaluate molecular inhibition; 'none' if not tested""")
    num_no_target_control: Optional[int] = Field(None, description="""NWSS: Number of no-template controls (NTC) per instrument run""")
    pasteurized: Optional[bool] = Field(None, description="""NWSS: Was the sample pasteurized?""")
    env_broad_scale: Optional[str] = Field(None, description="""MIxS required. ENVO term. e.g. ENVO:00002001 (wastewater)""")
    env_local_scale: Optional[str] = Field(None, description="""MIxS required. ENVO term. e.g. ENVO:01000621 (municipal WWTP)""")
    env_medium: Optional[str] = Field(None, description="""MIxS required. ENVO term. e.g. ENVO:00002040 (sewage)""")
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class WaterSample(EnvironmentalSample):
    """
    Sample from a non-wastewater water source.

    """
    water_source: Optional[WaterSourceEnum] = Field(None)
    water_temperature_c: float = Field(..., description="""Validation: range [-36, 100]. Unit: °C.
""")
    turbidity_ntu: float = Field(..., description="""Validation: range (0, 4000]; values above 4000 flagged for confirmation (possible decimal point omission). Unit: NTU.
""")
    ph: float = Field(...)
    salinity_ppm: float = Field(...)
    env_broad_scale: Optional[str] = Field(None)
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class AirSample(EnvironmentalSample):
    """
    Airborne/aerosol sample.

    """
    air_source: AirSourceEnum = Field(..., description="""Examples: cooling tower, internal vent, urban, plane.
""")
    airflow_rate_m3_s: float = Field(...)
    pm25_ug_m3: float = Field(...)
    pm10_ug_m3: float = Field(...)
    env_broad_scale: Optional[str] = Field(None)
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class SoilSample(EnvironmentalSample):
    """
    Sample from a soil matrix.

    """
    soil_site_type: str = Field(..., description="""Examples: rodent burrow, construction site, agricultural, CAFO vicinity.
""")
    sample_depth_cm: str = Field(..., description="""Examples: 5, [0, 2], [0, 10]. Validation: positive numeric, single value or range notation.
""")
    nitrogen_mg_kg: Optional[float] = Field(None)
    soil_temperature_c: Optional[float] = Field(None, description="""Validation: range [-36, 100]. Unit: °C.
""")
    moisture_g_g: Optional[float] = Field(None)
    organic_carbon_g_kg: Optional[float] = Field(None)
    soil_ph: Optional[float] = Field(None)
    soil_salinity_ppm: Optional[float] = Field(None)
    env_broad_scale: Optional[str] = Field(None, description="""MIxS required. ENVO term. e.g. ENVO:00001998 (soil), ENVO:00000046 (agricultural soil)
""")
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class SurfaceSample(EnvironmentalSample):
    """
    Surface swab sample (indoor or outdoor). NCBI MIMS.me.built_environment package.

    """
    indoor_space: str = Field(..., description="""Allowable: bedroom, office, bathroom, foyer, kitchen, locker room, hallway, elevator, missing, not applicable, not collected, not provided, restricted access.
""")
    indoor_surface: str = Field(..., description="""Allowable: counter top, window, wall, cabinet, ceiling, door, shelving, vent cover, missing, not applicable, not collected, not provided, restricted access.
""")
    indoor_surface_subpart: Optional[str] = Field(None)
    surface_orientation: Optional[List[str]] = Field(default_factory=list)
    surface_material: List[str] = Field(default_factory=list, description="""Examples: concrete, wood, tile, plastic, glass, stainless steel.
""")
    surface_temperature_c: Optional[float] = Field(None)
    surface_air_contaminants: Optional[List[str]] = Field(default_factory=list, description="""Examples: dust, organic matter, particulate matter, VOCs.
""")
    surface_moisture_qualitative: Optional[str] = Field(None, description="""Values: intermittent moisture, not present, submerged.
""")
    surface_moisture_cm3_cm3: Optional[float] = Field(None)
    surface_moisture_ph: Optional[float] = Field(None)
    surface_humidity_pct: Optional[float] = Field(None)
    wall_surface_treatment: Optional[List[str]] = Field(default_factory=list, description="""e.g. painted, wall paper, no treatment, stucco, fabric.
""")
    wall_texture: Optional[List[str]] = Field(default_factory=list, description="""e.g. smooth, popcorn, orange peel, knockdown, Santa-Fe texture.
""")
    wall_mold_signs: Optional[str] = Field(None, description="""Values: yes, no, unknown.
""")
    env_broad_scale: Optional[str] = Field(None, description="""MIxS required. ENVO term. e.g. ENVO:01000162 (built environment)""")
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class FoodSample(EnvironmentalSample):
    """
    Sample from a food product.

    """
    food_location_type: FoodLocationTypeEnum = Field(...)
    storage_temperature_setting: Optional[str] = Field(None, description="""Examples: freezer, frozen, refrigerator, shelf, room temperature. Validation: numeric OR match defined allowable entries.
""")
    product_temperature_c: Optional[float] = Field(None, description="""Validation: range [-36, 100]. Unit: °C.
""")
    food_product_type: FoodProductTypeEnum = Field(...)
    env_broad_scale: Optional[str] = Field(None)
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class ProduceAgSample(EnvironmentalSample):
    """
    Sample from an agricultural produce crop.

    """
    plant_species: str = Field(..., description="""Examples: Lactuca sativa var. longifolia, Allium cepa.
""")
    distribution_scale: Optional[List[DistributionScaleEnum]] = Field(default_factory=list)
    produce_water_source: List[ProduceWaterSourceEnum] = Field(default_factory=list)
    fertilizer_type: Optional[List[FertilizerTypeEnum]] = Field(default_factory=list)
    near_animal_agriculture: bool = Field(..., description="""Whether crop is downwind/downhill of animal ag operations""")
    washed_before_packing: Optional[bool] = Field(None)
    env_broad_scale: Optional[str] = Field(None)
    env_local_scale: Optional[str] = Field(None)
    env_medium: Optional[str] = Field(None)
    sample_id: str = Field(..., description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""")
    jackpot_uri: Optional[str] = Field(None, description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""")
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(..., description="""is required. Further required fields depend on this value. Validation: match defined allowable entries.
""")
    organism_name: OrganismNameEnum = Field(..., description="""NCBI organism name. Controlled vocabulary derived from the host jurisdiction's reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted.
""")
    strain: Optional[str] = Field(None, description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""")
    isolate: Optional[str] = Field(None, description="""individual from which the sample was obtained.
""")
    serotype: Optional[str] = Field(None, description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""")
    biosample_accession: Optional[str] = Field(None, description="""NCBI BioSample accession (e.g. SAMN12345678)""")
    sra_accession: Optional[str] = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: Optional[str] = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: Optional[str] = Field(None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)""")
    bioproject_accession: Optional[str] = Field(None, description="""NCBI BioProject accession (e.g. PRJNA123456)""")
    type_of_experiment: ExperimentTypeEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    nucleic_acid_extraction_method: List[str] = Field(default_factory=list, description="""Multiple values permitted. Match defined allowable entries.
""")
    library_preparation_method: str = Field(..., description="""Match defined allowable entries (one only).
""")
    sequencing_protocol: str = Field(..., description="""Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""")
    sequencing_platform: SequencingPlatformEnum = Field(..., description="""Validation: match defined allowable entries (one only).
""")
    sequencing_instrument: Optional[str] = Field(None, description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""")
    sequencing_lab: str = Field(..., description="""performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Example Reference Lab', 'Laboratory Corporation of America'. Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal
""")
    date_collected: date = Field(..., description="""Validation: flag if >5 years in past; reject if future date.
""")
    date_sequenced: date = Field(..., description="""Validation: must not be future date; must not precede date_collected.
""")
    collection_facility: str = Field(..., description="""the sample was collected. Match defined allowable entries.
""")
    purpose_for_collection: List[str] = Field(default_factory=list, description="""Multiple selections permitted. Match defined allowable entries.
""")
    collection_location_country: str = Field(..., description="""Country of sample collection. Free text — no controlled vocabulary enforced at Tier 1 or Tier 2. At Tier 3 (SUBMITTABLE), must match an INSDC-approved country name for BioSample submission via TOSTADAS (e.g. \"USA\" not \"United States\", \"United Kingdom\" not \"UK\"). INSDC country list: https://www.insdc.org/submitting-standards/country-qualifier-vocabulary/ portal_to_tostadas.py validates against the INSDC list before constructing the geo_loc_name field (format: Country:State:City).""")
    collection_location_state: Optional[str] = Field(None, description="""Sub-national administrative region of sample collection. Accepts any equivalent administrative division regardless of country: US state, Canadian province, Mexican estado, Australian state, Brazilian estado, UK county/nation, German Bundesland, Japanese prefecture, etc. Free text — not a controlled vocabulary since administrative divisions vary by country. Used in NCBI BioSample geo_loc_name construction (Country:State:City).""")
    collection_location_county: Optional[str] = Field(None, description="""County, district, or equivalent sub-state administrative region of sample collection. US county, UK district, French département, Australian local government area, etc. Free text. Optional — not all countries use a county-level administrative division.""")
    collection_location_zipcode: Optional[str] = Field(None, description="""Postal code of collection location. Format varies by country and is not validated — free text. Examples: US ZIP (85004), UK postcode (SW1A 1AA), Canadian postal code (A1A 1A1), Australian postcode (2000), German Postleitzahl (10115). Optional — many countries do not use postal codes, and postal codes are not used in NCBI BioSample geo_loc_name construction.""")
    collection_location_city: Optional[str] = Field(None, description="""City, town, municipality, or village of sample collection. Free text. Used in NCBI BioSample geo_loc_name construction alongside collection_location_country and collection_location_state: format is \"Country:State:City\" (e.g. \"USA:State:City\"). Optional — omitted from geo_loc_name if not provided.""")
    geo_lat: Optional[float] = Field(None, description="""Decimal latitude (WGS84), e.g. 39.7392""")
    geo_lon: Optional[float] = Field(None, description="""Decimal longitude (WGS84), e.g. -104.9903""")
    mmwr_year: Optional[int] = Field(None, description="""CDC MMWR epiweek year (computed at ingest)""")
    mmwr_week: Optional[int] = Field(None, description="""CDC MMWR week number 1–53 (computed at ingest)""")
    iso_year: Optional[int] = Field(None, description="""ISO 8601 week-based year (computed at ingest)""")
    iso_week: Optional[int] = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    case_id: Optional[str] = Field(None, description="""Generic public health case identifier. Links samples across sectors (human, animal, environmental) that share an epidemiological connection. HumanSample also provides external_case_id for an operator-issued anonymized identifier where the operator has its own case-management system. Other jurisdictions use this generic case_id field: CalREDIE (CA), ECLRS (NY), NEDSS (CDC), etc. Nullable — not all samples belong to a named case.""")
    case_source_system: Optional[str] = Field(None, description="""The surveillance system that issued the case_id. Examples: MEDSIS, CalREDIE, ECLRS, NEDSS, ESSENCE. Free text — not a controlled vocabulary since system names vary by jurisdiction and evolve over time.""")
    case_type: Optional[CaseTypeEnum] = Field(None, description="""Classification of the epidemiological event this sample is associated with. Only meaningful when case_id is populated.""")
    sector: SectorEnum = Field(..., description="""One Health sector classification. Determines surveillance network routing and tiered access control rules. Distinct from source_type which describes the physical sample material.""")
    surveillance_relevant: bool = Field(..., description="""Whether the host operator's public health oversight access applies to this sample. Computed at ingest from organism_name against the reportable_organisms table. TRUE if organism is reportable, FALSE otherwise. For metagenomic samples (organism_name = metagenome): TRUE if any target_organism is reportable, or TRUE by default if no targets specified (conservative). Can be overridden — see surveillance_relevant_override.""")
    surveillance_relevant_override: Optional[bool] = Field(None, description="""TRUE if surveillance_relevant was manually overridden from its organism-driven default. Triggers audit logging. TRUE → FALSE overrides require governance board approval (status tracked via surveillance_override_pending). FALSE → TRUE overrides are self-declared by Lab Director.""")
    surveillance_override_pending: Optional[bool] = Field(None, description="""TRUE when a TRUE → FALSE override has been submitted but not yet approved by the governance board. surveillance_relevant stays TRUE until approval. Cleared when override is approved or denied.""")
    surveillance_override_category: Optional[SurveillanceOverrideCategoryEnum] = Field(None, description="""Classification of the override reason. Determines whether governance board approval is required.""")
    surveillance_override_reason: Optional[str] = Field(None, description="""Required when surveillance_relevant_override is TRUE. Justification for the override, reviewed by governance board for TRUE → FALSE changes.""")
    surveillance_override_approved_by_id: Optional[int] = Field(None, description="""User ID of the governance board member who approved a TRUE → FALSE override. NULL for FALSE → TRUE overrides (no approval required) and for non-overridden samples.""")
    surveillance_override_date: Optional[date] = Field(None, description="""Date the override was approved by the governance board.""")
    target_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list, description="""For metagenomic samples (organism_name = metagenome) — the pathogen(s) the lab is specifically targeting or monitoring for. Used to compute surveillance_relevant when organism_name is 'metagenome'. If empty (untargeted metagenomics), surveillance_relevant defaults to TRUE conservatively. Not applicable to isolate or consensus genome samples.""")
    quality_status: QualityStatusEnum = Field(..., description="""Metadata completeness tier achieved at ingest. Determines which platform features are available for this sample. PRELIMINARY = Tier 1 (ingestible, immediately available for pipeline runs). ANALYZABLE = Tier 2 (eligible for time-series and geographic analyses). SUBMITTABLE = Tier 3 (meets full NCBI/GISAID/NWSS requirements). QC_FAILED = failed QC checks, retained for audit but excluded from analyses. RETRACTED = previously released data withdrawn.""")
    date_collected_precision: Optional[DatePrecisionEnum] = Field(None, description="""Precision of date_collected. When only a year or year-month is known, set this field and store date_collected as YYYY-01-01 or YYYY-MM-01 respectively. Epiweek computation is suppressed when precision is year or month. Displayed to analysts so they understand the resolution of time-series data.""")
    read_type: Optional[ReadTypeEnum] = Field(None, description="""Sequencing read length/technology category. Determines pipeline compatibility and QC expectations. Distinct from sequencing_platform (which captures the instrument make). A hybrid assembly uses both short_read and long_read inputs for the same sample.""")
    assembly_type: Optional[AssemblyTypeEnum] = Field(None, description="""Distinguishes isolate assemblies from metagenome-assembled genomes (MAGs) and other assembly strategies. Drives QC threshold selection and pipeline routing. MAG-specific QC fields (mag_completeness_pct, mag_contamination_pct, etc.) are only meaningful when assembly_type is mag or sag.""")
    mag_completeness_pct: Optional[float] = Field(None, description="""CheckM2 completeness percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_contamination_pct: Optional[float] = Field(None, description="""CheckM2 contamination percentage. Only applicable when assembly_type = mag or sag. Range: [0, 100].""")
    mag_strain_heterogeneity_pct: Optional[float] = Field(None, description="""CheckM2 strain heterogeneity percentage. Indicates within-bin strain diversity. Only applicable when assembly_type = mag.""")
    mag_bin_size_bp: Optional[int] = Field(None, description="""MAG bin size in base pairs. Only applicable when assembly_type = mag.""")
    originating_lab: Optional[str] = Field(None, description="""Lab that collected the original sample. Maps to GISAID \"Originating lab\" and NCBI BioSample originating_lab. Required for WHO Principle 6 attribution. May differ from sequencing_lab (who sequenced it) and submitting_lab (who uploaded to JACKPOT).""")
    submitting_lab: Optional[str] = Field(None, description="""Lab that submitted data to JACKPOT. May differ from originating_lab and sequencing_lab. Required for WHO Principle 6 credit tracking.""")
    data_generator: Optional[str] = Field(None, description="""Individual or organization that generated the sequence data. Used for attribution in publications per WHO Principle 6. Format: \"Name, Institution\" or ORCID URI.""")
    ena_accession: Optional[str] = Field(None, description="""European Nucleotide Archive run accession (ERR prefix). ENA and NCBI SRA mirror each other but submitting labs in Europe and Asia may submit via ENA. Required for WHO Principle 9 interoperability with non-US partners.""")
    data_use_terms: Optional[DataUseTermsEnum] = Field(None, description="""Conditions under which this data may be used, per WHO Principle 8 (\"as open as possible, as closed as necessary\"). Defaults to the organization's policy. Overrides sharing_level for external data use agreements.""")
    embargo_release_date: Optional[date] = Field(None, description="""Date after which data_use_terms = embargo data becomes openly accessible. Only meaningful when data_use_terms = embargo.""")
    citation_request: Optional[str] = Field(None, description="""Free-text citation request from originating lab. Surfaced to data users when they access or download this sample's data. Per WHO Principle 6 — users should invite originating labs to participate in research and publications.""")
    date_received_lab: Optional[date] = Field(None, description="""Date sample received at sequencing lab. Start of the turnaround clock. Rockefeller benchmark: ≤10 days from receipt to consensus genome upload.""")
    date_sequence_uploaded: Optional[date] = Field(None, description="""Date consensus genome uploaded to JACKPOT. Rockefeller target: ≤10 days from date_received_lab.""")
    date_lineage_assigned: Optional[date] = Field(None, description="""Date lineage or sequence type assignment completed (Pangolin, MLST, cgMLST). Rockefeller target: ≤48 hours from date_sequence_uploaded.""")
    date_phenotype_reported: Optional[date] = Field(None, description="""Date phenotypic threat assessment (AMR profile, virulence) reported. Rockefeller target: ≤21 days from date_sequence_uploaded.""")
    associated_sample_ids: Optional[List[str]] = Field(default_factory=list, description="""type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""")
    ct_value: Optional[float] = Field(None, description="""Validation: numeric, range [0, 50].
""")
    other_testing_performed: Optional[List[str]] = Field(default_factory=list, description="""Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""")
    lab_of_other_testing: Optional[List[str]] = Field(default_factory=list, description="""other_testing_performed is not empty or 'none'.
""")
    intermediary_clinical_lab: Optional[str] = Field(None, description="""Match defined allowable entries.
""")
    assembly_method: Optional[str] = Field(None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5""")
    coverage_depth: Optional[float] = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: Optional[float] = Field(None, description="""Percentage of reference genome covered (0–100)""")
    pango_lineage: Optional[str] = Field(None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86""")
    pango_lineage_version: Optional[str] = Field(None, description="""Pangolin software version used for assignment""")
    pango_qc_status: Optional[PangoQCStatusEnum] = Field(None, description="""Pangolin QC status for the lineage call. A 'fail' or 'ambiguous' status means the lineage designation is uncertain and should not drive surveillance decisions without manual review. WHO and CDC both require confidence indicators in genomic surveillance reporting. Populated automatically from Pangolin output at pipeline completion.""")
    pango_conflict: Optional[float] = Field(None, description="""Pangolin conflict score (0.0–1.0). Values >0.0 indicate ambiguity between two or more lineage calls. High conflict (>0.5) indicates the assignment is unreliable. Stored for downstream filtering — surveillance dashboards should suppress or flag high-conflict calls.""")
    nextstrain_clade: Optional[str] = Field(None, description="""Nextstrain clade designation, e.g. 24A""")
    nextclade_qc_score: Optional[float] = Field(None, description="""Nextclade QC score (0–100; higher is better quality)""")
    nextclade_version: Optional[str] = Field(None, description="""Nextclade software version""")
    vadr_status: Optional[VADRStatusEnum] = Field(None, description="""NCBI VADR genome annotation validation result""")
    vadr_alerts: Optional[List[str]] = Field(default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON""")
    mlst_scheme: Optional[str] = Field(None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'""")
    mlst_sequence_type: Optional[str] = Field(None, description="""MLST sequence type, e.g. ST131""")
    mlst_confidence: Optional[MLSTConfidenceEnum] = Field(None, description="""Confidence level of the MLST sequence type assignment. Perfect = all alleles matched exactly. Good = all alleles matched but some may be novel. Low = one or more alleles missing or novel. Unknown = insufficient data. Surveillance reports should distinguish confident from uncertain ST assignments — a novel allele can indicate a genuinely new strain or a sequencing artefact.""")
    amrfinder_genes: Optional[List[str]] = Field(default_factory=list, description="""AMR genes detected by NCBI AMRFinder""")
    card_aro_terms: Optional[List[str]] = Field(default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected""")
    loinc_code: Optional[str] = Field(None, description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""")
    loinc_system: Optional[str] = Field(None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'""")
    snomed_clinical_finding: Optional[str] = Field(None, description="""SNOMED CT clinical finding code, e.g. 840539006""")
    ncbi_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS""")
    ncbi_submitted_at: Optional[datetime ] = Field(None)
    gisaid_submission_status: Optional[SubmissionStatusEnum] = Field(None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status""")
    gisaid_submitted_at: Optional[datetime ] = Field(None)
    fastq_r1_uri: Optional[str] = Field(None, description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and s3:// (S3-compatible) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""")
    fastq_r2_uri: Optional[str] = Field(None, description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""")
    raw_fastq_uri: Optional[str] = Field(None, description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""")
    consensus_fasta_uri: Optional[str] = Field(None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)""")
    assembly_uri: Optional[str] = Field(None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: Optional[str] = Field(None, description="""Validation: must match existing user in the platform.
""")
    grant_number: Optional[str] = Field(None)
    contact_other: Optional[str] = Field(None, description="""Email format. Phase 2: allow non-user contacts.
""")
    comments: Optional[str] = Field(None, description="""Free text comments""")
    deletion_status: Optional[DeletionStatusEnum] = Field(None)
    deletion_requested_at: Optional[str] = Field(None)
    deletion_requested_by_user_id: Optional[str] = Field(None)
    deletion_reason: Optional[str] = Field(None)
    tombstoned_at: Optional[str] = Field(None)
    vacuumed_at: Optional[str] = Field(None)
    parasite_developmental_stage: Optional[ParasiteDevelopmentalStageEnum] = Field(None)
    sample_preservation_method: Optional[SamplePreservationMethodEnum] = Field(None)
    parasitemia_percent: Optional[float] = Field(None)
    multiplicity_of_infection: Optional[int] = Field(None)
    coinfection_organisms: Optional[List[OrganismNameEnum]] = Field(default_factory=list)



class SampleAssociation(ConfiguredBaseModel):
    """
    Links two samples from the same investigation. Derived from 'IDs of any associated samples' field present in ALL Stored as directed pairs in the sample_associations table. Bidirectional: A→B implies B→A but stored as two records.

    """
    source_sample_id: str = Field(...)
    target_sample_id: str = Field(...)
    association_type: Optional[SampleAssociationTypeEnum] = Field(None)
    notes: Optional[str] = Field(None, description="""Free text notes about the association""")



class OutbreakInvestigation(ConfiguredBaseModel):
    """
    A named public health outbreak or cluster investigation. First-class entity that samples link to via outbreak_investigation_id FK in the samples table. Enables querying \"all samples from Outbreak AZ-Salmonella-2026-001\", cross-sector investigation tracking (human + food + environmental samples in the same investigation), and CDC/WHO situation report generation without requiring aggregation from case_type = outbreak on individual sample records.
Maps to: CDC NNDSS OutbreakNumber, WHO Situation Report investigation ID.
    """
    outbreak_id: str = Field(..., description="""Unique identifier for this investigation. Platform-minted on creation. Format: {STATE}-{PATHOGEN_CODE}-{YEAR}-{SEQUENTIAL}, e.g. AZ-SALM-2026-001, AZ-SARS2-2026-042.""")
    outbreak_name: str = Field(..., description="""Human-readable name for the investigation. e.g. 'Some County Salmonella Typhimurium Cluster 2026'.""")
    investigation_status: OutbreakStatusEnum = Field(..., description="""Current status of the investigation.""")
    pathogen: OrganismNameEnum = Field(..., description="""Primary pathogen under investigation.""")
    investigation_start_date: date = Field(..., description="""Date the investigation was formally opened.""")
    investigation_close_date: Optional[date] = Field(None, description="""Date the investigation was formally closed. NULL if ongoing.""")
    reporting_jurisdiction: str = Field(..., description="""Primary public health jurisdiction responsible for this investigation. e.g. 'State Health Dept', 'County DHS', 'CDC', 'WHO PAHO'.""")
    sectors_involved: Optional[List[SectorEnum]] = Field(default_factory=list, description="""One Health sectors represented in this investigation. A foodborne outbreak may involve clinical, agricultural, and food samples under the same investigation.""")
    case_count: Optional[int] = Field(None, description="""Current confirmed case count. Updated as investigation progresses.""")
    nndss_outbreak_number: Optional[str] = Field(None, description="""CDC NNDSS OutbreakNumber if this investigation has been reported to NNDSS. Links JACKPOT investigation to national outbreak tracking.""")
    notes: Optional[str] = Field(None, description="""Free text investigation notes. Not displayed in catalog.""")



class PipelineProvenance(ConfiguredBaseModel):
    """
    Structured provenance record for a pipeline run. Required for FAIR Reusability (R1.2 — detailed provenance). Serialized as JSON-LD alongside pipeline results in GCS.

    """
    pipeline_run_id: str = Field(...)
    pipeline_name: str = Field(...)
    pipeline_version: Optional[str] = Field(None)
    nextflow_version: Optional[str] = Field(None)
    reference_databases: Optional[List[str]] = Field(default_factory=list, description="""Reference databases and versions used. e.g. 'Pangolin 4.3/pango-designation 1.2.161', 'CARD 3.2.9', 'NCBIAMRFinderPlus 2024-01-31.1'
""")
    container_versions: Optional[List[str]] = Field(default_factory=list, description="""Docker/Singularity container image URIs with SHA digests""")
    input_sample_ids: Optional[List[str]] = Field(default_factory=list)
    output_uris: Optional[List[str]] = Field(default_factory=list)
    completed_at: Optional[datetime ] = Field(None)



class SampleFile(ConfiguredBaseModel):
    """
    A single read file (FASTQ or FASTA) associated with a sample. This is the canonical per-file registry and the source of truth for all file tracking.
Replaces the flat fastq_r1_uri / fastq_r2_uri columns on Sample as the complete file record. Those columns are kept as convenience denormalized fields, populated automatically by file_detector.py for the common 2-file paired-end case only.
Handles all real-world NGS file layouts:
  - Simple paired-end (R1 + R2)
  - Multi-lane Illumina (L001_R1, L001_R2, L002_R1, L002_R2 ...)
  - Nanopore multi-chunk (sample_0.fq.gz, sample_1.fq.gz ...)
  - Single-end / unpaired reads
  - Mixed or non-standard naming

Supported extensions (case-insensitive):
  .fastq, .fq                  with optional .gz or .bz2
  .fasta, .fa, .fna            with optional .gz

    """
    uri: str = Field(..., description="""gs:// or s3:// URI of the scrubbed file. UNIQUE — the same physical file cannot be registered twice.
""")
    raw_uri: Optional[str] = Field(None, description="""Pre-scrub URI. NULL after raw deletion (30-day lifecycle). Accessible to Lab Directors only.
""")
    filename: str = Field(..., description="""Original filename as uploaded. Examples: covid-19_sample_18_R1.fastq.gz, barcode01_0.fq.gz, wgs_L001_R1_001.fastq.gz
""")
    file_size_bytes: Optional[int] = Field(None)
    md5: Optional[str] = Field(None, description="""MD5 checksum populated post-upload for integrity verification""")
    file_type: SampleFileTypeEnum = Field(..., description="""FASTQ / FASTA / OTHER — derived from file extension""")
    library_layout: SampleFileLayoutEnum = Field(..., description="""PAIRED = one of a paired-end pair (partner in paired_file_id). SINGLE = paired-end read with missing partner. UNPAIRED = genuinely single-end or nanopore chunk.
""")
    read_direction: Optional[ReadDirectionEnum] = Field(None, description="""R1 (forward) or R2 (reverse) for paired reads. NULL for unpaired, single-end, or BAM files.
""")
    lane: Optional[str] = Field(None, description="""Illumina lane identifier, e.g. L001, L002. NULL for non-multi-lane runs.
""")
    chunk_index: Optional[int] = Field(None, description="""Nanopore/multi-file chunk index (0-based). NULL for non-chunked data.
""")
    paired_file_id: Optional[str] = Field(None, description="""ID of the partner SampleFile for this read direction (R1↔R2). NULL for unpaired files.
""")
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    content_hash: Optional[str] = Field(None, description="""SHA-256 of the full file contents, hex-encoded (64 characters). The dedup primitive — UNIQUE in the database when non-null. NULL until the compute_full_content_hash background job populates it lazily after registration. See Critical Rule 58.
""")
    head64k_hash: Optional[str] = Field(None, description="""SHA-256 of the first 64 KB of the file, hex-encoded. Cheap fingerprint piece used together with file_size_bytes and tail64k_hash to short-circuit dedup before the full content_hash is available.
""")
    tail64k_hash: Optional[str] = Field(None, description="""SHA-256 of the last 64 KB of the file, hex-encoded. Cheap fingerprint piece — see head64k_hash.
""")
    storage_state: FileStorageState = Field("EXTERNAL", description="""Lifecycle ownership of this file: EXTERNAL, MANAGED, MIRRORED, STAGED, or BROKEN. Defaults to EXTERNAL — JACKPOT does not copy bytes on ingest and references files in place. See Critical Rule 57 and the FileStorageState enum.
""")
    alternate_uris: Optional[List[str]] = Field(default_factory=list, description="""Additional URIs that point to the same content. Used when the same FASTQ is reachable at multiple locations (e.g. on a local NFS mount at /srv/seq/... and in a cloud archive at gs://archive/...). The primary uri stays in the uri column; everything else lands here.
""")
    first_seen_at: datetime  = Field(..., description="""Timestamp when JACKPOT first registered this file. Set DB-side to NOW() at insert; never updated.
""")
    last_verified_at: Optional[datetime ] = Field(None, description="""Timestamp of the most recent successful or attempted verification by the verify_file_references background job. NULL until the job first runs against this row.
""")
    last_verification_status: Optional[str] = Field(None, description="""Outcome of the most recent verification attempt: OK, MISSING, SIZE_CHANGED, or READ_ERROR. NULL until the job first runs.
""")
    retention_policy: str = Field("STANDARD", description="""Retention class governing how long the file is kept: STANDARD, LONG_TERM, or EPHEMERAL. Defaults to STANDARD.
""")
    original_uri: Optional[str] = Field(None, description="""For storage_state == MIRRORED only — the external URI that the managed copy was made from. NULL for all other storage states.
""")
    staged_for_run_id: Optional[str] = Field(None, description="""For storage_state == STAGED only — the UUID of the pipeline run that owns this temporary copy. The staging-cleanup job uses this to identify which staged files are safe to remove. NULL for all other storage states.
""")
    updated_at: datetime  = Field(..., description="""Timestamp of the most recent change to this row. Maintained by a DB trigger on UPDATE; not user-writable.
""")



class ExecutionProfile(ConfiguredBaseModel):
    """
    A named, operator-configured set of execution settings that the launch endpoint applies to a single pipeline run. Each profile carries an executor type (LOCAL, SLURM, GCP_BATCH, ...), a container engine, a work directory, and executor-specific overrides in config_overrides JSONB. At most one profile per deployment may carry is_default=true; that profile is the fallback when neither the launch request nor the pipeline's default-profile association picks one. Soft-deleted via active=false. See Critical Rule 59 and spec.md Phase P0g.

    """
    profile_id: str = Field(..., description="""UUID primary key. Generated DB-side via gen_random_uuid() on insert.
""")
    name: str = Field(..., description="""Operator-friendly profile name; UNIQUE within a deployment. Examples: \"default-local\", \"slurm-mylab-apptainer\", \"gcp-batch-spot-us-central1\".
""")
    executor_type: ExecutorTypeEnum = Field(..., description="""Which Nextflow executor this profile drives.
""")
    container_engine: ContainerEngineEnum = Field(..., description="""Container runtime used to materialize pipeline processes. NONE means processes run as native binaries on the host.
""")
    work_dir: str = Field(..., description="""Filesystem path or cloud URI (gs://, s3://) where Nextflow stages task work directories for runs that select this profile.
""")
    config_overrides: str = Field("{}", description="""Executor-specific fields rendered into the per-run nextflow.config — e.g. Slurm account/partition/QOS, GCP project/region, Kubernetes namespace, weblog_reachable. Stored as JSONB at the database level; modeled as a string here because LinkML has no native JSONB range. The renderer (G-4) parses this column with json.loads. Defaults to the empty object.
""")
    is_default: bool = Field(False, description="""True for the deployment-default profile. The migration enforces \"at most one row with is_default=true\" via a partial unique index. Defaults to false.
""")
    created_by_id: int = Field(..., description="""FK to users.id — the operator who created the profile.
""")
    created_at: datetime  = Field(..., description="""Timestamp the profile was created. Set DB-side to NOW() at insert; never updated.
""")
    active: bool = Field(True, description="""Soft-delete flag. Inactive profiles are hidden from launch selection but retained for audit. Defaults to true.
""")



class PipelineDefaultProfile(ConfiguredBaseModel):
    """
    Association linking a pipeline to one or more execution profiles that the launch endpoint should consider as defaults when the request does not name a profile explicitly. A pipeline may have multiple default profiles; the launcher picks the lowest priority value (priority=1 wins over priority=100). pipeline_id is intentionally a string-typed UUID reference rather than a typed FK because the pipelines surface is not yet represented as a LinkML class — only at the SQL level via pipeline_catalog (which carries a SERIAL id, not a UUID). When the pipelines surface gets a LinkML class with a UUID PK, this field becomes a typed range. See spec.md Phase P0g and the Phase P0g G-1 prompt's \"FK fallback\" guidance.

    """
    pipeline_id: str = Field(..., description="""UUID of the pipeline this association applies to. Composite PK component with profile_id.
""")
    profile_id: str = Field(..., description="""The default profile for the named pipeline. Composite PK component with pipeline_id.
""")
    priority: int = Field(100, description="""Tie-breaker when a pipeline has multiple default profiles — lower numeric values are preferred. Defaults to 100.
""")




# Model rebuild
# see https://pydantic-docs.helpmanual.io/usage/models/#rebuilding-a-model
Organization.model_rebuild()
Lab.model_rebuild()
Project.model_rebuild()
Sample.model_rebuild()
HumanSample.model_rebuild()
WildlifeSample.model_rebuild()
CompanionAnimalSample.model_rebuild()
LivestockSample.model_rebuild()
VectorSample.model_rebuild()
EnvironmentalSample.model_rebuild()
WastewaterSample.model_rebuild()
WaterSample.model_rebuild()
AirSample.model_rebuild()
SoilSample.model_rebuild()
SurfaceSample.model_rebuild()
FoodSample.model_rebuild()
ProduceAgSample.model_rebuild()
SampleAssociation.model_rebuild()
OutbreakInvestigation.model_rebuild()
PipelineProvenance.model_rebuild()
SampleFile.model_rebuild()
ExecutionProfile.model_rebuild()
PipelineDefaultProfile.model_rebuild()
