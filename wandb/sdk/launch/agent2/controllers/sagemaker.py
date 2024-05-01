import asyncio
import logging
from typing import Any, List

from ..._project_spec import LaunchProject
from ...queue_driver.standard_queue_driver import StandardQueueDriver
from ..controller import LaunchControllerConfig, LegacyResources
from ..jobset import JobSet, JobWithQueue
from .base import WANDB_JOBSET_DISCOVERABILITY_LABEL, BaseManager
from .util import parse_max_concurrency

DEFAULT_MAX_CONCURRENCY = 1000


async def sagemaker_controller(
    config: LaunchControllerConfig,
    jobset: JobSet,
    logger: logging.Logger,
    shutdown_event: asyncio.Event,
    legacy: LegacyResources,
    scheduler_queue: "asyncio.Queue[JobWithQueue]",
):
    iter = 0
    max_concurrency = parse_max_concurrency(config, DEFAULT_MAX_CONCURRENCY)

    logger.debug(
        f"Starting SageMaker controller with max_concurrency={max_concurrency}"
    )

    mgr = SageMakerManager(
        config, jobset, logger, legacy, scheduler_queue, max_concurrency
    )

    while not shutdown_event.is_set():
        await mgr.reconcile()
        await asyncio.sleep(5)
        iter += 1

    return None


class SageMakerManager(BaseManager):
    """Maintains state for multiple SageMaker jobs."""

    resource_type = "sagemaker"

    def __init__(
        self,
        config: LaunchControllerConfig,
        jobset: JobSet,
        logger: logging.Logger,
        legacy: LegacyResources,
        scheduler_queue: "asyncio.Queue[JobWithQueue]",
        max_concurrency: int,
    ):
        self.queue_driver = StandardQueueDriver(jobset.api, jobset, logger)
        super().__init__(
            config, jobset, logger, legacy, scheduler_queue, max_concurrency
        )

        # TODO: find orphaned jobs in resource and assign to self

    async def find_orphaned_jobs(self) -> List[Any]:
        raise NotImplementedError("SageMakerManager.find_orphaned_jobs not implemented")

    def label_job(self, project: LaunchProject) -> None:
        resource_block = self._get_resource_block(project)
        if resource_block is None:
            return
        jobset_label = self._construct_jobset_discoverability_label()
        # add to tags for job
        _tags = resource_block.get("Tags", [])
        _tags.append({"Key": WANDB_JOBSET_DISCOVERABILITY_LABEL, "Value": jobset_label})
        resource_block["Tags"] = _tags
