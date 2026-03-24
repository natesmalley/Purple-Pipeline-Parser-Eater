"""Component initialization for orchestrator."""

import logging
from typing import Dict
from anthropic import AsyncAnthropic

from components.github_scanner import GitHubParserScanner
from components.claude_analyzer import ClaudeParserAnalyzer
from components.lua_generator import ClaudeLuaGenerator
from components.rag_knowledge import RAGKnowledgeBase
from components.rag_assistant import ClaudeRAGAssistant
from components.observo_client import ObservoAPIClient
from components.github_automation import ClaudeGitHubAutomation
from utils.error_handler import ConversionError

logger = logging.getLogger(__name__)


async def initialize_components(config: Dict) -> Dict[str, object]:
    """
    Initialize all components with async support.

    Args:
        config: Configuration dictionary

    Returns:
        Dictionary of initialized components

    Raises:
        ConversionError: If component initialization fails
    """
    logger.info("[INIT] Initializing components...")

    try:
        components = {}

        # Initialize Claude client
        anthropic_config = config.get("anthropic", {})
        components["claude_client"] = AsyncAnthropic(api_key=anthropic_config.get("api_key"))

        # Initialize scanner
        github_token = config.get("github", {}).get("token")
        components["scanner"] = GitHubParserScanner(github_token, config)

        # Initialize analyzer
        components["analyzer"] = ClaudeParserAnalyzer(config)

        # Initialize LUA generator
        components["lua_generator"] = ClaudeLuaGenerator(config)

        # Initialize RAG knowledge base
        components["knowledge_base"] = RAGKnowledgeBase(config)
        if components["knowledge_base"].enabled:
            # Ingest Observo.ai documentation
            components["knowledge_base"].ingest_observo_documentation()

        # Initialize RAG assistant
        components["rag_assistant"] = ClaudeRAGAssistant(config, components["knowledge_base"])

        # Initialize Observo client
        components["observo_client"] = ObservoAPIClient(config, components["claude_client"])

        # Initialize GitHub automation
        components["github_automation"] = ClaudeGitHubAutomation(config, components["claude_client"])

        logger.info("[OK] All components initialized successfully")
        return components

    except Exception as e:
        logger.error(f"Component initialization failed: {e}")
        raise ConversionError(f"Initialization failed: {e}")
