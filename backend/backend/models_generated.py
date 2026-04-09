from __future__ import annotations

import sys
from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel as BaseModel
from pydantic import ConfigDict, Field

if sys.version_info >= (3, 8):
    pass
else:
    pass


metamodel_version = "None"
version = "4.1"


class ConfiguredBaseModel(BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        validate_default=True,
        extra="forbid",
        arbitrary_types_allowed=True,
        use_enum_values=True,
    )

    pass


class OrganismNameEnum(str, Enum):
    """
    Controlled vocabulary of pathogen organism names. Derived from ADHS mandatory reportable communicable diseases. Anchored to NCBI Taxonomy for BioSample/SRA/GenBank/GISAID compatibility.

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
    # Valley fever (coccidioidomycosis) — California strain. Added by ASU/ADHS request; not on ADHS communicable disease list.

    Coccidioides_immitis = "Coccidioides immitis"
    # Valley fever (coccidioidomycosis) — Arizona/Texas strain. Predominant species in Arizona. Added by ASU/ADHS request; not on ADHS communicable disease list.

    Coccidioides_posadasii = "Coccidioides posadasii"
    # Chikungunya fever
    Chikungunya_virus = "Chikungunya virus"
    # Crimean-Congo hemorrhagic fever (CCHF)
    Crimean_Congo_hemorrhagic_fever_orthonairovirus = (
        "Crimean-Congo hemorrhagic fever orthonairovirus"
    )
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
    # RSV — included under ADHS 'Respiratory disease (outbreak)'. Use strain field for RSV-A or RSV-B.

    Respiratory_syncytial_virus = "Respiratory syncytial virus"
    # Rubella (German measles)
    Rubella_virus = "Rubella virus"
    # Severe acute respiratory syndrome (SARS, 2003)
    SARS_CoV = "SARS-CoV"
    # COVID-19 (novel coronavirus infection). NCBI standard name for SARS-CoV-2. Use pango_lineage field for Pangolin lineage designation.

    Severe_acute_respiratory_syndrome_coronavirus_2 = (
        "Severe acute respiratory syndrome coronavirus 2"
    )
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
    # ADHS reportable category: 'Emerging or exotic disease'. Use when a novel pathogen is identified but has no stable NCBI Taxonomy name yet. Platform Admin assigns permanent name when NCBI Taxonomy provides one.

    novel_pathogen = "novel pathogen"


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


class SharingLevelEnum(str, Enum):
    # Owner and Lab Director only
    PRIVATE = "PRIVATE"
    # All members of the owning Lab
    LAB = "LAB"
    # Metadata visible to all; files require access request
    DISCOVERABLE = "DISCOVERABLE"
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
    # Whole arthropod homogenate
    homogenized = "homogenized"
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


class Organization(ConfiguredBaseModel):
    """
    An institution (e.g. ASU, ADHS, CDC). Maps to APGAP Organization model.

    """

    display_name: str = Field(...)
    default_approve_analytical_dataset_requests: bool | None = Field(
        None, description="""Auto-approve dataset access requests from this org"""
    )


class Lab(ConfiguredBaseModel):
    """
    A research lab or operational unit within an Organization.
    """

    display_name: str = Field(...)
    organization: str = Field(...)
    description: str | None = Field(None)


class Project(ConfiguredBaseModel):
    """
    A specific study or surveillance effort within a Lab.
    """

    display_name: str = Field(...)
    lab: str = Field(...)
    pathogen_scope: list[str] | None = Field(default_factory=list)
    status: ProjectStatusEnum | None = Field(None)


class Sample(ConfiguredBaseModel):
    """
    Base class for all sequenced samples. Pathogen-agnostic. Fields derived from APGAP All_Sequences.xlsx. Every URI maps to GenEpiO, NCBI BioSample, MIxS, or OBI where a standard term exists.

    """

    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class HumanSample(Sample):
    """
    Clinical or surveillance sample from a human host. Fields from APGAP human_host.xlsx. Maps to GA4GH Phenopacket Individual + Disease elements.

    """

    adhs_medsis_id: str = Field(
        ...,
        description="""APGAP: 'ADHS issued ID (links with MEDSIS case data on their end)'. Either (1) an anonymized ID linking to the MEDSIS case record, or (2) an exemption code obtained for the study if the sample does not originate from ADHS surveillance. Validation: cross-checked against ADHS-issued ID list when that list becomes available. Currently free text — validation to be added when ADHS establishes the list. Distinct from case_id (used by non-ADHS public health sources).
""",
    )
    case_id: str | None = Field(
        None,
        description="""Generic public health case identifier for non-ADHS sources (e.g. CDC NEDSS case ID, county health department ID).
