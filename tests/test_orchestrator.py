"""
Test suite for ConversionSystemOrchestrator
"""
import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
import yaml

# Assuming the orchestrator is in parent directory
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from orchestrator import ConversionSystemOrchestrator


@pytest.fixture
def mock_config():
    """Mock configuration"""
    return {
        "anthropic": {
            "api_key": "test-api-key",
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 4000,
            "temperature": 0.1,
            "rate_limit_delay": 0.1
        },
        "observo": {
            "api_key": "test-observo-key",
            "base_url": "https://api.observo.ai/v1",
            "rate_limit_delay": 0.1
        },
        "github": {
            "token": "test-github-token",
            "target_repo_owner": "test-owner",
            "target_repo_name": "test-repo"
        },
        "milvus": {
            "host": "localhost",
            "port": "19530"
        },
        "processing": {
            "max_parsers": 5,
            "parser_types": ["community"],
            "batch_size": 2,
            "max_concurrent": 1,
            "rate_limit_delay": 0.1,
            "deployment_delay": 0.1
        },
        "logging": {
            "level": "DEBUG",
            "file": "test_conversion.log"
        }
    }


@pytest.fixture
def mock_parser():
    """Mock parser data"""
    return {
        "parser_id": "test_parser",
        "parser_name": "test_parser",
        "source_path": "parsers/community/test_parser",
        "config": {
            "attributes": {"dataSource.vendor": "Test"},
            "formats": [{"format": "$unmapped.{parse=json}$"}],
            "mappings": {"version": 1, "mappings": []}
        },
        "metadata": {},
        "source_type": "community"
    }


class TestOrchestrator:
    """Test ConversionSystemOrchestrator"""

    @pytest.mark.asyncio
    async def test_initialization(self, tmp_path, mock_config):
        """Test orchestrator initialization"""
        # Create temporary config file
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(mock_config, f)

        # Initialize orchestrator
        orchestrator = ConversionSystemOrchestrator(str(config_file))

        assert orchestrator.config == mock_config
        assert orchestrator.statistics["parsers_scanned"] == 0

    @pytest.mark.asyncio
    async def test_scan_parsers_phase(self, tmp_path, mock_config, mock_parser):
        """Test Phase 1: Scanning parsers"""
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(mock_config, f)

        orchestrator = ConversionSystemOrchestrator(str(config_file))

        # Mock scanner
        mock_scanner = AsyncMock()
        mock_scanner.scan_parsers = AsyncMock(return_value=[mock_parser])
        mock_scanner.get_statistics = Mock(return_value={})
        mock_scanner.__aenter__ = AsyncMock(return_value=mock_scanner)
        mock_scanner.__aexit__ = AsyncMock(return_value=None)

        orchestrator.scanner = mock_scanner

        # Run phase 1 using the new modular function
        from orchestrator.parser_scanner import scan_parsers
        parsers = await scan_parsers(
            orchestrator.scanner,
            orchestrator.config,
            orchestrator.statistics,
            orchestrator.output_dir
        )

        assert len(parsers) == 1
        assert parsers[0]["parser_id"] == "test_parser"
        assert orchestrator.statistics["parsers_scanned"] == 1

    @pytest.mark.asyncio
    async def test_statistics_tracking(self, tmp_path, mock_config):
        """Test statistics tracking throughout conversion"""
        config_file = tmp_path / "test_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(mock_config, f)

        orchestrator = ConversionSystemOrchestrator(str(config_file))

        # Verify initial state
        assert orchestrator.statistics["parsers_scanned"] == 0
        assert orchestrator.statistics["parsers_analyzed"] == 0
        assert orchestrator.statistics["lua_generated"] == 0

        # Test statistics update
        orchestrator.statistics["parsers_scanned"] = 10
        orchestrator.statistics["parsers_analyzed"] = 9
        orchestrator.statistics["lua_generated"] = 8

        assert orchestrator.statistics["parsers_scanned"] == 10


@pytest.mark.asyncio
async def test_error_handling():
    """Test error handling in orchestrator"""
    # Test with non-existent config file
    with pytest.raises(Exception):
        orchestrator = ConversionSystemOrchestrator("nonexistent_config.yaml")


@pytest.mark.asyncio
async def test_output_directory_creation(tmp_path, mock_config):
    """Test output directory is created"""
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(mock_config, f)

    orchestrator = ConversionSystemOrchestrator(str(config_file))

    assert orchestrator.output_dir.exists()
    assert orchestrator.output_dir.is_dir()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
