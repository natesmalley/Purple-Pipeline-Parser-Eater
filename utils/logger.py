"""
Logging configuration and utilities for the SentinelOne to Observo.ai conversion system
"""
import logging
import structlog
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from datetime import datetime


class ConversionLogger:
    """Enhanced logging for the conversion system"""

    def __init__(self, config: dict):
        self.config = config
        self.setup_logging()

    def setup_logging(self):
        """Configure structured logging with rotation"""
        # Create logs directory if needed
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Configure standard logging
        log_level = getattr(logging, self.config.get("logging", {}).get("level", "INFO"))
        log_file = self.config.get("logging", {}).get("file", "conversion.log")

        # Setup rotating file handler
        file_handler = RotatingFileHandler(
            log_dir / log_file,
            maxBytes=1024 * 1024 * 1024,  # 1GB
            backupCount=10
        )

        # Configure formatter
        formatter = logging.Formatter(
            self.config.get("logging", {}).get(
                "format",
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            )
        )
        file_handler.setFormatter(formatter)

        # Configure root logger
        logging.basicConfig(
            level=log_level,
            handlers=[file_handler, logging.StreamHandler()]
        )

        # Configure structlog for structured logging
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer()
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

    @staticmethod
    def get_logger(name: str) -> structlog.BoundLogger:
        """Get a structured logger instance"""
        return structlog.get_logger(name)

    @staticmethod
    def log_phase(phase: str, message: str, **kwargs):
        """Log a conversion phase with consistent formatting"""
        logger = structlog.get_logger("orchestrator")
        logger.info(
            f"[PHASE: {phase}] {message}",
            phase=phase,
            timestamp=datetime.now().isoformat(),
            **kwargs
        )

    @staticmethod
    def log_parser_conversion(parser_id: str, status: str, **details):
        """Log individual parser conversion status"""
        logger = structlog.get_logger("parser_conversion")
        logger.info(
            f"Parser {parser_id}: {status}",
            parser_id=parser_id,
            status=status,
            **details
        )