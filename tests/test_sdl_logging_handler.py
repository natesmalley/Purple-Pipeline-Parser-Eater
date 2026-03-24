import logging

from components.sdl_logging_handler import SDLLoggingHandler


def test_sdl_logging_handler_disables_when_api_key_missing():
    handler = SDLLoggingHandler(
        config={
            "sentinelone_sdl": {
                "audit_logging_enabled": True,
                "send_all_logs": True,
                "api_key": "",
            }
        },
        level=logging.INFO,
    )
    try:
        assert handler.enabled is False
    finally:
        handler.close()

