// JACKPOT wrapper for nf-core/viralrecon.
//
// Runs viralrecon, then invokes `pipelines.viralrecon.register` to
// POST every ParsedResult back through the JACKPOT register client.
// Wastewater-mode runs additionally register per-lineage Freyja
// abundances — that branch is exercised by setting
// `params.viralrecon_wastewater = true`.

nextflow.enable.dsl = 2

include { VIRALRECON } from 'nf-core/viralrecon'

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
    uv run --project ${workflow.projectDir} python -m pipelines.viralrecon.register \\
        --output-dir ${outdir} \\
        --pipeline-version ${pipeline_version} \\
        --run-id ${run_id} 2>&1 | tee register.log
    """
}

workflow {
    VIRALRECON()
    REGISTER_RESULTS(
        VIRALRECON.out.outdir,
        params.jackpot_run_id,
        params.jackpot_pipeline_version,
    )
}
