# Wastewater software landscape

Reference catalog of open-source software, methodologies, and algorithms used for wastewater pathogen analysis. This is the broader landscape doc — for JACKPOT's specific design, current state, and implementation path, see `docs/wastewater.md`.

This catalog covers the period 2018-2024, with focus on advances driven by the COVID-19 pandemic and subsequent multi-pathogen surveillance efforts.

## §1. Quick reference table

| Software / Platform | Main features & methods | Pathogen scope | Adoption / notes | Reference |
|---|---|---|---|---|
| **watermonitor** | Metatranscriptomic workflow, rapid AI-enhanced analysis, open-source (GitHub) | Viruses, bacteria | High accuracy/speed, reproducible, widely cited | [1] |
| **WastPan (Finland)** | Culture-based + molecular (qPCR, NGS), validated protocols | Viruses, bacteria, fungi, parasites, AMR genes | Covers 40% of Finland, model for national WBE | [2] |
| **Encyclopaedia Cloacae (EU4S)** | Digital platform, catalogues pathogens, geospatial analytics | Broad (global) | EU Wastewater Observatory, public health focus | [3] |
| **Custom open-source pipelines** | Multiplex qPCR, metagenomics, biosensors, dashboards | Multiple | Used in research and public health labs | [4] [5] |
| **Kraken2, PathoScope, ResPipe** | Taxonomic classification, AMR profiling, metagenomics | Bacteria, viruses, AMR | Widely used in bioinformatics workflows | [6] [7] |
| **Galaxy, EasyFlow** | GUI-based, reproducible workflows | Multiple | User-friendly, non-programmer access | [8] [9] |

## §2. Study scope

- **Time period:** 2018–2024 (focus on recent advances and COVID-19-driven innovation)
- **Disciplines:** Environmental microbiology, bioinformatics, public health, molecular biology, engineering
- **Methods covered:** Comparative software review, algorithmic evaluation, methodology catalog

## §3. Assumptions and limitations of this catalog

- Open source software is defined here by public code availability and modifiability.
- Many platforms are rapidly evolving; features and adoption may change.
- Standardization and data comparability remain major limitations across studies and software.
- Most entries are derived from peer-reviewed literature and public repositories; some emerging tools may not be captured.

## §4. Introduction

### §4.1 Wastewater-based epidemiology and pathogen surveillance

Wastewater-based epidemiology (WBE) has emerged as a critical tool for public health surveillance, enabling the detection and monitoring of infectious diseases, antimicrobial resistance (AMR), and emerging pathogens at the community level. By analyzing sewage, WBE provides a non-invasive, cost-effective means to assess population health, track outbreaks, and inform public health interventions. The COVID-19 pandemic accelerated the adoption of WBE, highlighting its value for early warning and real-time monitoring of viral spread, including SARS-CoV-2 and its variants, as well as other pathogens such as norovirus, enteric bacteria, and AMR genes [1] [10] [11].

### §4.2 Open source software in wastewater pathogen analysis

Open source software has become foundational in WBE, offering reproducible, transparent, and cost-effective solutions for complex data analysis. These tools enable the integration of molecular, sequencing, and biosensor data, supporting rapid detection, variant tracking, and comprehensive surveillance. Open source platforms foster collaboration, adaptability, and innovation, addressing the need for scalable and customizable workflows in diverse settings [1] [12].

## §5. Catalog of open source wastewater pathogen analysis software

### §5.1 Key open source projects and platforms

#### watermonitor

