nextflow.enable.dsl = 2

// Ingest gate pipeline — runs SRA-human-scrubber on every uploaded FASTQ.
// Triggered via Cloud Pub/Sub when files land in the staging bucket.
// See Section 14 of jackpot_architecture_v4.md for full documentation.

params.staging_bucket   = "gs://${System.env.PROJECT_ID}-staging"
params.sequences_bucket = "gs://${System.env.PROJECT_ID}-sequences"
params.api_url          = System.env.JACKPOT_API_URL ?: "http://localhost:8000"

process SCRUB_HUMAN_READS {
    container   "ncbi/sra-human-scrubber:latest"
    errorStrategy "retry"
    maxRetries 2

    input:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path(r1), path(r2_or_empty)

    output:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path("${sample_id}_R1_scrubbed.fastq.gz"),
          path("${sample_id}_R2_scrubbed.fastq.gz"), optional: true

    script:
    def r2_cmd = r2_or_empty.name != "empty" ? """
        scrub_human_data --input ${r2_or_empty} \
            --output ${sample_id}_R2_scrubbed.fastq.gz
    """ : ""
    """
    scrub_human_data --input ${r1} \
        --output ${sample_id}_R1_scrubbed.fastq.gz
    ${r2_cmd}
    """
}

process REGISTER_AND_MOVE {
    input:
    tuple val(sample_id), val(org_slug), val(lab_prefix),
          path(r1_scrubbed), path(r2_scrubbed)

    script:
    def r2_dest = r2_scrubbed.name != "empty" ?
        "${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r2_scrubbed}" : ""
    """
    gcloud storage cp ${r1_scrubbed} \
        ${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r1_scrubbed}

    if [ -n "${r2_dest}" ]; then
        gcloud storage cp ${r2_scrubbed} ${r2_dest}
    fi

    curl -s -X PATCH ${params.api_url}/api/v1/samples/${sample_id}/scrub-status \
        -H "Content-Type: application/json" \
        -d "{\"scrub_status\":\"COMPLETE\",\"fastq_r1_uri\":\"${params.sequences_bucket}/${org_slug}/${lab_prefix}/${sample_id}/${r1_scrubbed}\",\"fastq_r2_uri\":\"${r2_dest}\"}"
    """
}

workflow {
    Channel
        .fromPath("${params.staging_bucket}/**/*.fastq.gz")
        .map { f ->
            def parts = f.parent.toString().split("/")
            tuple(parts[-1], parts[-3], parts[-2], f)
        }
        .groupTuple(by: [0, 1, 2])
        .map { sid, org, lab, files ->
            def r1 = files.find { it.name.contains("_R1") } ?: files[0]
            def r2 = files.find { it.name.contains("_R2") } ?: file("empty")
            tuple(sid, org, lab, r1, r2)
        }
        | SCRUB_HUMAN_READS
        | REGISTER_AND_MOVE
}