""",
    )
    biospecimen_type: BiospecimenTypeEnum = Field(
        ...,
        description="""APGAP: 'Biospecimen type'. Type of biological specimen collected.
""",
    )
    reason_for_collection: list[ReasonForCollectionEnum] = Field(
        default_factory=list,
        description="""APGAP: 'Reason for sample collection'. Whether sample was obtained during clinical care or research study.
""",
    )
    host_sex: BiologicalSexEnum | None = Field(
        None,
        description="""APGAP: 'Sex'. Biological sex of the human host.
""",
    )
    host_age: int | None = Field(
        None,
        description="""APGAP: 'Age (years)'. Age at time of collection. Validation: integer, range [0, 120]. Unit: years.
""",
    )
    host_age_unit: AgeUnitEnum | None = Field(
        None, description="""Unit for host_age when age < 1 year"""
    )
    host_species: str | None = Field(
        None,
        description="""Auto-populated as 'Homo sapiens' for HumanSample. Not user-entered.
""",
    )
    host_disease: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Disease'. The disease caused by the pathogen (whether or not the host is symptomatic). Match defined allowable entries.
""",
    )
    isolation_source: str | None = Field(
        None,
        description="""Auto-populated as 'human clinical specimen' for HumanSample.
""",
    )
    vaccination_status: str | None = Field(
        None,
        description="""e.g. fully vaccinated, unvaccinated, boosted, partially vaccinated, unknown.
""",
    )
    clinical_outcome: str | None = Field(
        None,
        description="""e.g. hospitalized, ICU, deceased, outpatient, asymptomatic, unknown.
""",
    )
    underlying_conditions: list[str] | None = Field(
        default_factory=list,
        description="""Relevant comorbidities, e.g. diabetes, immunocompromised, chronic lung disease, obesity.
""",
    )
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class WildlifeSample(Sample):
    """
    Sample from a wild animal host. Fields from APGAP wildlife_host.xlsx.

    """

    host_species: str = Field(
        ...,
        description="""APGAP: 'Host species'. Scientific name preferred (genus + species); genus only acceptable. Match defined allowable entries. Examples: Eptesicus fuscus, Canis latrans, Odocoileus virginianus.
""",
    )
    wildlife_subject_id: str | None = Field(
        None, description="""Optional alphanumeric field identifier for the animal"""
    )
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    host_disease: list[str] = Field(default_factory=list)
    isolation_source: str | None = Field(
        None, description="""Auto-derived from host species + biospecimen type"""
    )
    isolate: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class CompanionAnimalSample(Sample):
    """
    Sample from a companion (pet) animal host. Fields from APGAP Companion_animal_host.xlsx.

    """

    host_species: str = Field(
        ...,
        description="""APGAP: 'Host species'. Genus and species. Examples: felis catus, canis familiaris.
""",
    )
    companion_subject_id: str | None = Field(
        None, description="""Optional alphanumeric field identifier for the animal"""
    )
    location_type: CompanionAnimalLocationEnum | None = Field(
        None,
        description="""APGAP: 'Location type'. Animal's setting.
""",
    )
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    vaccine_status_against_pathogen: VaccineStatusEnum | None = Field(
        None, description="""APGAP: 'Vaccine status against pathogen'"""
    )
    host_disease: list[str] = Field(default_factory=list)
    symptomatic: SymptomaticEnum | None = Field(
        None, description="""Whether animal was symptomatic at time of collection"""
    )
    isolation_source: str | None = Field(None)
    isolate: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class LivestockSample(Sample):
    """
    Sample from a livestock or agricultural animal host. Fields from APGAP Livestock_Ag_animal_host.xlsx.

    """

    host_species: str = Field(
        ...,
        description="""APGAP: 'Host species'. Scientific name of livestock species. Examples: Gallus gallus domesticus, Sus domesticus, Lama glama.
""",
    )
    livestock_subject_id: str | None = Field(
        None, description="""Optional field identifier for the individual animal"""
    )
    biospecimen_type: BiospecimenTypeEnum = Field(...)
    livestock_products: list[LivestockProductEnum] = Field(default_factory=list)
    location_type: LivestockLocationEnum | None = Field(None)
    distribution_scale: list[DistributionScaleEnum] | None = Field(default_factory=list)
    antibiotic_use: AntibioticUseEnum | None = Field(None)
    host_disease: list[str] = Field(default_factory=list)
    isolation_source: str | None = Field(None)
    isolate: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class VectorSample(Sample):
    """
    Sample from a disease vector (arthropod). Fields from APGAP vectors.xlsx.

    """

    vector_species: str = Field(
        ...,
        description="""APGAP: 'Vector species'. Scientific name. Examples: Aedes aegypti, Culex tarsalis, Rhipicephalus sanguineus, Dermacentor andersoni.
""",
    )
    vector_host_species: str | None = Field(
        None, description="""Host animal the vector was collected from, if known"""
    )
    biospecimen_type: VectorBiospecimenTypeEnum = Field(...)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class EnvironmentalSample(Sample):
    """
    Base class for all environmental samples. Do not instantiate directly — use the specific environmental subclasses below.

    """

    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class WastewaterSample(EnvironmentalSample):
    """
    Sample from a wastewater collection or treatment system. Fields from APGAP wastewater_sample.xlsx, aligned with CDC NWSS mandatory reporting fields. Reference: https://www.cdc.gov/nwss/reporting.html

    """

    wwtp_name: str | None = Field(
        None,
        description="""APGAP: 'Location (sample_location_specify)'. NWSS: sample_location. Wastewater facility name or upstream sewer location. Examples: 'South Tempe Water Reclamation Facility', 'undisclosed sewer line upstream of 5th Ave'.
""",
    )
    sample_location_zipcode: str | None = Field(
        None, description="""US ZIP code of wastewater sampling location (5-digit)"""
    )
    county_names: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Service area (county_names)'. NWSS: county_names. Counties served by this sampling site, by name or FIPS code. System cross-maps name ↔ FIPS. Multiple entries permitted. Examples: 'Maricopa County', '04013', 'Coconino'.
