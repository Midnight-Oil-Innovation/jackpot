import logging

logger = logging.getLogger(__name__)


async def run_scrubber_queue_job() -> None:
    """
    Auto-deny scrub override requests pending for > 48 hours.
    Conservative default: if Lab Director doesn't decide, scrubber runs.
    Implement fully when scrub override workflow is built (Month 2).
    """
    logger.info("run_scrubber_queue_job: not yet implemented")


async def run_access_request_job() -> None:
    """
    Auto-approve access requests where auto_approve_after <= NOW().
    Send 75-day warnings, 7-day expiry warnings, expire granted access.
    Mark pending requests moot where sharing_level = PUBLIC.
    Implement fully when access request workflow is built (Month 1).
    """
    logger.info("run_access_request_job: not yet implemented")
