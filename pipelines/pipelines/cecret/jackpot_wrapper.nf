// JACKPOT wrapper for UPHL-BioNGS/Cecret.
//
// This wrapper runs the upstream Cecret pipeline, then invokes the
// Python parsers in `parsers/` against the output directory, then
// POSTs every ParsedResult back through `shared.jackpot_register_client`.
//
// Expected at runtime (supplied by the launch endpoint via a per-run
// jackpot_run.config):
//   params.jackpot_run_id
//   params.jackpot_api_url
//   params.jackpot_pipeline_token
//   params.jackpot_pipeline_version   // e.g. "3.66"
//   params.cecret_outdir
//
// Register phase is a single Python entrypoint so retries happen in
// one place and partial-failure is preserved in pipeline_events.

nextflow.enable.dsl = 2

include { CECRET } from 'UPHL-BioNGS/Cecret'

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
    uv run --project ${workflow.projectDir} python -m pipelines.cecret.register \\
        --output-dir ${outdir} \\
        --pipeline-version ${pipeline_version} \\
        --run-id ${run_id} 2>&1 | tee register.log
    """
}

workflow {
    CECRET()
    REGISTER_RESULTS(
        CECRET.out.outdir,
        params.jackpot_run_id,
        params.jackpot_pipeline_version,
    )
}