""",
    )
    population_served: int = Field(
        ...,
        description="""APGAP/NWSS: 'Population served'. Estimated number of persons served by this sampling site. Validation: positive integer.
""",
    )
    sample_type: WastewaterSampleTypeEnum = Field(
        ..., description="""APGAP/NWSS: 'Sample type'. e.g. grab, 24-hr composite"""
    )
    sample_matrix: SampleMatrixEnum = Field(
        ...,
        description="""APGAP/NWSS: 'Sample matrix'. Wastewater matrix from which the sample was collected.
""",
    )
    pretreatment: list[PretreatmentEnum] = Field(
        default_factory=list,
        description="""APGAP: 'Pretreatment'. Treatment applied prior to collection. Flag if 'none' co-occurs with any other value.
""",
    )
    concentration_method: ConcentrationMethodEnum = Field(...)
    flow_rate_mgd: float = Field(
        ...,
        description="""APGAP: 'Flow rate (MGD)'. NWSS: flow_rate. Wastewater volumetric flow rate in million gallons per day. Validation: positive float. Unit: MGD.
""",
    )
    sample_collect_time: str | None = Field(
        None,
        description="""NWSS: 'sample_collect_time'. Local 24-hr time (HH:MM). For composite samples: start time.
""",
    )
    pcr_target: str | None = Field(
        None,
        description="""NWSS: 'pcr_target'. PCR quantification target. e.g. sars-cov-2, influenza-a, mpox, hMPXV Clade I. See NWSS value set vs_pcr_target.
""",
    )
    pcr_gene_target: str | None = Field(
        None,
        description="""NWSS: 'pcr_gene_target'. PCR gene for quantification. Must align with pcr_target selection.
""",
    )
    pcr_gene_target_ref: str | None = Field(
        None, description="""NWSS: Publication or URL for the PCR gene target used"""
    )
    pcr_type: str | None = Field(
        None,
        description="""NWSS: 'pcr_type'. Type of PCR used. Non-sars-cov-2/mpox targets must use a digital PCR type.
""",
    )
    quant_stan_type: str | None = Field(
        None, description="""NWSS: Type of nucleic acid used as quantification standard"""
    )
    stan_ref: str | None = Field(
        None, description="""NWSS: Publication/description of quantitative standard"""
    )
    lod_ref: str | None = Field(
        None, description="""NWSS: Publication/description of limit of detection method"""
    )
    inhibition_method: str | None = Field(
        None, description="""NWSS: Method to evaluate molecular inhibition; 'none' if not tested"""
    )
    num_no_target_control: int | None = Field(
        None, description="""NWSS: Number of no-template controls (NTC) per instrument run"""
    )
    pasteurized: bool | None = Field(None, description="""NWSS: Was the sample pasteurized?""")
    env_broad_scale: str | None = Field(
        None, description="""MIxS required. ENVO term. e.g. ENVO:00002001 (wastewater)"""
    )
    env_local_scale: str | None = Field(
        None, description="""MIxS required. ENVO term. e.g. ENVO:01000621 (municipal WWTP)"""
    )
    env_medium: str | None = Field(
        None, description="""MIxS required. ENVO term. e.g. ENVO:00002040 (sewage)"""
    )
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class WaterSample(EnvironmentalSample):
    """
    Sample from a non-wastewater water source. Fields from APGAP Water_sample.xlsx.

    """

    water_source: WaterSourceEnum | None = Field(
        None, description="""APGAP: 'Water source'. Type of water body or supply."""
    )
    water_temperature_c: float = Field(
        ...,
        description="""APGAP: 'Water temperature (C)'. Validation: range [-36, 100]. Unit: °C.