- **Description:** An open-source bioinformatic workflow for metatranscriptomic analysis, available at [GitHub](https://github.com/waterpt/watermonitor).
- **Features:** Rapid, accurate detection of human pathogenic viruses and bacteria; integrates AI-enhanced analysis; outperforms other workflows in speed and sensitivity.
- **Adoption:** Used in research and public health labs for scalable, reproducible monitoring [1].

#### WastPan (Finland)

- **Description:** National open-source WBE system combining culture-based and molecular methods (qPCR, NGS).
- **Scope:** Monitors viruses, bacteria, fungi, parasites, and AMR genes; validated protocols; covers 40% of Finland's population.
- **Significance:** Model for comprehensive, population-scale surveillance [2].

#### Encyclopaedia Cloacae (EU4S)

- **Description:** Digital platform cataloguing wastewater-detectable pathogens globally; provides geospatial analytics and continuous updates.
- **Role:** Supports public health surveillance and research across the EU [3].

#### Custom open-source pipelines

- **Examples:** Multiplex qPCR and metagenomic sequencing workflows, biosensor-integrated dashboards, and real-time analytics platforms.
- **Use cases:** Local and national public health risk assessment, rapid outbreak response [4] [5].

#### Other notable tools

- **Kraken2, PathoScope, ResPipe:** Taxonomic classification, AMR profiling, metagenomic analysis [6] [7].
- **Galaxy, EasyFlow:** GUI-based, reproducible workflows for non-programmers [8] [9].

### §5.2 Comparative features and usability

| Feature / aspect | Open source (e.g., watermonitor, Galaxy) | Commercial software |
|---|---|---|
| Cost | Free, no licensing | Expensive, licensing fees |
| Transparency | Full code access, modifiable | Proprietary, limited access |
| Flexibility | Highly customizable | Often rigid, less adaptable |
| Usability | Improving (GUIs, dashboards) | Often more polished |
| Reproducibility | High, community-verified | Variable |
| Data compatibility | Open formats, integrable | May support proprietary |
| Community support | Active, collaborative | Vendor-driven |

Open source workflows offer significant advantages in cost, transparency, and adaptability, with growing emphasis on user-friendly interfaces. Commercial tools may provide more polished experiences but are less flexible and often cost-prohibitive for large-scale or resource-limited applications [8] [9] [12] [13].

### §5.3 Integration of molecular and biosensor technologies

Modern open source platforms increasingly integrate molecular methods (qPCR, RT-qPCR, NGS) with biosensor technologies (e.g., electrochemical, graphene-based sensors) to enable rapid, sensitive, and field-deployable pathogen detection. These hybrid approaches facilitate near real-time surveillance, especially in settings lacking centralized laboratories [5] [14] [15] [16].

## §6. Methodologies and algorithms in open source wastewater pathogen detection

### §6.1 Bioinformatic algorithms for metagenomic and metatranscriptomic data

- **Kraken2, PathoScope, ResPipe:**
  - Used for taxonomic classification, AMR gene profiling, and metagenomic assembly.
  - Kraken2 and PathoScope outperform 16S amplicon tools for genus/species-level classification, especially with comprehensive databases [6].
  - ResPipe automates shotgun metagenomic data processing for AMR profiling [7].
- **Deep learning & genomic signal processing:**
  - CNNs applied to Z-Curve transformed viral genomes enable high-accuracy identification of closely related strains (e.g., SARS-CoV-2) [17].
- **Assembly strategies:**
  - Short-read: High accuracy for gene identification, limited contiguity.
  - Long-read: More contiguous assemblies, better for complex genomes.
  - Hybrid: Balances both, but may have higher misassembly rates [18] [19] [20].

### §6.2 Integration of molecular methods in computational pipelines

- **qPCR, RT-qPCR, dPCR:**
  - Provide rapid, sensitive, and specific quantification of pathogens.
  - dPCR offers improved accuracy and resistance to inhibitors [21] [22].
- **NGS (metagenomics, metatranscriptomics):**
  - Enables broad-spectrum detection, variant tracking, and community profiling.
  - Often qualitative/semi-quantitative; requires substantial computational resources [23] [24].
- **Combined pipelines:**
  - Leverage qPCR for quantification and NGS for diversity/novelty detection [23] [25].

### §6.3 Machine learning and advanced algorithms for low-abundance pathogen detection

- **Random forest, SVM, LSTM:**
  - Used for predictive modeling and time-series forecasting of pathogen loads [26].
- **Variant calling:**
  - BCFtools, FreeBayes, VarScan: High precision/recall for variant detection in mixed populations [27].
- **Hybrid-capture enrichment:**
  - Improves sensitivity for low-abundance and emerging viruses [28] [29].

### §6.4 Impact of sequencing and assembly strategies

| Strategy | Strengths | Weaknesses | Best use cases |
|---|---|---|---|
| Short-read | High accuracy, low cost | Limited contiguity, false positives | Quantification, variant calling |
| Long-read | Resolves complex genomes | Higher error rates, lower yield | Plasmid/ARG detection, diversity |
| Hybrid | Balances accuracy/contiguity | More complex, higher cost | Emerging pathogen discovery |

Hybrid approaches are most effective for reconstructing complete genomes and tracking emerging pathogens, but require careful optimization and sufficient sequencing depth [19] [20] [30].

## §7. Handling of known, unknown, and emerging pathogens

### §7.1 Detection strategies for known pathogens

- **Multiplex qPCR & digital PCR:**
  - High sensitivity/specificity for targeted detection of known pathogens and resistance genes [31] [32].
- **Probe capture enrichment:**
  - Enhances detection of known viruses, though complete genome recovery can be challenging for some targets [33].
- **Amplicon sequencing:**
  - Enables simultaneous detection and quantification of multiple targets [34].

### §7.2 Approaches for unknown and emerging pathogen detection

- **Untargeted metagenomics/metatranscriptomics:**
  - Broad, agnostic screening for novel pathogens at the genus/family level [1] [10].
- **Bioinformatic screening:**
  - Uses reference databases, de novo assembly, and phylogenetic placement to identify novel sequences [35] [36].
- **Enrichment methods:**
  - Probe capture and hybrid-capture sequencing improve sensitivity for low-abundance/emerging viruses [37].

### §7.3 Bioinformatic differentiation and lineage deconvolution

- **Lineage deconvolution pipelines:**
  - Tools like PiGx SARS-CoV-2 and Aquascope automate detection and quantification of viral lineages/variants [35] [38].
- **Phylogenetic placement:**
  - Tools such as WEPP achieve near-haplotype resolution, supporting early detection of variants [36].
- **Variant calling:**
  - High-precision algorithms (BCFtools, FreeBayes) are critical for accurate mutation assignment in mixed samples [27].

### §7.4 Effectiveness of enrichment and multithreshold bioinformatics

- **Probe capture enrichment:**
  - Streamlines virus recovery, reduces processing time, and increases sensitivity for emerging viruses [37].
- **Multithreshold bioinformatics:**
  - Optimized workflows improve sensitivity and accuracy, especially for low-abundance targets [24].
- **Limitations:**
  - Bacterial RNA and phage dominance in samples, incomplete genome recovery, and need for further methodological development [39].

## §8. Current limitations and gaps in open source wastewater pathogen analysis software

### §8.1 Standardization and data interpretation challenges

- **Sampling & processing:**
  - Diverse protocols lead to inconsistent recovery rates and hinder cross-study comparability [40] [41].
- **Reporting:**
  - Lack of standardized metadata, normalization, and visualization complicates interpretation and public health action [41] [42].
- **Data quality:**
  - Variability in population size, shedding rates, and sample degradation introduces uncertainty [43].

### §8.2 Sensitivity and specificity gaps in early detection

- **Low-abundance / emerging variants:**
  - Detection is limited by low prevalence, uneven genome coverage, and PCR inhibitors [44] [45].
- **False positives / negatives:**
  - Suboptimal probe panels and variant callers can misidentify mutations [27] [33].
- **Variant deconvolution:**
  - Mixed samples challenge accurate estimation of lineage abundance [46].

### §8.3 Addressing PCR inhibition and complex wastewater matrix effects

- **Sample preparation:**
  - Techniques include gel filtration, protein coagulation, adsorption-elution, and inhibitor removal kits [47] [48].
- **Digital PCR & isothermal amplification:**
  - dPCR and LAMP/CRISPR methods are more resistant to inhibitors [49] [50].
- **Internal controls:**
  - Use of amplification controls and dilution curves to assess inhibition [51].

### §8.4 Opportunities for future development

- **Standardization:**
  - Develop open, harmonized protocols for sampling, processing, and reporting [52].
- **Low-cost biosensors:**
  - Expand field-deployable, real-time detection platforms [53].
- **Data visualization & collaboration:**
  - Improve dashboards, open data sharing, and interdisciplinary networks [54].

## §9. Conclusion

### §9.1 Summary of key insights

- Open source software is central to modern wastewater pathogen surveillance, enabling rapid, scalable, and reproducible analysis of known, unknown, and emerging pathogens [1].
- Platforms like watermonitor, WastPan, and Encyclopaedia Cloacae exemplify the integration of molecular, sequencing, and biosensor technologies for comprehensive public health monitoring [1] [3].
- Advanced bioinformatic and machine learning algorithms enhance detection sensitivity, especially for low-abundance and novel pathogens [10].
- Major limitations include lack of standardization, sensitivity gaps for early detection, and challenges in data interpretation [40].

### §9.2 Future directions and recommendations

- **Standardize protocols:**
  Develop and disseminate open, validated protocols for all stages of WBE, from sampling to reporting [52].
- **Integrate real-time biosensors:**
  Combine portable biosensor data with cloud-based analytics for rapid outbreak detection and prediction [53].
- **Advance machine learning:**
  Expand the use of AI for anomaly detection, variant tracking, and predictive modeling in open source platforms [54].
- **Foster collaboration:**
  Build open data networks linking environmental, clinical, and public health stakeholders to maximize the impact of WBE [54].

## §10. References

1. Carneiro, J., Pascoal, F., Semedo, M., (...), Magalhães, C. (2023) Mapping human pathogens in wastewater using a metatranscriptomic approach. *Environmental Research*. https://doi.org/10.1016/j.envres.2023.116040
2. Tiwari, A., Lehto, K.-M., Paspaliari, D.K., (...), Pitkänen, T. (2024) Developing wastewater-based surveillance schemes for multiple pathogens: The WastPan project in Finland. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2024.171401
3. Hirvonen, A., Comero, S., Tavazzi, S., (...), Gawlik, B.M. (2025) "Encyclopaedia Cloacae"—Mapping Wastewaters from Pathogen A to Z. *Microorganisms*. https://doi.org/10.3390/microorganisms13081900
4. Msomi, N.S., Levy, J.I., Matteson, N.L., (...), Yousif, M. (2025) Wastewater-integrated pathogen surveillance dashboards enable real-time, transparent, and interpretable public health risk assessment and dissemination. *PLOS Global Public Health*. https://doi.org/10.1371/journal.pgph.0004443
5. Geiwitz, M., Page, O.R., Marello, T., (...), Burch, K.S. (2024) Graphene Multiplexed Sensor for Point-of-Need Viral Wastewater-Based Epidemiology. *ACS Applied Bio Materials*. https://doi.org/10.1021/acsabm.4c00484
6. Odom, A.R., Faits, T., Castro-Nallar, E., (...), Johnson, W.E. (2023) Metagenomic profiling pipelines improve taxonomic classification for 16S amplicon sequencing data. *Scientific Reports*. https://doi.org/10.1038/s41598-023-40799-x
7. Gweon, H.S., Shaw, L.P., Swann, J., (...), Woodford, N. (2019) The impact of sequencing depth on the inferred taxonomic composition and AMR gene content of metagenomic samples. *Environmental Microbiomes*. https://doi.org/10.1186/s40793-019-0347-1
8. Mendez, Kevin M., Pritchard, Leighton, Reinke, Stacey N., Broadhurst, David I. (2019) Toward collaborative open data science in metabolomics using Jupyter Notebooks and cloud computing. *Metabolomics*. https://doi.org/10.1007/s11306-019-1588-0
9. Ma, Yitong, Eizenberg-Magar, Inbal, Antebi, Yaron (2024) EasyFlow: An open-source, user-friendly cytometry analyzer with graphic user interface (GUI). *PLoS ONE*. https://doi.org/10.1371/journal.pone.0308873
10. Li, Y., Miyani, B., Faust, R.A., (...), Xagoraraki, I. (2024) A broad wastewater screening and clinical data surveillance for virus-related diseases in the metropolitan Detroit area in Michigan. *Human Genomics*. https://doi.org/10.1186/s40246-024-00581-0
11. Farkas, K., Williams, R.C., Hillary, L.S., (...), Jones, D.L. (2025) Harnessing the Power of Next-Generation Sequencing in Wastewater-Based Epidemiology and Global Disease Surveillance. *Food and Environmental Virology*. https://doi.org/10.1007/s12560-024-09616-0
12. Peeters, L., Beirnaert, C., van der Auwera, A., (...), Foubert, K. (2019) Revelation of the metabolic pathway of hederacoside C using an innovative data analysis strategy for dynamic multiclass biotransformation experiments. *Journal of Chromatography A*. https://doi.org/10.1016/j.chroma.2019.02.055
13. Srivastava, Nishtha, Sen, Anamika, Srivastava, Aastha, (...), Khare, Shubhra (2025) Cost-benefit analysis of automated water quality management: investment, savings, and strategic advantages. *Computational Automation for Water Security*. https://doi.org/10.1016/B978-0-443-33321-7.00021-4
14. Sarekoski, A., Lipponen, A., Hokajärvi, A.-M., (...), Pitkänen, T. (2024) Simultaneous biomass concentration and subsequent quantitation of multiple infectious disease agents and antimicrobial resistance genes from community wastewater. *Environment International*. https://doi.org/10.1016/j.envint.2024.108973
15. Singh, A., Dar, M.Y., Dwivedi, V. (2025) Wastewater-Based Epidemiology and Biosensor Technology: Emerging Tools for Environmental Risk Management. *Environmental Claims Journal*. https://doi.org/10.1080/10406026.2025.2554159
16. Jiménez-Rodríguez, M.G., Silva-Lance, F., Parra-Arroyo, L., (...), Sosa-Hernández, J.E. (2022) Biosensors for the detection of disease outbreaks through wastewater-based epidemiology. *TrAC - Trends in Analytical Chemistry*. https://doi.org/10.1016/j.trac.2022.116585
17. Adetiba, E., Abolarinwa, J.A., Adegoke, A.A., (...), Badejo, J.A. (2022) DeepCOVID-19: A model for identification of COVID-19 virus sequences with genomic signal processing and deep learning. *Cogent Engineering*. https://doi.org/10.1080/23311916.2021.2017580
18. Yorki, S., Shea, T., Cuomo, C.A., (...), Worby, C.J. (2023) Comparison of long- and short-read metagenomic assembly for low-abundance species and resistance genes. *Briefings in Bioinformatics*. https://doi.org/10.1093/bib/bbad050
19. Brown, Connor L., Keenum, Ishi M., Dai, Dongjuan, (...), Pruden, Amy (2099) Critical evaluation of short, long, and hybrid assembly for contextual analysis of antibiotic resistance genes in complex environmental metagenomes. *Scientific Reports*. https://doi.org/10.1038/s41598-021-83081-8
20. Commichaux, Seth, Javkar, Kiran, Ramachandran, Padmini, (...), Ottesen, Andrea (2021) *BMC Genomics*. https://doi.org/10.1186/s12864-021-07702-2
21. Tiwari, A., Ahmed, W., Oikarinen, S., (...), Bivins, A. (2022) Application of digital PCR for public health-related water quality monitoring. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2022.155663
22. Malla, B., Shrestha, S., Haramoto, E. (2024) Optimization of the 5-plex digital PCR workflow for simultaneous monitoring of SARS-CoV-2 and other pathogenic viruses in wastewater. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2023.169746
23. Zhao, Y., Huang, F., Wang, W., (...), Gao, S.-H. (2023) Application of high-throughput sequencing technologies and analytical tools for pathogen detection in urban water systems: Progress and future perspectives. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2023.165867
24. Carneiro, J., Pascoal, F., Semedo, M., (...), Magalhães, C. (2023) Mapping human pathogens in wastewater using a metatranscriptomic approach. *Environmental Research*. https://doi.org/10.1016/j.envres.2023.116040
25. Liu, S., Wang, C., Wang, P., (...), Yuan, Q. (2018) Variation of bacterioplankton community along an urban river impacted by touristic city: With a focus on pathogen. *Ecotoxicology and Environmental Safety*. https://doi.org/10.1016/j.ecoenv.2018.09.006
26. Ali, M., Younis, A.B., Duru, C.I., Sherchan, S.P. (2026) A review of AI/ML approaches in wastewater surveillance advancement. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2026.181364
27. Bassano, I., Ramachandran, V.K., Khalifa, M.S., (...), Grimsley, J.M.S. (2023) Evaluation of variant calling algorithms for wastewater-based epidemiology using mixed populations of SARS-CoV-2 variants in synthetic and wastewater samples. *Microbial Genomics*. https://doi.org/10.1099/mgen.0.000933
28. Child, H.T., Airey, G., Maloney, D.M., (...), Bassano, I. (2023) Comparison of metagenomic and targeted methods for sequencing human pathogenic viruses from wastewater. *mBio*. https://doi.org/10.1128/mbio.01468-23
29. Bellekom, B., Troman, C., Fitz, S., (...), Shaw, A.G. (2026) Comparison of the sensitivity of targeted and untargeted (metagenomic) methods for the detection of viral pathogens in wastewater. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2025.181333
30. Liu, M., Xu, N., Chen, B., (...), Qian, H. (2024) Effects of different assembly strategies on gene annotation in activated sludge. *Environmental Research*. https://doi.org/10.1016/j.envres.2024.119116
31. van Poelvoorde, L.A.E., Bogaerts, B., Vanneste, K., (...), Roosens, N. (2026) Suitability of concentration and extraction protocols for genomic applications in wastewater-based epidemiology. *Environmental Science: Water Research and Technology*. https://doi.org/10.1039/d5ew00930h
32. Suzuki, Y., Shimizu, H., Tamai, S., (...), Ishii, S. (2023) Simultaneous detection of various pathogenic Escherichia coli in water by sequencing multiplex PCR amplicons. *Environmental Monitoring and Assessment*. https://doi.org/10.1007/s10661-022-10863-6
33. Kantor, R.S., Jiang, M. (2024) Considerations and Opportunities for Probe Capture Enrichment Sequencing of Emerging Viruses from Wastewater. *Environmental Science and Technology*. https://doi.org/10.1021/acs.est.4c02638
34. Li, Y., Shi, X., Zuo, Y., (...), Wang, S. (2022) Multiplexed Target Enrichment Enables Efficient and In-Depth Analysis of Antimicrobial Resistome in Metagenomes. *Microbiology Spectrum*. https://doi.org/10.1128/spectrum.02297-22
35. Schumann, V.-F., de Castro Cuadrat, R.R., Wyler, E., (...), Akalin, A. (2022) SARS-CoV-2 infection dynamics revealed by wastewater sequencing analysis and deconvolution. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2022.158931
36. Gangwar, P., Katte, P., Bhat, M., Turakhia, Y. (2026) WEPP: Phylogenetic placement achieves near-haplotype resolution in wastewater-based epidemiology. *PLoS Computational Biology*. https://doi.org/10.1371/journal.pcbi.1014124
37. Brighton, K., Fisch, S., Wu, H., (...), Aw, T.G. (2024) Targeted community wastewater surveillance for SARS-CoV-2 and Mpox virus during a festival mass-gathering event. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2023.167443
38. Feistel, D.J., Welsh, R., Mercante, J., (...), Cornforth, D.M. (2025) Detection and Tracking of SARS-CoV-2 Lineages through National Wastewater Surveillance System Pathogen Genomics. *Emerging Infectious Diseases*. https://doi.org/10.3201/eid3113.241411
39. Sakkos, A., Saint-John, B., Tyml, T., (...), Schulz, F. (2026) Agnostic capture of pathogens for the detection and diagnostics of emerging threats. *iScience*. https://doi.org/10.1016/j.isci.2026.114684
40. Jiang, G., Liu, Y., Tang, S., (...), Meiman, J. (2023) Moving forward with COVID-19: Future research prospects of wastewater-based epidemiology methodologies and applications. *Current Opinion in Environmental Science and Health*. https://doi.org/10.1016/j.coesh.2023.100458
41. Servetas, S.L., Parratt, K.H., Brinkman, N.E., (...), Lin, N.J. (2022) Standards to support an enduring capability in wastewater surveillance for public health: Where are we? *Case Studies in Chemical and Environmental Engineering*. https://doi.org/10.1016/j.cscee.2022.100247
42. Sokoloski, Kevin J., Holm, Rochelle H., Smith, Melissa, (...), Smith, Ted (2023) What is the functional reach of wastewater surveillance for respiratory viruses, pathogenic viruses of concern, and bacterial antibiotic resistance genes of interest? *Human Genomics*. https://doi.org/10.1186/s40246-023-00563-8
43. McLeod, R.E., Julian, T.R., Stadler, T., Lison, A. (2026) Real-time outlier detection in digital PCR data for wastewater-based pathogen surveillance. *Environmental Research*. https://doi.org/10.1016/j.envres.2026.124269
44. Chen, X., Phan, T., Lee, W.L., (...), Wu, F. (2026) An integrated framework for early detection and transmissibility assessment of emerging variants in wastewater. *International Journal of Hygiene and Environmental Health*. https://doi.org/10.1016/j.ijheh.2026.114790
45. Lipponen, A., Kolehmainen, A., Oikarinen, S., (...), Räisänen, K. (2024) Detection of SARS-COV-2 variants and their proportions in wastewater samples using next-generation sequencing in Finland. *Scientific Reports*. https://doi.org/10.1038/s41598-024-58113-8
46. Karthikeyan, S., Levy, J.I., de Hoff, P., (...), Knight, R. (2022) Wastewater sequencing reveals early cryptic SARS-CoV-2 variant transmission. *Nature*. https://doi.org/10.1038/s41586-022-05049-6
47. Sidhu, J.P.S., Ahmed, W., Toze, S. (2013) Sensitive detection of human adenovirus from small volume of primary wastewater samples by quantitative PCR. *Journal of Virological Methods*. https://doi.org/10.1016/j.jviromet.2012.11.002
48. Zafeiriadou, Anastasia, Kaltsis, Lazaros, Thomaidis, Nikolaos S., Markou, Athina (2024) Simultaneous detection of influenza A, B and respiratory syncytial virus in wastewater samples by one-step multiplex RT-ddPCR assay. *Human Genomics*. https://doi.org/10.1186/s40246-024-00614-8
49. de la Cruz Barron, Magali, Kneis, David, Geissler, Michael, (...), Berendonk, Thomas U. (2023) Evaluating the sensitivity of droplet digital PCR for the quantification of SARS-CoV-2 in wastewater. *Frontiers in Public Health*. https://doi.org/10.3389/fpubh.2023.1271594
50. Song, D., Xu, C., Sang, P., (...), Huang, X. (2025) Rapid and contamination-free detection of cucumber green mottle mosaic virus as a viral indicator in wastewater via UDG-RT-LAMP combined with CRISPR/Cas12a. *Journal of Hazardous Materials*. https://doi.org/10.1016/j.jhazmat.2025.139571
51. Wannigama, D.L., Amarasiri, M., Sano, D., Hamamoto, H. (2026) Tracking Mpox through wastewater: advances in environmental surveillance and analytical methodologies. *Methods in Microbiology*. https://doi.org/10.1016/bs.mim.2026.02.001
52. Robins, K., Leonard, A.F.C., Farkas, K., (...), McIntyre-Nolan, S. (2022) Research needs for optimising wastewater-based epidemiology monitoring for public health protection. *Journal of Water and Health*. https://doi.org/10.2166/wh.2022.026
53. Gholipour, S., Shamsizadeh, Z., Halabowski, D., (...), Nikaeen, M. (2024) Combating antibiotic resistance using wastewater surveillance: Significance, applications, challenges, and future directions. *Science of the Total Environment*. https://doi.org/10.1016/j.scitotenv.2023.168056
54. Sokoloski, K.J., Holm, R.H., Smith, M., (...), Smith, T. (2023) What is the functional reach of wastewater surveillance for respiratory viruses, pathogenic viruses of concern, and bacterial antibiotic resistance genes of interest? *Human Genomics*. https://doi.org/10.1186/s40246-023-00563-8
