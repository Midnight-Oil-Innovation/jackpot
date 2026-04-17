// JACKPOT wrapper for UPHL-BioNGS/walkercreek.
//
// Runs walkercreek (influenza / RSV via IRMA), then registers the
// per-sample typing summary through the JACKPOT register client.
// Per-segment consensus FASTAs are staged separately.

nextflow.enable.dsl = 2

include { WALKERCREEK } from 'UPHL-BioNGS/walkercreek'

process REGISTER_RESULTS {
    tag "register:${run_id}"
    label 'jackpot_register'

    input:
    path outdir
    val run_id
    val pipeline_version

    output:
    path "register.log"

    script:
    """
    export JACKPOT_API_URL='${params.jackpot_api_url}'
    export JACKPOT_RUN_ID='${run_id}'
    export JACKPOT_PIPELINE_TOKEN='${params.jackpot_pipeline_token}'
    uv run --project ${workflow.projectDir} python -m pipelines.walkercreek.register \\
        --output-dir ${outdir} \\
        --pipeline-version ${pipeline_version} \\
        --run-id ${run_id} 2>&1 | tee register.log
    """
}

workflow {
    WALKERCREEK()
    REGISTER_RESULTS(
        WALKERCREEK.out.outdir,
        params.jackpot_run_id,
        params.jackpot_pipeline_version,
    )
}