""",
    )
    turbidity_ntu: float = Field(
        ...,
        description="""APGAP: 'Turbidity (NTU)'. Nephelometric Turbidity Units. Validation: range (0, 4000]; values above 4000 flagged for confirmation (possible decimal point omission). Unit: NTU.
""",
    )
    ph: float = Field(..., description="""APGAP: 'pH'. Validation: range [0, 14].""")
    salinity_ppm: float = Field(..., description="""APGAP: 'Salinity (ppm)'. Unit: ppm.""")
    env_broad_scale: str | None = Field(None)
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class AirSample(EnvironmentalSample):
    """
    Airborne/aerosol sample. Fields from APGAP Air.xlsx.

    """

    air_source: AirSourceEnum = Field(
        ...,
        description="""APGAP: 'Source'. Origin of the air sample. Examples: cooling tower, internal vent, urban, plane.
""",
    )
    airflow_rate_m3_s: float = Field(
        ..., description="""APGAP: 'Airflow rate (m³/s)'. Validation: positive float. Unit: m³/s."""
    )
    pm25_ug_m3: float = Field(
        ..., description="""APGAP: 'PM2.5 (µg/m³)'. Validation: positive float. Unit: µg/m³."""
    )
    pm10_ug_m3: float = Field(
        ..., description="""APGAP: 'PM10 (µg/m³)'. Validation: positive float. Unit: µg/m³."""
    )
    env_broad_scale: str | None = Field(None)
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class SoilSample(EnvironmentalSample):
    """
    Sample from a soil matrix. Fields from APGAP Soil_sample.xlsx.

    """

    soil_site_type: str = Field(
        ...,
        description="""APGAP: 'Type of soil site'. Characterization of the soil context. Examples: rodent burrow, construction site, agricultural, CAFO vicinity.
""",
    )
    sample_depth_cm: str = Field(
        ...,
        description="""APGAP: 'Depth of sample (cm)'. Single value or range. Examples: 5, [0, 2], [0, 10]. Validation: positive numeric, single value or range notation.
""",
    )
    nitrogen_mg_kg: float | None = Field(
        None, description="""APGAP: 'Nitrogen (mg/kg)'. Unit: mg/kg."""
    )
    soil_temperature_c: float | None = Field(
        None,
        description="""APGAP: 'Temperature (C)'. Soil temperature. Validation: range [-36, 100]. Unit: °C.
""",
    )
    moisture_g_g: float | None = Field(
        None, description="""APGAP: 'Moisture (g/g)'. Gravimetric water content. Unit: g/g."""
    )
    organic_carbon_g_kg: float | None = Field(
        None, description="""APGAP: 'Organic carbon (g/kg)'. Unit: g/kg."""
    )
    soil_ph: float | None = Field(None, description="""APGAP: 'pH'. Validation: range [0, 14].""")
    soil_salinity_ppm: float | None = Field(
        None, description="""APGAP: 'Salinity (ppm)'. Unit: ppm."""
    )
    env_broad_scale: str | None = Field(
        None,
        description="""MIxS required. ENVO term. e.g. ENVO:00001998 (soil), ENVO:00000046 (agricultural soil)
""",
    )
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class SurfaceSample(EnvironmentalSample):
    """
    Surface swab sample (indoor or outdoor). Fields from APGAP Surface.xlsx. NCBI MIMS.me.built_environment package.

    """

    indoor_space: str = Field(
        ...,
        description="""APGAP/NCBI: 'indoor_space'. Distinguishable space within a structure. Allowable: bedroom, office, bathroom, foyer, kitchen, locker room, hallway, elevator, missing, not applicable, not collected, not provided, restricted access.
""",
    )
    indoor_surface: str = Field(
        ...,
        description="""APGAP/NCBI: 'indoor_surface'. Type of indoor surface. Allowable: counter top, window, wall, cabinet, ceiling, door, shelving, vent cover, missing, not applicable, not collected, not provided, restricted access.
""",
    )
    indoor_surface_subpart: str | None = Field(
        None, description="""APGAP/NCBI: 'indoor_surf_subpart'. Subpart of object swabbed."""
    )
    surface_orientation: list[str] | None = Field(
        default_factory=list,
        description="""APGAP/NCBI: 'surface_orientation'. e.g. underside, top, corner.""",
    )
    surface_material: list[str] = Field(
        default_factory=list,
        description="""APGAP/NCBI: 'surf_material'. Surface materials at sampling point. Examples: concrete, wood, tile, plastic, glass, stainless steel.
