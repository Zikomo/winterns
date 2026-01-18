"""Main execution orchestrator - runs winterns through the full pipeline.

The pipeline flow:
1. Interpret context → search queries
2. Search all sources for each query
3. Deduplicate against SeenContent
4. Curate content (filter to 60+ score)
5. Record seen content
6. Compose digest
7. Deliver to all channels
8. Complete run, update next_run_at
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import structlog

from wintern.agents import (
    ComposerInput,
    CuratedContent,
    CuratorInput,
    InterpretedContext,
    InterpreterInput,
    ScoredItem,
    ScrapedItem,
    UserContext,
    compose_digest,
    curate_content,
    interpret_context,
)
from wintern.agents.composer import DeliveryChannel as AgentDeliveryChannel
from wintern.delivery.schemas import DeliveryItem, DeliveryPayload
from wintern.execution import service as execution_service
from wintern.execution.factories import (
    UnsupportedDeliveryError,
    UnsupportedSourceError,
    create_data_source,
    create_delivery_channel,
)
from wintern.sources.schemas import SearchResult
from wintern.winterns.models import DeliveryType

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


log = structlog.get_logger()


# -----------------------------------------------------------------------------
# Custom Exceptions
# -----------------------------------------------------------------------------


class ExecutionError(Exception):
    """Base exception for execution errors."""

    pass


class NoSourcesConfiguredError(ExecutionError):
    """Raised when a wintern has no active sources configured."""

    def __init__(self, wintern_id: uuid.UUID) -> None:
        self.wintern_id = wintern_id
        super().__init__(f"Wintern {wintern_id} has no active sources configured")


class NoDeliveryConfiguredError(ExecutionError):
    """Raised when a wintern has no active delivery channels configured."""

    def __init__(self, wintern_id: uuid.UUID) -> None:
        self.wintern_id = wintern_id
        super().__init__(f"Wintern {wintern_id} has no active delivery channels configured")


class NoContentFoundError(ExecutionError):
    """Raised when no content was found during execution."""

    def __init__(self, wintern_id: uuid.UUID) -> None:
        self.wintern_id = wintern_id
        super().__init__(f"No content found for wintern {wintern_id}")


# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------


def scored_item_to_delivery_item(item: ScoredItem) -> DeliveryItem:
    """Convert a ScoredItem from curator to DeliveryItem for delivery.

    Args:
        item: The scored item from the curator agent.

    Returns:
        A DeliveryItem ready for the delivery payload.
    """
    return DeliveryItem(
        url=item.url,
        title=item.title,
        relevance_score=item.relevance_score,
        reasoning=item.reasoning,
        key_excerpt=item.key_excerpt,
    )


def delivery_type_to_agent_channel(delivery_type: DeliveryType) -> AgentDeliveryChannel:
    """Convert a DeliveryType enum to the agent's DeliveryChannel enum.

    Args:
        delivery_type: The delivery type from the database model.

    Returns:
        The corresponding agent DeliveryChannel.
    """
    match delivery_type:
        case DeliveryType.SLACK:
            return AgentDeliveryChannel.SLACK
        case DeliveryType.EMAIL:
            return AgentDeliveryChannel.EMAIL
        case DeliveryType.SMS:
            return AgentDeliveryChannel.SMS


def search_result_to_scraped_item(result: SearchResult) -> ScrapedItem:
    """Convert a SearchResult to a ScrapedItem for the curator.

    Args:
        result: The search result from a data source.

    Returns:
        A ScrapedItem for the curator agent.
    """
    return ScrapedItem(
        url=result.url,
        title=result.title,
        snippet=result.snippet,
        source=result.source,
        published_date=result.published_at.isoformat() if result.published_at else None,
    )


# -----------------------------------------------------------------------------
# Main Execution Orchestrator
# -----------------------------------------------------------------------------


async def execute_wintern(
    session: AsyncSession,
    wintern_id: uuid.UUID,
) -> uuid.UUID:
    """Execute a wintern through the full pipeline.

    This is the main entry point for running a wintern. It orchestrates:
    1. Create & start WinternRun
    2. Validate active sources/deliveries
    3. Interpret context → search queries
    4. Search all sources for each query
    5. Deduplicate against SeenContent
    6. Curate content (filter to 60+ score)
    7. Record seen content
    8. Compose digest
    9. Deliver to all channels
    10. Complete run, update next_run_at

    Args:
        session: The database session.
        wintern_id: The ID of the wintern to execute.

    Returns:
        The UUID of the created WinternRun.

    Raises:
        ExecutionError: If the wintern cannot be found or execution fails.
        NoSourcesConfiguredError: If no active sources are configured.
        NoDeliveryConfiguredError: If no active delivery channels are configured.
    """
    # Load wintern with relationships
    wintern = await execution_service.get_wintern_for_execution(session, wintern_id)
    if not wintern:
        raise ExecutionError(f"Wintern {wintern_id} not found")

    # Create run record
    run = await execution_service.create_run(session, wintern_id)
    run_id = run.id

    # Track metadata throughout execution
    metadata: dict = {
        "total_searched": 0,
        "new_content": 0,
        "curated": 0,
        "source_errors": [],
        "deliveries": [],
    }

    try:
        # Start the run
        await execution_service.start_run(session, run)

        # Validate we have sources and delivery channels
        active_sources = [s for s in wintern.source_configs if s.is_active]
        active_deliveries = [d for d in wintern.delivery_configs if d.is_active]

        if not active_sources:
            raise NoSourcesConfiguredError(wintern_id)

        if not active_deliveries:
            raise NoDeliveryConfiguredError(wintern_id)

        # Step 1: Interpret context
        log.info("Interpreting context", wintern_id=str(wintern_id), run_id=str(run_id))
        interpreter_input = InterpreterInput(context=wintern.context)
        interpret_result = await interpret_context(interpreter_input)
        interpreted_context: InterpretedContext = interpret_result.output

        log.info(
            "Context interpreted",
            wintern_id=str(wintern_id),
            queries=len(interpreted_context.search_queries),
        )

        # Step 2: Search all sources for each query
        all_results: list[SearchResult] = []
        for source_config in active_sources:
            try:
                source = create_data_source(source_config)
                for query in interpreted_context.search_queries:
                    try:
                        results = await source.search(query, count=10)
                        all_results.extend(results)
                        log.debug(
                            "Search completed",
                            source=source.source_name,
                            query=query,
                            results=len(results),
                        )
                    except Exception as e:
                        error_msg = f"{source.source_name}: {e}"
                        metadata["source_errors"].append(error_msg)
                        log.warning(
                            "Search query failed",
                            source=source.source_name,
                            query=query,
                            error=str(e),
                        )
            except UnsupportedSourceError as e:
                metadata["source_errors"].append(str(e))
                log.warning("Unsupported source type", error=str(e))

        metadata["total_searched"] = len(all_results)
        log.info(
            "Search phase complete",
            wintern_id=str(wintern_id),
            total_results=len(all_results),
        )

        # Step 3: Deduplicate against SeenContent
        seen_hashes = await execution_service.get_seen_hashes(session, wintern_id)
        new_results: list[SearchResult] = []
        for result in all_results:
            content_hash = execution_service.compute_content_hash(result.url)
            if content_hash not in seen_hashes:
                new_results.append(result)
                seen_hashes.add(content_hash)  # Prevent duplicates within this batch

        metadata["new_content"] = len(new_results)
        log.info(
            "Deduplication complete",
            wintern_id=str(wintern_id),
            new_content=len(new_results),
            duplicates_removed=len(all_results) - len(new_results),
        )

        # Handle case where no new content was found
        if not new_results:
            log.info("No new content found", wintern_id=str(wintern_id))
            # Complete run with empty digest
            await execution_service.complete_run(
                session,
                run,
                digest_content="No new content found.",
                metadata=metadata,
            )
            await execution_service.update_next_run_at(session, wintern)
            return run_id

        # Step 4: Curate content
        log.info("Curating content", wintern_id=str(wintern_id), items=len(new_results))
        scraped_items = [search_result_to_scraped_item(r) for r in new_results]
        curator_input = CuratorInput(
            interpreted_context=interpreted_context,
            items=scraped_items,
        )
        curate_result = await curate_content(curator_input)
        curated_content: CuratedContent = curate_result.output

        metadata["curated"] = len(curated_content.items)
        log.info(
            "Curation complete",
            wintern_id=str(wintern_id),
            curated_items=len(curated_content.items),
        )

        # Step 5: Record seen content (all new content, not just curated)
        items_to_record = [(r.url, r.source) for r in new_results]
        await execution_service.record_seen_content_batch(
            session, wintern_id, run_id, items_to_record
        )

        # Handle case where no content passed curation
        if not curated_content.items:
            log.info("No content passed curation", wintern_id=str(wintern_id))
            await execution_service.complete_run(
                session,
                run,
                digest_content="No relevant content found after curation.",
                metadata=metadata,
            )
            await execution_service.update_next_run_at(session, wintern)
            return run_id

        # Step 6: Compose digest
        # Use the first delivery channel type for composition, then deliver to all
        primary_delivery_type = active_deliveries[0].delivery_type
        agent_channel = delivery_type_to_agent_channel(primary_delivery_type)

        composer_input = ComposerInput(
            curated_content=curated_content,
            channel=agent_channel,
            user_context=UserContext(),  # TODO: Load user context if available
            research_topic=wintern.context[:200],  # Truncate for digest
        )
        compose_result = await compose_digest(composer_input)
        digest_content = compose_result.output

        log.info(
            "Digest composed",
            wintern_id=str(wintern_id),
            subject=digest_content.subject,
            item_count=digest_content.item_count,
        )

        # Step 7: Deliver to all channels
        delivery_items = [scored_item_to_delivery_item(item) for item in curated_content.items]
        payload = DeliveryPayload(
            subject=digest_content.subject,
            body=digest_content.body_slack,  # Use Slack format for now
            items=delivery_items,
        )

        for delivery_config in active_deliveries:
            try:
                channel = create_delivery_channel(delivery_config)
                result = await channel.deliver(payload)
                metadata["deliveries"].append({
                    "channel": result.channel,
                    "success": result.success,
                    "error": result.error_message,
                })
                log.info(
                    "Delivery complete",
                    channel=result.channel,
                    success=result.success,
                    error=result.error_message,
                )
            except UnsupportedDeliveryError as e:
                metadata["deliveries"].append({
                    "channel": delivery_config.delivery_type.value,
                    "success": False,
                    "error": str(e),
                })
                log.warning("Unsupported delivery type", error=str(e))
            except Exception as e:
                metadata["deliveries"].append({
                    "channel": delivery_config.delivery_type.value,
                    "success": False,
                    "error": str(e),
                })
                log.error(
                    "Delivery failed",
                    channel=delivery_config.delivery_type.value,
                    error=str(e),
                )

        # Step 8: Complete run and update next_run_at
        await execution_service.complete_run(
            session,
            run,
            digest_content=digest_content.body_plain,
            metadata=metadata,
        )
        await execution_service.update_next_run_at(session, wintern)

        log.info(
            "Wintern execution complete",
            wintern_id=str(wintern_id),
            run_id=str(run_id),
            curated=metadata["curated"],
        )

        return run_id

    except NoSourcesConfiguredError:
        await execution_service.fail_run(
            session, run, "No active sources configured", metadata=metadata
        )
        # Advance to next scheduled time to avoid retry spam
        await execution_service.update_next_run_at(session, wintern)
        raise
    except NoDeliveryConfiguredError:
        await execution_service.fail_run(
            session, run, "No active delivery channels configured", metadata=metadata
        )
        # Advance to next scheduled time to avoid retry spam
        await execution_service.update_next_run_at(session, wintern)
        raise
    except Exception as e:
        log.error(
            "Wintern execution failed",
            wintern_id=str(wintern_id),
            run_id=str(run_id),
            error=str(e),
        )
        await execution_service.fail_run(
            session, run, str(e), metadata=metadata
        )
        # Advance to next scheduled time to avoid retry spam
        await execution_service.update_next_run_at(session, wintern)
        raise ExecutionError(f"Execution failed: {e}") from e
