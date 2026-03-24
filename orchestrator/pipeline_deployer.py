"""Phase 4: Deployment - Deploy pipelines to Observo and upload to GitHub."""

import asyncio
import logging
from typing import List, Dict
from datetime import datetime
from pathlib import Path

from utils.logger import ConversionLogger
from .utils import save_json, build_manifest_metadata

logger = logging.getLogger(__name__)


async def deploy_and_upload(
    observo_client,
    github_automation,
    output_manager,
    validator,
    metadata_builder,
    rag_assistant,
    lua_parsers: List[Dict],
    config: Dict,
    statistics: Dict,
    output_dir: Path
) -> List[Dict]:
    """
    Phase 4: Validate, deploy to Observo and upload to GitHub.

    DIRECTOR REQUIREMENT 4: Validate JSON via upload/testing
    DIRECTOR REQUIREMENT 5: Extract same fields as original parsers
    DIRECTOR REQUIREMENT 6: Add AI-SIEM metadata

    Args:
        observo_client: ObservoAPIClient instance
        github_automation: ClaudeGitHubAutomation instance
        output_manager: ParserOutputManager instance
        validator: PipelineValidator instance
        metadata_builder: AISIEMMetadataBuilder instance
        rag_assistant: ClaudeRAGAssistant instance
        lua_parsers: List of Lua generation results from Phase 3
        config: Configuration dictionary
        statistics: Statistics tracking dictionary
        output_dir: Output directory path

    Returns:
        List of deployment results

    Raises:
        Exception: If deployment fails
    """
    phase_start = datetime.now()
    ConversionLogger.log_phase(
        "4: DEPLOY",
        f"Validating and deploying {len(lua_parsers)} pipelines to Observo.ai"
    )

    deployment_results = []

    try:
        async with observo_client, github_automation:
            for i, parser in enumerate(lua_parsers, 1):
                logger.info(f"Processing {i}/{len(lua_parsers)}: {parser['parser_id']}")

                try:
                    # REQUIREMENT 6: Build complete AI-SIEM metadata
                    complete_metadata = metadata_builder.build_complete_metadata(
                        parser_id=parser['parser_id'],
                        parser_config=parser.get("config", {}),
                        analysis_data=parser.get("analysis", {}),
                        lua_code=parser["lua_code"],
                        conversion_metadata={
                            "fields_extracted": parser.get("fields_extracted", []),
                            "ocsf_classification": parser.get("ocsf_classification", {}),
                            "source_info": {
                                "repository": "sentinel-one/ai-siem",
                                "parser_type": parser.get("parser_type", "unknown"),
                                "source_type": parser.get("source_type", "unknown")
                            }
                        }
                    )

                    # Build complete pipeline JSON for validation and deployment
                    pipeline_json = await observo_client.build_pipeline_json(
                        parser,
                        parser["lua_code"],
                        complete_metadata
                    )

                    # REQUIREMENTS 4 & 5: Comprehensive validation
                    validation_results = validator.validate_complete_pipeline(
                        parser_id=parser['parser_id'],
                        pipeline_json=pipeline_json,
                        lua_code=parser["lua_code"],
                        original_parser_config=parser.get("config", {}),
                        sample_events=parser.get("sample_events", [])
                    )

                    # Log validation status
                    if validation_results["overall_status"] == "failed":
                        logger.warning(
                            f"Validation failed for {parser['parser_id']}: "
                            f"{validation_results['error_count']} errors"
                        )

                    # Deploy to Observo.ai (even if validation has warnings)
                    deployment_result = await observo_client.deploy_validated_pipeline(
                        pipeline_json,
                        validation_results
                    )

                    # Generate documentation
                    documentation = await rag_assistant.generate_pipeline_documentation(
                        parser["parser_id"],
                        pipeline_json,
                        parser["lua_code"],
                        complete_metadata
                    )

                    # REQUIREMENT 3: Save all per-parser artifacts (4 files)
                    manifest_metadata = build_manifest_metadata(parser, validation_results, config, mode="stable")
                    output_manager.save_manifest(parser['parser_id'], manifest_metadata, mode="stable")
                    if parser.get("canary_config", {}).get("enabled"):
                        canary_manifest = build_manifest_metadata(parser, validation_results, config, mode="canary")
                        output_manager.save_manifest(parser['parser_id'], canary_manifest, mode="canary")

                    artifact_paths = output_manager.save_all_artifacts(
                        parser_id=parser['parser_id'],
                        analysis_data={
                            **parser,
                            "template_used": parser.get("selected_template"),
                            "validation_status": validation_results["overall_status"]
                        },
                        lua_code=parser["lua_code"],
                        pipeline_data=pipeline_json,
                        validation_results=validation_results,
                        manifest_data=manifest_metadata,
                    )

                    logger.info(
                        f"[OK] Saved artifacts for {parser['parser_id']}: "
                        f"{len(artifact_paths)} files"
                    )

                    # Upload to GitHub
                    github_result = await github_automation.upload_pipeline_files(
                        parser["parser_id"],
                        parser["lua_code"],
                        documentation,
                        deployment_result,
                        parser
                    )

                    # Combine results
                    result = {
                        **parser,
                        "metadata": complete_metadata,
                        "validation": validation_results,
                        "deployment": deployment_result,
                        "github": github_result,
                        "documentation": documentation,
                        "artifact_paths": {k: str(v) for k, v in artifact_paths.items()},
                        "processed_at": datetime.now().isoformat()
                    }

                    deployment_results.append(result)

                    statistics["pipelines_deployed"] += 1
                    statistics["github_uploads"] += 1

                    ConversionLogger.log_parser_conversion(
                        parser["parser_id"],
                        "deployed",
                        pipeline_id=deployment_result.get("pipeline_id")
                    )

                    # Delay between deployments
                    deployment_delay = config.get("processing", {}).get("deployment_delay", 5.0)
                    await asyncio.sleep(deployment_delay)

                except Exception as e:
                    logger.error(f"Failed to process {parser['parser_id']}: {e}")
                    statistics["errors"].append(f"{parser['parser_id']}: {str(e)}")
                    continue

        # Create repository index
        await github_automation.create_repository_index(deployment_results)

        statistics["phase_timings"]["phase_4"] = (datetime.now() - phase_start).total_seconds()

        # Save deployment results
        save_json(deployment_results, str(output_dir / "04_deployment_results.json"))

        ConversionLogger.log_phase(
            "4: DEPLOY",
            f"Completed - {len(deployment_results)} pipelines deployed and uploaded",
            count=len(deployment_results)
        )

        return deployment_results

    except Exception as e:
        logger.error(f"Phase 4 failed: {e}")
        raise