""",
    )
    surface_temperature_c: float | None = Field(
        None, description="""APGAP/NCBI: 'surf_temp'. Surface temperature. Unit: °C."""
    )
    surface_air_contaminants: list[str] | None = Field(
        default_factory=list,
        description="""APGAP/NCBI: 'surf_air_cont'. Contaminant on surface. Examples: dust, organic matter, particulate matter, VOCs.
""",
    )
    surface_moisture_qualitative: str | None = Field(
        None,
        description="""APGAP/NCBI: 'samp_surf_moisture'. Qualitative moisture. Values: intermittent moisture, not present, submerged.
""",
    )
    surface_moisture_cm3_cm3: float | None = Field(
        None, description="""APGAP/NCBI: 'surf_moisture'. Numeric moisture. Unit: cm³/cm³."""
    )
    surface_moisture_ph: float | None = Field(
        None,
        description="""APGAP/NCBI: 'surf_moisture_ph'. pH of surface moisture. Range [0,14].""",
    )
    surface_humidity_pct: float | None = Field(
        None, description="""APGAP/NCBI: 'surf_humidity'. Water activity. Unit: %."""
    )
    wall_surface_treatment: list[str] | None = Field(
        default_factory=list,
        description="""APGAP/NCBI: 'wall_surf_treatment'. e.g. painted, wall paper, no treatment, stucco, fabric.
""",
    )
    wall_texture: list[str] | None = Field(
        default_factory=list,
        description="""APGAP/NCBI: 'wall_texture'. e.g. smooth, popcorn, orange peel, knockdown, Santa-Fe texture.
""",
    )
    wall_mold_signs: str | None = Field(
        None,
        description="""APGAP/NCBI: 'wall_water_mold'. Signs of mold/mildew. Values: yes, no, unknown.
""",
    )
    env_broad_scale: str | None = Field(
        None, description="""MIxS required. ENVO term. e.g. ENVO:01000162 (built environment)"""
    )
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class FoodSample(EnvironmentalSample):
    """
    Sample from a food product. Fields from APGAP Food-Products.xlsx.

    """

    food_location_type: FoodLocationTypeEnum = Field(
        ..., description="""APGAP: 'Location type'. Where the food sample was collected."""
    )
    storage_temperature_setting: str | None = Field(
        None,
        description="""APGAP: 'Storage temperature setting'. Numeric (°C) or descriptive string. Examples: freezer, frozen, refrigerator, shelf, room temperature. Validation: numeric OR match defined allowable entries.
""",
    )
    product_temperature_c: float | None = Field(
        None,
        description="""APGAP: 'Product temperature (C)'. Actual measured temperature. Validation: range [-36, 100]. Unit: °C.
""",
    )
    food_product_type: FoodProductTypeEnum = Field(...)
    env_broad_scale: str | None = Field(None)
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class ProduceAgSample(EnvironmentalSample):
    """
    Sample from an agricultural produce crop. Fields from APGAP Produce_Ag.xlsx.

    """

    plant_species: str = Field(
        ...,
        description="""APGAP: 'Plant species'. Scientific name of the agricultural plant. Examples: Lactuca sativa var. longifolia, Allium cepa.
""",
    )
    distribution_scale: list[DistributionScaleEnum] | None = Field(default_factory=list)
    produce_water_source: list[ProduceWaterSourceEnum] = Field(default_factory=list)
    fertilizer_type: list[FertilizerTypeEnum] | None = Field(default_factory=list)
    near_animal_agriculture: bool = Field(
        ..., description="""Whether crop is downwind/downhill of animal ag operations"""
    )
    washed_before_packing: bool | None = Field(None)
    env_broad_scale: str | None = Field(None)
    env_local_scale: str | None = Field(None)
    env_medium: str | None = Field(None)
    sample_id: str = Field(
        ...,
        description="""Unique alphanumeric identifier for this sample. Must not already be in use in the system. APGAP: 'Sample ID'. Validation: alphanumeric, unique. Portal mints persistent URI at ingest: https://data.jackpot.health/samples/{sample_id}
""",
    )
    jackpot_uri: str | None = Field(
        None,
        description="""Persistent URI minted at ingest for FAIR Findability (F1). Format: https://data.jackpot.health/samples/{sample_id} Stable before NCBI/GISAID accessions are assigned.
""",
    )
    lab: str = Field(...)
    project: str = Field(...)
    owner: str = Field(..., description="""Email of the researcher who uploaded the sample""")
    source_type: SourceTypeEnum = Field(
        ...,
        description="""APGAP: 'Source type'. Determines which host-specific subclass is required. Further required fields depend on this value. Validation: match defined allowable entries.
