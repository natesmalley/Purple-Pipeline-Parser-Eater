#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web Feedback UI Server - Backward Compatibility Wrapper

DEPRECATED: This file now imports from components.web_ui module.
For new code, import directly from components.web_ui:
    from components.web_ui import WebFeedbackServer

This wrapper maintains backward compatibility with existing code that imports
from this module. All functionality has been refactored into modular components
for better maintainability.

Original implementation:
- Phase 2: TLS/HTTPS support with SSL context
- Phase 2: XSS protection with CSP headers and event delegation
- Phase 3: CSRF Protection
- Phase 4: Rate limiting (MANDATORY for production)
- Phase 5: API documentation blueprint
- Phase 6: Nonce-based Content Security Policy
"""

from components.web_ui import WebFeedbackServer

__all__ = ['WebFeedbackServer']