""",
    )
    organism_name: OrganismNameEnum = Field(
        ...,
        description="""NCBI organism name. Controlled vocabulary derived from the ADHS mandatory reportable communicable diseases list, plus Coccidioides spp. (Valley fever) and metagenome for metagenomic samples. Platform Admins may add new values when novel pathogens emerge. Researchers may request additions via the portal. Use 'metagenome' when no specific organism is targeted. APGAP: 'Pathogen/organism name (or metagenomic)'.
""",
    )
    strain: str | None = Field(
        None,
        description="""Pathogen strain designation. Also used for: Influenza subtype (H1N1, H3N2), Pango lineage pre-Pangolin-pipeline, rabies variant, poliovirus type (wild vs. vaccine-derived).
""",
    )
    isolate: str | None = Field(
        None,
        description="""APGAP: 'Isolate'. Identification or description of the specific individual from which the sample was obtained.
""",
    )
    serotype: str | None = Field(
        None,
        description="""Serotype of the pathogen isolate. Use for: Salmonella serovar (e.g. Typhimurium, Enteritidis), Dengue serotype (DENV-1 to DENV-4), Poliovirus type (1, 2, 3), Influenza subtype (H1N1, H3N2, H5N1).
""",
    )
    biosample_accession: str | None = Field(
        None, description="""NCBI BioSample accession (e.g. SAMN12345678)"""
    )
    sra_accession: str | None = Field(None, description="""NCBI SRA accession (e.g. SRR12345678)""")
    genbank_accession: str | None = Field(None, description="""GenBank accession (e.g. OQ123456)""")
    gisaid_accession: str | None = Field(
        None, description="""GISAID EPI_ accession (e.g. EPI_ISL_1234567)"""
    )
    bioproject_accession: str | None = Field(
        None, description="""NCBI BioProject accession (e.g. PRJNA123456)"""
    )
    type_of_experiment: ExperimentTypeEnum = Field(
        ...,
        description="""APGAP: 'Type of experiment'. Validation: match defined allowable entries (one only).
""",
    )
    nucleic_acid_extraction_method: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Nucleic acid extraction method'. Multiple values permitted. Match defined allowable entries.
""",
    )
    library_preparation_method: str = Field(
        ...,
        description="""APGAP: 'Nucleic acid library preparation method'. Match defined allowable entries (one only).
""",
    )
    sequencing_protocol: str = Field(
        ...,
        description="""APGAP: 'Sequencing protocol'. URL to protocol document. Validation: URL format preferred (e.g. https://www.protocols.io/view/artic-v4-1).
""",
    )
    sequencing_platform: SequencingPlatformEnum = Field(
        ...,
        description="""APGAP: 'Sequencing instrument make and model'. Validation: match defined allowable entries (one only).
""",
    )
    sequencing_instrument: str | None = Field(
        None,
        description="""Specific instrument model. Examples: NextSeq 2000, MinION, Sequel IIe, Ion S5.
""",
    )
    sequencing_lab: str = Field(
        ...,
        description="""APGAP: 'Sequencing lab (originating lab)'. The lab that performed the sequencing. NOT a static enum — validated at ingest against the sequencing_labs database table, which is a Platform Admin-managed controlled vocabulary. Seeded values: 'Sonora Quest Laboratories', 'Laboratory Corporation of America'. Registered JACKPOT Labs are auto-added (APGAP backlog #42). Unknown values trigger validation error directing Lab Director to submit a sequencing lab addition request via the portal (APGAP backlog #7).
""",
    )
    date_collected: date = Field(
        ...,
        description="""APGAP: 'Date Collected'. ISO 8601 format (YYYY-MM-DD). Validation: flag if >5 years in past; reject if future date.
""",
    )
    date_sequenced: date = Field(
        ...,
        description="""APGAP: 'Date Sequenced'. ISO 8601 format. Validation: must not be future date; must not precede date_collected.
""",
    )
    collection_facility: str = Field(
        ...,
        description="""APGAP: 'Collection facility'. Institution or facility where the sample was collected. Match defined allowable entries.
""",
    )
    purpose_for_collection: list[str] = Field(
        default_factory=list,
        description="""APGAP: 'Purpose for collection and sequencing'. Multiple selections permitted. Match defined allowable entries.
""",
    )
    collection_location_country: str = Field(..., description="""Country of sample collection""")
    collection_location_state: str | None = Field(
        None, description="""US state or equivalent administrative region"""
    )
    collection_location_county: str | None = Field(
        None, description="""County or equivalent sub-state region"""
    )
    collection_location_zipcode: str | None = Field(
        None,
        description="""APGAP: 'Zip code'. US ZIP code of collection location. Validation: 5-digit numeric format.
""",
    )
    geo_lat: float | None = Field(None, description="""Decimal latitude (WGS84), e.g. 33.4484""")
    geo_lon: float | None = Field(None, description="""Decimal longitude (WGS84), e.g. -112.0740""")
    mmwr_year: int | None = Field(
        None, description="""CDC MMWR epiweek year (computed at ingest)"""
    )
    mmwr_week: int | None = Field(
        None, description="""CDC MMWR week number 1–53 (computed at ingest)"""
    )
    iso_year: int | None = Field(
        None, description="""ISO 8601 week-based year (computed at ingest)"""
    )
    iso_week: int | None = Field(None, description="""ISO week number 1–53 (computed at ingest)""")
    associated_sample_ids: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'IDs of any associated samples'. Present in ALL sample type spreadsheets. Links sequences from the same investigation (e.g. pet and owner, food product and patient, vector and host). Validation: each ID should match an existing sample_id in the system. Flag (not reject) if linked sample not yet uploaded — may arrive later. Bidirectional linkage confirmed at resolution. Stored as directed pairs in the sample_associations table.
""",
    )
    ct_value: float | None = Field(
        None,
        description="""APGAP: 'Ct value'. PCR cycle threshold value. Validation: numeric, range [0, 50].
""",
    )
    other_testing_performed: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Other Testing Performed'. Multiple entries permitted. Match defined allowable entries. Flag error if 'none' entered alongside any other value.
""",
    )
    lab_of_other_testing: list[str] | None = Field(
        default_factory=list,
        description="""APGAP: 'Lab of Other Testing'. Conditional: required if other_testing_performed is not empty or 'none'.
""",
    )
    intermediary_clinical_lab: str | None = Field(
        None,
        description="""APGAP: 'Intermediary clinical lab name'. Optional. Match defined allowable entries.
""",
    )
    assembly_method: str | None = Field(
        None, description="""e.g. SPAdes 3.15, IVAR 1.4, Flye 2.9, Unicycler 0.5"""
    )
    coverage_depth: float | None = Field(None, description="""Mean sequencing depth (X)""")
    genome_completeness: float | None = Field(
        None, description="""Percentage of reference genome covered (0–100)"""
    )
    pango_lineage: str | None = Field(
        None, description="""Pangolin lineage designation, e.g. JN.1, BA.2.86"""
    )
    pango_lineage_version: str | None = Field(
        None, description="""Pangolin software version used for assignment"""
    )
    nextstrain_clade: str | None = Field(
        None, description="""Nextstrain clade designation, e.g. 24A"""
    )
    nextclade_qc_score: float | None = Field(
        None, description="""Nextclade QC score (0–100; higher is better quality)"""
    )
    nextclade_version: str | None = Field(None, description="""Nextclade software version""")
    vadr_status: VADRStatusEnum | None = Field(
        None, description="""NCBI VADR genome annotation validation result"""
    )
    vadr_alerts: list[str] | None = Field(
        default_factory=list, description="""VADR alert codes, e.g. CDS_HAS_STOP_CODON"""
    )
    mlst_scheme: str | None = Field(
        None, description="""MLST scheme, e.g. 'senterica', 'campylobacter'"""
    )
    mlst_sequence_type: str | None = Field(None, description="""MLST sequence type, e.g. ST131""")
    amrfinder_genes: list[str] | None = Field(
        default_factory=list, description="""AMR genes detected by NCBI AMRFinder"""
    )
    card_aro_terms: list[str] | None = Field(
        default_factory=list, description="""CARD Antibiotic Resistance Ontology terms detected"""
    )
    loinc_code: str | None = Field(
        None,
        description="""LOINC code for the lab test performed. e.g. 94500-6 (SARS-CoV-2 RNA, PCR, NP swab)
""",
    )
    loinc_system: str | None = Field(
        None, description="""LOINC specimen/body site, e.g. 'Nasopharynx'"""
    )
    snomed_clinical_finding: str | None = Field(
        None, description="""SNOMED CT clinical finding code, e.g. 840539006"""
    )
    ncbi_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""NCBI SRA/BioSample/GenBank submission status via TOSTADAS"""
    )
    ncbi_submitted_at: datetime | None = Field(None)
    gisaid_submission_status: SubmissionStatusEnum | None = Field(
        None, description="""GISAID EpiCoV/EpiFlu/EpiPox submission status"""
    )
    gisaid_submitted_at: datetime | None = Field(None)
    fastq_r1_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the primary (R1 or first) scrubbed read file. Populated automatically for simple 2-file paired runs. Supports gs:// (GCS) and drs:// (GA4GH DRS) schemes. Accepted extensions: .fastq, .fq, .fasta, .fa, .fna with optional .gz or .bz2 compression. For all other cases (multi-lane, nanopore, multiple unpaired), query the sample_files table for the complete file list.
""",
    )
    fastq_r2_uri: str | None = Field(
        None,
        description="""Convenience field: URI of the R2 FASTQ for simple paired runs. NULL for single-end, multi-lane, or nanopore samples. Query sample_files for the complete file list.
""",
    )
    raw_fastq_uri: str | None = Field(
        None,
        description="""Pre-scrub URI of primary read file — restricted to Lab Directors and above. NULL after 30-day lifecycle deletion.
""",
    )
    consensus_fasta_uri: str | None = Field(
        None, description="""Consensus/assembly FASTA URI (auto-populated post-pipeline)"""
    )
    assembly_uri: str | None = Field(
        None, description="""Full assembly FASTA URI (auto-populated post-assembly pipeline)"""
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)
    sharing_level: SharingLevelEnum = Field(...)
    pi_name: str | None = Field(
        None,
        description="""APGAP: 'PI name'. Defaults to Lab Director. Validation: must match existing user in the platform.
""",
    )
    grant_number: str | None = Field(None, description="""APGAP: 'Grant number'. Alphanumeric.""")
    contact_other: str | None = Field(
        None,
        description="""APGAP: 'Contact (if other than user uploading data)'. Email format. Phase 2: allow non-user contacts.
""",
    )
    comments: str | None = Field(None, description="""Free text comments""")


class SampleAssociation(ConfiguredBaseModel):
    """
    Links two samples from the same investigation. Derived from 'IDs of any associated samples' field present in ALL APGAP sample type spreadsheets. Stored as directed pairs in the sample_associations table. Bidirectional: A→B implies B→A but stored as two records.

    """

    source_sample_id: str = Field(...)
    target_sample_id: str = Field(...)
    association_type: SampleAssociationTypeEnum | None = Field(None)
    notes: str | None = Field(None, description="""Free text notes about the association""")


class PipelineProvenance(ConfiguredBaseModel):
    """
    Structured provenance record for a pipeline run. Required for FAIR Reusability (R1.2 — detailed provenance). Serialized as JSON-LD alongside pipeline results in GCS.

    """

    pipeline_run_id: str = Field(...)
    pipeline_name: str = Field(...)
    pipeline_version: str | None = Field(None)
    nextflow_version: str | None = Field(None)
    reference_databases: list[str] | None = Field(
        default_factory=list,
        description="""Reference databases and versions used. e.g. 'Pangolin 4.3/pango-designation 1.2.161', 'CARD 3.2.9', 'NCBIAMRFinderPlus 2024-01-31.1'
""",
    )
    container_versions: list[str] | None = Field(
        default_factory=list,
        description="""Docker/Singularity container image URIs with SHA digests""",
    )
    input_sample_ids: list[str] | None = Field(default_factory=list)
    output_uris: list[str] | None = Field(default_factory=list)
    completed_at: datetime | None = Field(None)


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

    uri: str = Field(
        ...,
        description="""gs:// or drs:// URI of the scrubbed file. UNIQUE — the same physical file cannot be registered twice.
""",
    )
    raw_uri: str | None = Field(
        None,
        description="""Pre-scrub URI. NULL after raw deletion (30-day lifecycle). Accessible to Lab Directors only.
""",
    )
    filename: str = Field(
        ...,
        description="""Original filename as uploaded. Examples: covid-19_sample_18_R1.fastq.gz, barcode01_0.fq.gz, wgs_L001_R1_001.fastq.gz
""",
    )
    file_size_bytes: int | None = Field(None)
    md5: str | None = Field(
        None, description="""MD5 checksum populated post-upload for integrity verification"""
    )
    file_type: SampleFileTypeEnum = Field(
        ..., description="""FASTQ / FASTA / OTHER — derived from file extension"""
    )
    library_layout: SampleFileLayoutEnum = Field(
        ...,
        description="""PAIRED = one of a paired-end pair (partner in paired_file_id). SINGLE = paired-end read with missing partner. UNPAIRED = genuinely single-end or nanopore chunk.
""",
    )
    read_direction: ReadDirectionEnum | None = Field(
        None,
        description="""R1 (forward) or R2 (reverse) for paired reads. NULL for unpaired, single-end, or BAM files.
""",
    )
    lane: str | None = Field(
        None,
        description="""Illumina lane identifier, e.g. L001, L002. NULL for non-multi-lane runs.
""",
    )
    chunk_index: int | None = Field(
        None,
        description="""Nanopore/multi-file chunk index (0-based). NULL for non-chunked data.
""",
    )
    paired_file_id: str | None = Field(
        None,
        description="""ID of the partner SampleFile for this read direction (R1↔R2). NULL for unpaired files.
""",
    )
    scrub_status: ScrubStatusEnum = Field(...)
    pii_scan_status: PIIScanStatusEnum = Field(...)
    ingest_method: IngestMethodEnum = Field(...)


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
PipelineProvenance.model_rebuild()
SampleFile.model_rebuild()
