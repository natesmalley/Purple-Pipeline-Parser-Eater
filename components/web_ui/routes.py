"""Route handlers for web UI."""

import logging
import asyncio
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify, g
from flask_wtf.csrf import generate_csrf, CSRFError
from .parser_workbench import ParserLuaWorkbench
from components.testing_harness import HarnessOrchestrator
from utils.security_utils import (
    validate_parser_name, sanitize_log_input, sanitize_request_id,
    validate_json_depth, get_secure_nonce
)

logger = logging.getLogger(__name__)

# HTML Template (imported from main module)
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Purple Pipeline Parser Eater - Feedback UI</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1400px;
            margin: 0 auto;
        }
        .header {
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        h1 {
            color: #764ba2;
            margin-bottom: 10px;
        }
        .status-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-top: 20px;
        }
        .stat-card {
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }
        .stat-label {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
            margin-bottom: 5px;
        }
        .stat-value {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .conversion-list {
            background: white;
            border-radius: 10px;
            padding: 30px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .runtime-panel {
            background: white;
            border-radius: 10px;
            padding: 30px;
            margin-top: 20px;
            margin-bottom: 20px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        .runtime-header-title {
            font-size: 22px;
            font-weight: 600;
            color: #333;
            margin-bottom: 15px;
        }
        .runtime-grid {
            display: grid;
            gap: 15px;
            grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
        }
        .runtime-card {
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 18px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            transition: border-color 0.3s ease, box-shadow 0.3s ease;
        }
        .runtime-card:hover {
            border-color: #764ba2;
            box-shadow: 0 6px 18px rgba(118, 75, 162, 0.15);
        }
        .runtime-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-weight: 600;
            color: #333;
        }
        .runtime-parser {
            font-size: 16px;
        }
        .runtime-mode {
            font-size: 12px;
            color: #666;
            text-transform: uppercase;
        }
        .runtime-body {
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 14px;
            color: #444;
        }
        .runtime-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .runtime-row strong {
            font-variant-numeric: tabular-nums;
            color: #333;
        }
        .runtime-error strong {
            color: #dc3545;
        }
        .runtime-state {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
            margin-top: 4px;
        }
        .runtime-state-item {
            font-size: 12px;
            background: #f3f4f6;
            border-radius: 12px;
            padding: 4px 10px;
            color: #555;
        }
        .runtime-actions {
            display: flex;
            gap: 10px;
            margin-top: 10px;
        }
        .btn-runtime {
            background: #4f46e5;
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 13px;
        }
        .btn-runtime:hover {
            background: #4338ca;
        }
        .runtime-empty {
            font-size: 14px;
            color: #777;
        }
        .conversion-item {
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            transition: all 0.3s ease;
        }
        .conversion-item:hover {
            border-color: #667eea;
            box-shadow: 0 5px 15px rgba(102, 126, 234, 0.2);
        }
        .parser-name {
            font-size: 20px;
            font-weight: bold;
            color: #333;
            margin-bottom: 10px;
        }
        .code-preview {
            background: #f5f5f5;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            max-height: 300px;
            overflow-y: auto;
            margin: 15px 0;
            white-space: pre-wrap;
        }
        .button-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn {
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            transition: all 0.3s ease;
        }
        .btn-approve {
            background: #28a745;
            color: white;
        }
        .btn-approve:hover {
            background: #218838;
            transform: translateY(-2px);
        }
        .btn-reject {
            background: #dc3545;
            color: white;
        }
        .btn-reject:hover {
            background: #c82333;
            transform: translateY(-2px);
        }
        .btn-modify {
            background: #ffc107;
            color: #333;
        }
        .btn-modify:hover {
            background: #e0a800;
            transform: translateY(-2px);
        }
        .empty-state {
            text-align: center;
            padding: 60px;
            color: #999;
        }
        .empty-state h2 {
            color: #764ba2;
            margin-bottom: 10px;
        }
        .modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.5);
            z-index: 1000;
        }
        .modal-content {
            background: white;
            margin: 50px auto;
            padding: 30px;
            border-radius: 10px;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
        }
        .editor {
            width: 100%;
            min-height: 400px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            margin: 15px 0;
        }
        .timestamp {
            color: #999;
            font-size: 12px;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>[PPPE] Purple Pipeline Parser Eater - Feedback UI</h1>
            <p>Review and provide feedback on parser conversions</p>

            <div class="status-bar">
                <div class="stat-card">
                    <div class="stat-label">Pending Review</div>
                    <div class="stat-value">{{ status.pending_conversions }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Approved</div>
                    <div class="stat-value">{{ status.approved_conversions }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Rejected</div>
                    <div class="stat-value">{{ status.rejected_conversions }}</div>
                </div>
                <div class="stat-card">
                    <div class="stat-label">Queue Size</div>
                    <div class="stat-value">{{ status.queue_size }}</div>
                </div>
            </div>
        </div>

        <div class="runtime-panel">
            <div class="runtime-header-title">Runtime Metrics & Canary Status</div>
            <div id="runtimeStatusPanel" class="runtime-grid runtime-empty">
                <p>Loading runtime metrics…</p>
            </div>
        </div>

        <div class="conversion-list">
            <h2>Pending Conversions</h2>

            {% if pending %}
                {% for parser_name, conversion in pending.items() %}
                <div class="conversion-item" id="conversion-{{ parser_name }}">
                    <div class="parser-name">{{ parser_name|e }}</div>
                    <div class="timestamp">Converted: {{ conversion.timestamp|e }}</div>

                    {% if conversion.conversion_result.success %}
                    <div class="code-preview">{{ conversion.conversion_result.lua_code[:500]|e }}...
(click "Modify" to see full code)</div>

                    <div class="button-group">
                        <button class="btn btn-approve" data-parser-id="{{ parser_name|e }}" data-action="approve">
                            [OK] Approve
                        </button>
                        <button class="btn btn-reject" data-parser-id="{{ parser_name|e }}" data-action="reject">
                            [ERROR] Reject
                        </button>
                        <button class="btn btn-modify" data-parser-id="{{ parser_name|e }}" data-action="modify">
                            [EDIT] Modify
                        </button>
                    </div>
                    {% else %}
                    <div class="code-preview" style="background: #ffe6e6; border-color: #dc3545;">
                        [ERROR] Conversion failed: {{ conversion.conversion_result.error|e }}
                    </div>

                    <div class="button-group">
                        <button class="btn btn-reject" data-parser-id="{{ parser_name|e }}" data-action="reject">
                            [ERROR] Reject
                        </button>
                    </div>
                    {% endif %}
                </div>
                {% endfor %}
            {% else %}
                <div class="empty-state">
                    <h2>No Pending Conversions</h2>
                    <p>New conversions will appear here when detected.</p>
                    <p>The system checks GitHub every hour for new parsers.</p>
                </div>
            {% endif %}
        </div>
    </div>

    <!-- Modify Modal -->
    <div id="modifyModal" class="modal">
        <div class="modal-content">
            <h2>Modify LUA Code</h2>
            <p id="modalParserName"></p>
            <textarea id="luaEditor" class="editor"></textarea>
            <div class="button-group">
                <button class="btn btn-approve" data-action="save-modification">Save & Approve</button>
                <button class="btn btn-reject" data-action="close-modal">Cancel</button>
            </div>
        </div>
    </div>

    <script nonce="{{ csp_nonce }}">
        // SECURITY: Event delegation - no inline onclick handlers
        // All event handlers attached via data attributes and event delegation
        // SECURITY FIX: Phase 6 - Script protected by CSP nonce

        let currentParser = null;
        let csrfToken = null;  // SECURITY FIX: Phase 3 - CSRF token

        // Event delegation for all button clicks
        document.addEventListener('DOMContentLoaded', function() {
            // SECURITY FIX: Phase 3 - Fetch CSRF token on page load
            fetch('/api/csrf-token')
                .then(r => r.json())
                .then(data => {
                    csrfToken = data.csrf_token;
                    // CSRF token loaded successfully
                })
                .catch(err => {
                    // Log error to server instead of console
                    fetch('/api/error', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({error: 'CSRF token load failed', details: err.message})
                    }).catch(() => {});
                    alert('Security initialization failed. Please refresh the page.');
                });

            // Delegate all button clicks to document body
            document.body.addEventListener('click', function(event) {
                const button = event.target.closest('button[data-action]');
                if (!button) return;

                const action = button.getAttribute('data-action');
                const parserId = button.getAttribute('data-parser-id');

                // Route to appropriate handler based on action
                switch(action) {
                    case 'approve':
                        handleApprove(parserId);
                        break;
                    case 'reject':
                        handleReject(parserId);
                        break;
                    case 'modify':
                        handleModify(parserId);
                        break;
                    case 'save-modification':
                        handleSaveModification();
                        break;
                    case 'close-modal':
                        handleCloseModal();
                        break;
                    case 'runtime-reload':
                        handleRuntimeReload(parserId);
                        break;
                    case 'runtime-promote':
                        handleRuntimePromotion(parserId);
                        break;
                }
            });

            // Periodically refresh runtime status section
            fetchRuntimeStatus();
            setInterval(fetchRuntimeStatus, 15000);
        });

        function handleApprove(parserName) {
            // Sanitize parser name for display (prevent XSS in confirm dialog)
            const sanitized = sanitizeForDisplay(parserName);
            if (!confirm(`Approve conversion for ${sanitized}?`)) return;

            // SECURITY FIX: Phase 3 - Check CSRF token available
            if (!csrfToken) {
                alert('Security token not loaded. Please refresh the page.');
                return;
            }

            fetch('/api/v1/approve', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken  // SECURITY FIX: Phase 3
                },
                body: JSON.stringify({ parser_name: parserName })
            })
            .then(r => r.json())
            .then(data => {
                alert('[OK] Approved!');
                // Safely remove element by escaping ID selector
                const element = document.querySelector(`[id="conversion-${CSS.escape(parserName)}"]`);
                if (element) element.remove();
                location.reload();
            })
            .catch(err => {
                alert('Error approving conversion: ' + err.message);
            });
        }

        function handleReject(parserName) {
            const sanitized = sanitizeForDisplay(parserName);
            const reason = prompt(`Why are you rejecting ${sanitized}?`, '');
            if (!reason) return;

            const retry = confirm('Retry with different strategy?');

            // SECURITY FIX: Phase 3 - Check CSRF token available
            if (!csrfToken) {
                alert('Security token not loaded. Please refresh the page.');
                return;
            }

            fetch('/api/v1/reject', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken  // SECURITY FIX: Phase 3
                },
                body: JSON.stringify({
                    parser_name: parserName,
                    reason: reason,
                    retry: retry
                })
            })
            .then(r => r.json())
            .then(data => {
                alert('[ERROR] Rejected' + (retry ? ' (will retry)' : ''));
                const element = document.querySelector(`[id="conversion-${CSS.escape(parserName)}"]`);
                if (element) element.remove();
                location.reload();
            })
            .catch(err => {
                alert('Error rejecting conversion: ' + err.message);
            });
        }

        function handleModify(parserName) {
            currentParser = parserName;

            // Fetch full conversion details with proper encoding
            fetch('/api/v1/conversion/' + encodeURIComponent(parserName))
            .then(r => r.json())
            .then(conversion => {
                // Use textContent (not innerHTML) to prevent XSS
                document.getElementById('modalParserName').textContent = parserName;
                document.getElementById('luaEditor').value = conversion.conversion_result.lua_code;
                document.getElementById('modifyModal').style.display = 'block';
            })
            .catch(err => {
                alert('Error loading conversion: ' + err.message);
            });
        }

        function handleSaveModification() {
            const correctedLua = document.getElementById('luaEditor').value;
            const reason = prompt('What did you change and why?', '');

            if (!reason) return;

            // SECURITY FIX: Phase 3 - Check CSRF token available
            if (!csrfToken) {
                alert('Security token not loaded. Please refresh the page.');
                return;
            }

            fetch('/api/v1/modify', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken  // SECURITY FIX: Phase 3
                },
                body: JSON.stringify({
                    parser_name: currentParser,
                    corrected_lua: correctedLua,
                    reason: reason
                })
            })
            .then(r => r.json())
            .then(data => {
                alert('[OK] Modified and approved!');
                handleCloseModal();
                location.reload();
            })
            .catch(err => {
                alert('Error saving modification: ' + err.message);
            });
        }

        function handleCloseModal() {
            document.getElementById('modifyModal').style.display = 'none';
            currentParser = null;
        }

        function handleRuntimeReload(parserName) {
            if (!csrfToken) {
                alert('Security token not loaded. Please refresh the page.');
                return;
            }

            fetch(`/api/v1/runtime/reload/${encodeURIComponent(parserName)}`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                }
            }).then(r => r.json()).then(data => {
                alert('[OK] Reload requested.');
                fetchRuntimeStatus();
            }).catch(err => {
                alert('Error requesting reload: ' + err.message);
            });
        }

        function handleRuntimePromotion(parserName) {
            if (!csrfToken) {
                alert('Security token not loaded. Please refresh the page.');
                return;
            }

            fetch(`/api/v1/runtime/canary/${encodeURIComponent(parserName)}/promote`, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrfToken
                }
            }).then(r => r.json()).then(data => {
                alert('[OK] Promotion requested.');
                fetchRuntimeStatus();
            }).catch(err => {
                alert('Error requesting promotion: ' + err.message);
            });
        }

        function fetchRuntimeStatus() {
            fetch('/api/v1/runtime/status')
                .then(r => r.json())
                .then(data => {
                    updateRuntimeStatus(data);
                })
                .catch(err => console.warn('Runtime status fetch failed:', err));
        }

        function updateRuntimeStatus(data) {
            const panel = document.getElementById('runtimeStatusPanel');
            if (!panel) return;

            const metrics = data.metrics || {};
            const reloads = data.reload_requests || {};
            const promotions = data.pending_promotions || {};

            if (!Object.keys(metrics).length) {
                panel.innerHTML = '<p>No runtime metrics available yet.</p>';
                return;
            }

            let html = '';
            for (const [parserId, metric] of Object.entries(metrics)) {
                const reloadState = reloads[parserId] || 'none';
                const promotionState = promotions[parserId] || 'none';

                html += `
                <div class="runtime-card">
                    <div class="runtime-header">
                        <span class="runtime-parser">${sanitizeForDisplay(parserId)}</span>
                        <span class="runtime-mode">Stable: ${metric.stable_events || 0} / Canary: ${metric.canary_events || 0}</span>
                    </div>
                    <div class="runtime-body">
                        <div class="runtime-row">
                            <span>Total</span><strong>${metric.total_events || 0}</strong>
                        </div>
                        <div class="runtime-row">
                            <span>Successes</span><strong>${metric.successes || 0}</strong>
                        </div>
                        <div class="runtime-row">
                            <span>Failures</span><strong>${metric.failures || 0}</strong>
                        </div>
                        <div class="runtime-row ${metric.error_rate > 0 ? 'runtime-error' : ''}">
                            <span>Error Rate</span><strong>${((metric.error_rate || 0) * 100).toFixed(2)}%</strong>
                        </div>
                        <div class="runtime-row">
                            <span>Last Error</span><strong>${sanitizeForDisplay(metric.last_error || '—')}</strong>
                        </div>
                        <div class="runtime-state">
                            <div class="runtime-state-item">Reload: <strong>${reloadState}</strong></div>
                            <div class="runtime-state-item">Promotion: <strong>${promotionState}</strong></div>
                        </div>
                    </div>
                    <div class="runtime-actions">
                        <button class="btn btn-runtime" data-action="runtime-reload" data-parser-id="${sanitizeForDisplay(parserId)}">Request Reload</button>
                        <button class="btn btn-runtime" data-action="runtime-promote" data-parser-id="${sanitizeForDisplay(parserId)}">Request Promotion</button>
                    </div>
                </div>`;
            }

            panel.innerHTML = html;
        }

        // SECURITY: Sanitize strings for safe display in alert/confirm/prompt
        function sanitizeForDisplay(str) {
            // Create a text node and get its textContent to auto-escape HTML
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Auto-refresh every 30 seconds
        setInterval(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

WORKBENCH_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Parser Lua Workbench - Testing Harness</title>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: "Segoe UI", Tahoma, sans-serif;
            background: radial-gradient(circle at top left, #0e1a2b, #0a1019 60%);
            color: #e6edf3;
            min-height: 100vh;
        }
        .wrap { max-width: 1400px; margin: 0 auto; padding: 20px; }
        .header {
            background: linear-gradient(120deg, #1d3557, #457b9d);
            border-radius: 14px;
            padding: 22px;
            margin-bottom: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 { font-size: 26px; }
        .hint { color: #b8d4e3; font-size: 13px; margin-top: 4px; }

        /* Confidence gauge */
        .confidence-badge {
            text-align: center;
            min-width: 100px;
        }
        .confidence-score {
            font-size: 42px;
            font-weight: 800;
            line-height: 1;
        }
        .confidence-grade {
            font-size: 14px;
            font-weight: 600;
            margin-top: 2px;
        }
        .grade-A { color: #4ade80; }
        .grade-B { color: #86efac; }
        .grade-C { color: #fbbf24; }
        .grade-D { color: #fb923c; }
        .grade-F { color: #f87171; }

        .panel {
            background: #121a26;
            border: 1px solid #2a3547;
            border-radius: 12px;
            padding: 16px;
            margin-bottom: 14px;
        }
        .toolbar {
            display: grid;
            grid-template-columns: 1fr auto auto auto auto auto;
            gap: 10px;
            align-items: center;
        }
        select, button, input, textarea {
            border-radius: 8px;
            border: 1px solid #41526d;
            background: #0d1622;
            color: #e6edf3;
            padding: 10px 12px;
            font-size: 14px;
        }
        button {
            background: #2a9d8f;
            border-color: #2a9d8f;
            cursor: pointer;
            font-weight: 600;
        }
        button:hover { background: #23867b; }
        button.btn-primary { background: #6366f1; border-color: #6366f1; }
        button.btn-primary:hover { background: #4f46e5; }
        button:disabled { opacity: 0.5; cursor: not-allowed; }

        /* Check summary bar */
        .check-bar {
            display: grid;
            grid-template-columns: repeat(5, 1fr);
            gap: 8px;
            margin-top: 12px;
        }
        .check-item {
            background: #0d1622;
            border: 1px solid #30415b;
            border-radius: 8px;
            padding: 10px;
            text-align: center;
            font-size: 12px;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        .check-item:hover { border-color: #6366f1; }
        .check-item.active { border-color: #6366f1; background: #1a2740; }
        .check-icon { font-size: 20px; margin-bottom: 4px; }
        .check-label { color: #94a3b8; text-transform: uppercase; font-size: 10px; }
        .check-status { margin-top: 3px; font-weight: 600; }
        .st-passed { color: #4ade80; }
        .st-good { color: #86efac; }
        .st-fair { color: #fbbf24; }
        .st-poor { color: #f87171; }
        .st-failed { color: #f87171; }
        .st-skipped { color: #6b7280; }
        .st-error { color: #f87171; }
        .st-needs_review { color: #fbbf24; }
        .st-excellent { color: #4ade80; }

        /* Tabs */
        .tabs {
            display: flex;
            gap: 2px;
            margin-bottom: 0;
            border-bottom: 2px solid #2a3547;
        }
        .tab-btn {
            background: #0d1622;
            border: 1px solid #2a3547;
            border-bottom: none;
            border-radius: 8px 8px 0 0;
            padding: 10px 18px;
            color: #94a3b8;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
        }
        .tab-btn.active { background: #121a26; color: #e6edf3; border-color: #6366f1; }
        .tab-content {
            display: none;
            background: #121a26;
            border: 1px solid #2a3547;
            border-top: none;
            border-radius: 0 0 12px 12px;
            padding: 16px;
            min-height: 400px;
        }
        .tab-content.active { display: block; }

        pre {
            margin: 0;
            border-radius: 8px;
            border: 1px solid #314259;
            background: #09111b;
            color: #d7e3f2;
            padding: 14px;
            max-height: 60vh;
            overflow: auto;
            white-space: pre-wrap;
            font-size: 12px;
            line-height: 1.5;
        }
        .split { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
        .status { margin-top: 8px; font-size: 13px; color: #9bd1c7; }
        h3 { font-size: 15px; margin-bottom: 10px; color: #cbd5e1; }
        .meta {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 8px;
            margin-top: 10px;
        }
        .meta-item {
            background: #0d1622;
            border: 1px solid #30415b;
            border-radius: 8px;
            padding: 8px 10px;
        }
        .meta-label { font-size: 11px; color: #94a3b8; text-transform: uppercase; }
        .meta-value { font-size: 13px; margin-top: 2px; word-break: break-word; }

        /* Lint issues */
        .lint-issue {
            padding: 6px 10px;
            border-left: 3px solid #6b7280;
            margin-bottom: 6px;
            font-size: 13px;
            background: #0d1622;
            border-radius: 0 6px 6px 0;
        }
        .lint-issue.error { border-left-color: #f87171; }
        .lint-issue.warning { border-left-color: #fbbf24; }
        .lint-issue.info { border-left-color: #60a5fa; }
        .lint-line { color: #94a3b8; font-size: 11px; }
        .lint-rule { color: #6b7280; font-size: 11px; margin-left: 8px; }

        /* OCSF field table */
        .field-table { width: 100%; border-collapse: collapse; font-size: 13px; }
        .field-table th {
            text-align: left;
            padding: 8px;
            background: #0d1622;
            color: #94a3b8;
            font-size: 11px;
            text-transform: uppercase;
            border-bottom: 1px solid #2a3547;
        }
        .field-table td {
            padding: 6px 8px;
            border-bottom: 1px solid #1a2740;
        }
        .field-present { color: #4ade80; }
        .field-missing { color: #f87171; }
        .field-unknown { color: #fbbf24; }
        .field-optional { color: #60a5fa; }
        .sortable-th { cursor: pointer; user-select: none; position: relative; }
        .sortable-th:hover { color: #e2e8f0; }
        .sortable-th::after { content: ' \u2195'; font-size: 10px; opacity: 0.4; }
        .sortable-th.sort-asc::after { content: ' \u2191'; opacity: 0.9; }
        .sortable-th.sort-desc::after { content: ' \u2193'; opacity: 0.9; }

        /* Test results */
        .test-card {
            background: #0d1622;
            border: 1px solid #30415b;
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 10px;
        }
        .test-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 8px;
        }
        .test-name { font-weight: 600; font-size: 14px; }
        .test-pass { color: #4ade80; font-weight: 600; }
        .test-fail { color: #f87171; font-weight: 600; }
        .test-error { color: #fb923c; font-weight: 600; }
        .test-split {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        .test-split pre { max-height: 200px; font-size: 11px; }
        textarea.event-editor {
            width: 100%;
            min-height: 120px;
            font-family: monospace;
            font-size: 12px;
            resize: vertical;
        }
        .version-select { padding: 6px 10px; font-size: 13px; }
        .loading { color: #6b7280; font-style: italic; }
        @media (max-width: 980px) {
            .split, .test-split { grid-template-columns: 1fr; }
            .toolbar { grid-template-columns: 1fr; }
            .check-bar { grid-template-columns: repeat(3, 1fr); }
        }
    </style>
</head>
<body>
    <div class="wrap">
        <div class="header">
            <div>
                <h1>Parser Lua Workbench</h1>
                <div class="hint">Build, validate, and test Lua transformations with 5-point confidence scoring</div>
            </div>
            <div class="confidence-badge" id="confidenceBadge" style="display:none">
                <div class="confidence-score" id="confidenceScore">--</div>
                <div class="confidence-grade" id="confidenceGrade">-</div>
            </div>
        </div>

        <div class="panel">
            <div class="toolbar">
                <select id="parserSelect"></select>
                <input id="filterInput" placeholder="Filter parsers..." />
                <button id="aiGenBtn" style="background:#6366f1;border-color:#6366f1">AI Generate</button>
                <button id="validateBtn" class="btn-primary" disabled>Validate All</button>
                <button id="uploadPrBtn" style="background:#d97706;border-color:#d97706;display:none">Upload PR</button>
            </div>
            <div class="status" id="statusMsg">Loading parser list...</div>

            <div class="check-bar" id="checkBar" style="display:none">
                <div class="check-item" data-tab="tab-lua" id="chk-validity">
                    <div class="check-icon">&#9881;</div>
                    <div class="check-label">Lua Validity</div>
                    <div class="check-status" id="chk-validity-st">--</div>
                </div>
                <div class="check-item" data-tab="tab-lint" id="chk-linting">
                    <div class="check-icon">&#9733;</div>
                    <div class="check-label">Lua Linting</div>
                    <div class="check-status" id="chk-linting-st">--</div>
                </div>
                <div class="check-item" data-tab="tab-ocsf" id="chk-ocsf">
                    <div class="check-icon">&#9745;</div>
                    <div class="check-label">OCSF Mapping</div>
                    <div class="check-status" id="chk-ocsf-st">--</div>
                </div>
                <div class="check-item" data-tab="tab-fields" id="chk-fields">
                    <div class="check-icon">&#9776;</div>
                    <div class="check-label">Source Fields</div>
                    <div class="check-status" id="chk-fields-st">--</div>
                </div>
                <div class="check-item" data-tab="tab-tests" id="chk-tests">
                    <div class="check-icon">&#9654;</div>
                    <div class="check-label">Test Events</div>
                    <div class="check-status" id="chk-tests-st">--</div>
                </div>
            </div>
        </div>

        <div class="tabs" id="tabBar">
            <button class="tab-btn active" data-tab="tab-lua">Lua Code</button>
            <button class="tab-btn" data-tab="tab-lint">Lint Results</button>
            <button class="tab-btn" data-tab="tab-ocsf">OCSF Mapping</button>
            <button class="tab-btn" data-tab="tab-fields">Source Fields</button>
            <button class="tab-btn" data-tab="tab-tests">Test Events</button>
        </div>

        <!-- Tab: Lua Code -->
        <div class="tab-content active" id="tab-lua">
            <div class="split">
                <div>
                    <h3>Generated Lua</h3>
                    <pre id="luaCode">Select a parser and click AI Generate</pre>
                </div>
                <div>
                    <h3>Example Log</h3>
                    <pre id="exampleLog"></pre>
                    <div class="meta" id="metaGrid"></div>
                </div>
            </div>
        </div>

        <!-- Tab: Lint Results -->
        <div class="tab-content" id="tab-lint">
            <div class="split">
                <div>
                    <h3>Lint Quality Score</h3>
                    <div id="lintScore" class="loading">Run validation to see results</div>
                    <h3 style="margin-top:16px">Issues</h3>
                    <div id="lintIssues"></div>
                </div>
                <div>
                    <h3>Generated Lua (reference)</h3>
                    <pre id="lintLuaRef"></pre>
                </div>
            </div>
        </div>

        <!-- Tab: OCSF Mapping -->
        <div class="tab-content" id="tab-ocsf">
            <div style="margin-bottom:12px; display:flex; gap:10px; align-items:center;">
                <label>OCSF Version:</label>
                <select class="version-select" id="ocsfVersionSelect">
                    <option value="1.0.0">v1.0.0</option>
                    <option value="1.1.0">v1.1.0</option>
                    <option value="1.3.0" selected>v1.3.0</option>
                </select>
                <span id="ocsfClassName" style="color:#94a3b8;font-size:13px;"></span>
            </div>
            <div class="split">
                <div>
                    <h3>Required OCSF Fields</h3>
                    <table class="field-table sortable" id="ocsfRequiredTable">
                        <thead><tr><th data-sort="field" class="sortable-th">Field Name</th><th data-sort="status" class="sortable-th">Status</th></tr></thead>
                        <tbody id="ocsfRequiredBody"></tbody>
                    </table>
                </div>
                <div>
                    <h3>All Mapped Fields</h3>
                    <table class="field-table sortable" id="ocsfAllTable">
                        <thead><tr><th data-sort="field" class="sortable-th">Field Name</th><th data-sort="status" class="sortable-th">OCSF Status</th><th data-sort="value" class="sortable-th">Assigned Value</th></tr></thead>
                        <tbody id="ocsfAllBody"></tbody>
                    </table>
                </div>
            </div>
        </div>

        <!-- Tab: Source Fields -->
        <div class="tab-content" id="tab-fields">
            <div class="split">
                <div>
                    <h3>Source Parser Fields</h3>
                    <table class="field-table" id="sourceFieldsTable">
                        <thead><tr><th>Field Name</th><th>Type</th><th>Source</th></tr></thead>
                        <tbody id="sourceFieldsBody"></tbody>
                    </table>
                </div>
                <div>
                    <h3>Field Mapping Coverage</h3>
                    <div id="fieldCoverageInfo" class="loading">Run validation to see results</div>
                    <div id="fieldComparisonDetail"></div>
                </div>
            </div>
        </div>

        <!-- Tab: Test Events -->
        <div class="tab-content" id="tab-tests">
            <div style="margin-bottom:12px; display:flex; gap:10px; align-items:center;">
                <button id="runTestsBtn" disabled>Run Tests</button>
                <span id="testSummary" style="font-size:13px; color:#94a3b8;"></span>
            </div>
            <div id="testResults" class="loading">Run validation to generate and execute test events</div>
            <div style="margin-top:16px">
                <h3>Custom Test Event</h3>
                <textarea class="event-editor" id="customEventInput" placeholder='{"timestamp":"2024-01-15T10:30:00Z","event_id":4624,"user_name":"admin"}'></textarea>
                <button id="runCustomBtn" style="margin-top:8px" disabled>Run Custom Event</button>
                <div id="customResult"></div>
            </div>
        </div>
    </div>

    <script nonce="{{ csp_nonce }}">
        let csrfToken = null;
        let parsers = [];
        let currentParser = null;
        let currentLua = null;
        let lastReport = null;

        const $ = id => document.getElementById(id);
        const esc = s => String(s).replace(/</g, '&lt;').replace(/>/g, '&gt;');

        function setStatus(msg) { $('statusMsg').textContent = msg; }

        // Tab switching
        document.querySelectorAll('.tab-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                btn.classList.add('active');
                $(btn.dataset.tab).classList.add('active');
            });
        });
        // Check-bar items also switch tabs
        document.querySelectorAll('.check-item').forEach(item => {
            item.addEventListener('click', () => {
                const tab = item.dataset.tab;
                document.querySelectorAll('.tab-btn').forEach(b => {
                    b.classList.toggle('active', b.dataset.tab === tab);
                });
                document.querySelectorAll('.tab-content').forEach(c => {
                    c.classList.toggle('active', c.id === tab);
                });
            });
        });

        function populateSelect(list) {
            const select = $('parserSelect');
            const current = select.value;
            select.innerHTML = list.map(p =>
                `<option value="${esc(p.parser_name)}">${esc(p.parser_name)} [${esc(p.ingestion_mode)}]</option>`
            ).join('');
            if (current) {
                const found = list.find(x => x.parser_name === current);
                if (found) select.value = current;
            }
        }

        async function loadParsers() {
            const resp = await fetch('/api/v1/workbench/parsers');
            const data = await resp.json();
            parsers = data.parsers || [];
            populateSelect(parsers);
            setStatus(`Loaded ${parsers.length} parsers.`);
        }

        async function loadCsrf() {
            const resp = await fetch('/api/csrf-token');
            const data = await resp.json();
            csrfToken = data.csrf_token;
        }

        function renderMeta(payload) {
            $('metaGrid').innerHTML = [
                ['Parser', payload.parser_name],
                ['Ingestion', payload.ingestion_mode],
                ['Template', payload.processing_template_used || 'none'],
                ['Source', payload.generated_source]
            ].map(([k,v]) => `<div class="meta-item"><div class="meta-label">${k}</div><div class="meta-value">${esc(v||'')}</div></div>`).join('');
        }

        async function buildSelected() {
            const parserName = $('parserSelect').value;
            if (!parserName) return;
            if (!csrfToken) await loadCsrf();
            currentParser = parserName;

            setStatus(`Building Lua for ${parserName}...`);
            const resp = await fetch('/api/v1/workbench/build', {
                method: 'POST',
                headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                body: JSON.stringify({parser_name: parserName})
            });
            const payload = await resp.json();
            if (!resp.ok) { setStatus(`Build failed: ${payload.error}`); return; }

            currentLua = payload.lua_code || '';
            $('luaCode').textContent = currentLua;
            $('lintLuaRef').textContent = currentLua;
            $('exampleLog').textContent = payload.example_log || '';
            renderMeta(payload);
            $('validateBtn').disabled = false;
            $('runTestsBtn').disabled = false;
            $('runCustomBtn').disabled = false;
            setStatus(`Built ${parserName}. Click Validate All to run the testing harness.`);
        }

        function updateConfidence(report) {
            const badge = $('confidenceBadge');
            badge.style.display = '';
            const score = report.confidence_score;
            const grade = report.confidence_grade;
            $('confidenceScore').textContent = score;
            $('confidenceGrade').textContent = `Grade ${grade}`;
            $('confidenceGrade').className = `confidence-grade grade-${grade}`;
            $('confidenceScore').className = `confidence-score grade-${grade}`;
        }

        function updateCheckBar(report) {
            $('checkBar').style.display = '';
            const summary = report.check_summary || {};
            const map = {
                'chk-validity': summary.lua_validity,
                'chk-linting': summary.lua_linting,
                'chk-ocsf': summary.ocsf_mapping,
                'chk-fields': summary.field_comparison,
                'chk-tests': summary.test_execution
            };
            for (const [id, status] of Object.entries(map)) {
                const el = $(id + '-st');
                const st = status || 'skipped';
                el.textContent = st.replace(/_/g, ' ');
                el.className = `check-status st-${st}`;
            }
        }

        function renderLintResults(checks) {
            const lint = checks.lua_linting || {};
            if (lint.error || lint.skipped) {
                $('lintScore').innerHTML = `<span class="st-skipped">${lint.error || 'Skipped'}</span>`;
                return;
            }
            const score = lint.score || 0;
            const cls = score >= 80 ? 'st-passed' : score >= 50 ? 'st-fair' : 'st-poor';
            $('lintScore').innerHTML = `<span class="${cls}" style="font-size:36px;font-weight:800">${score}</span><span style="color:#94a3b8"> / 100</span>
                <div style="margin-top:4px;font-size:13px;color:#94a3b8">${(lint.summary||{}).errors||0} errors, ${(lint.summary||{}).warnings||0} warnings, ${(lint.summary||{}).info||0} info</div>`;

            const issues = lint.issues || [];
            $('lintIssues').innerHTML = issues.length === 0
                ? '<div style="color:#4ade80">No issues found</div>'
                : issues.map(i => `<div class="lint-issue ${i.severity}">
                    <span>${esc(i.message)}</span>
                    ${i.line ? `<span class="lint-line">Line ${i.line}</span>` : ''}
                    <span class="lint-rule">${esc(i.rule)}</span>
                </div>`).join('');
        }

        // Status display names and sort priority
        const STATUS_LABELS = {
            'required_present': 'Required',
            'required_missing': 'MISSING',
            'optional_present': 'Optional',
            'deprecated': 'Deprecated',
            'unknown': 'Unmapped'
        };
        const STATUS_PRIORITY = {
            'required_missing': 0,
            'required_present': 1,
            'optional_present': 2,
            'unknown': 3,
            'deprecated': 4
        };
        const STATUS_CSS = {
            'required_present': 'field-present',
            'required_missing': 'field-missing',
            'optional_present': 'field-optional',
            'unknown': 'field-unknown',
            'deprecated': 'field-unknown'
        };

        // Generic table sort handler
        function setupTableSort(tableId, bodyId, dataFn) {
            const table = document.getElementById(tableId);
            if (!table) return;
            let sortCol = null, sortDir = 'asc';
            table.querySelectorAll('.sortable-th').forEach(th => {
                th.addEventListener('click', () => {
                    const col = th.dataset.sort;
                    if (sortCol === col) { sortDir = sortDir === 'asc' ? 'desc' : 'asc'; }
                    else { sortCol = col; sortDir = 'asc'; }
                    table.querySelectorAll('.sortable-th').forEach(h => h.classList.remove('sort-asc','sort-desc'));
                    th.classList.add(sortDir === 'asc' ? 'sort-asc' : 'sort-desc');
                    const data = dataFn();
                    data.sort((a,b) => {
                        let va = a[col] || '', vb = b[col] || '';
                        if (col === 'status') { va = STATUS_PRIORITY[va] ?? 99; vb = STATUS_PRIORITY[vb] ?? 99; }
                        else { va = String(va).toLowerCase(); vb = String(vb).toLowerCase(); }
                        if (va < vb) return sortDir === 'asc' ? -1 : 1;
                        if (va > vb) return sortDir === 'asc' ? 1 : -1;
                        return 0;
                    });
                    document.getElementById(bodyId).innerHTML = dataFn.render(data);
                });
            });
        }

        let _ocsfRequiredData = [];
        let _ocsfAllData = [];

        function renderOCSFResults(checks) {
            const ocsf = checks.ocsf_mapping || {};
            if (ocsf.error || ocsf.skipped) return;

            $('ocsfClassName').textContent = ocsf.class_name
                ? `Class: ${ocsf.class_name} (${ocsf.class_uid}) | Coverage: ${(ocsf.required_coverage||0).toFixed(0)}%`
                : '';

            // Build required fields data
            const missing = (ocsf.missing_required || []);
            _ocsfRequiredData = (ocsf.field_details||[])
                .filter(d => d.status === 'required_present' || d.status === 'required_missing')
                .concat(missing.filter(f => !(ocsf.field_details||[]).some(d => d.field === f))
                    .map(f => ({field: f, status: 'required_missing'})));
            // Sort: missing first, then present, then alphabetical
            _ocsfRequiredData.sort((a,b) => (STATUS_PRIORITY[a.status]??99) - (STATUS_PRIORITY[b.status]??99) || a.field.localeCompare(b.field));

            const renderReq = (data) => data.map(d => `<tr>
                    <td>${esc(d.field)}</td>
                    <td class="${STATUS_CSS[d.status] || ''}">
                        ${STATUS_LABELS[d.status] || d.status}
                    </td>
                </tr>`).join('') || '<tr><td colspan=2 style="color:#6b7280">No data</td></tr>';
            $('ocsfRequiredBody').innerHTML = renderReq(_ocsfRequiredData);

            // Build all fields data — sort by status priority then field name
            _ocsfAllData = (ocsf.field_details||[]).map(d => ({
                field: d.field, status: d.status, value: d.assigned_value || ''
            }));
            _ocsfAllData.sort((a,b) => (STATUS_PRIORITY[a.status]??99) - (STATUS_PRIORITY[b.status]??99) || a.field.localeCompare(b.field));

            const renderAll = (data) => data.map(d => `<tr>
                <td>${esc(d.field)}</td>
                <td class="${STATUS_CSS[d.status] || ''}">
                    ${STATUS_LABELS[d.status] || esc(d.status.replace(/_/g, ' '))}
                </td>
                <td style="color:#6b7280;font-size:11px">${esc(d.value)}</td>
            </tr>`).join('') || '<tr><td colspan=3 style="color:#6b7280">No data</td></tr>';
            $('ocsfAllBody').innerHTML = renderAll(_ocsfAllData);

            // Wire up sorting
            const reqDataFn = () => _ocsfRequiredData; reqDataFn.render = renderReq;
            const allDataFn = () => _ocsfAllData; allDataFn.render = renderAll;
            setupTableSort('ocsfRequiredTable', 'ocsfRequiredBody', reqDataFn);
            setupTableSort('ocsfAllTable', 'ocsfAllBody', allDataFn);
        }

        function renderSourceFields(checks) {
            const src = checks.source_fields || {};
            if (src.error || src.skipped) {
                $('sourceFieldsBody').innerHTML = `<tr><td colspan=3 style="color:#6b7280">${esc(src.reason || src.error || 'Skipped')}</td></tr>`;
                return;
            }
            $('sourceFieldsBody').innerHTML = (src.fields||[]).map(f => `<tr>
                <td>${esc(f.name)}</td>
                <td style="color:#94a3b8">${esc(f.type||'-')}</td>
                <td style="color:#6b7280;font-size:11px">${esc(f.source||'')}</td>
            </tr>`).join('') || '<tr><td colspan=3 style="color:#6b7280">No fields found</td></tr>';

            // Coverage
            const comp = checks.field_comparison || {};
            if (comp.skipped || comp.error) {
                $('fieldCoverageInfo').innerHTML = `<span class="st-skipped">${esc(comp.reason || comp.error || 'Skipped')}</span>`;
            } else {
                const pct = (comp.coverage_pct||0).toFixed(0);
                const cls = pct >= 70 ? 'st-passed' : pct >= 40 ? 'st-fair' : 'st-poor';
                $('fieldCoverageInfo').innerHTML = `<span class="${cls}" style="font-size:28px;font-weight:700">${pct}%</span>
                    <span style="color:#94a3b8"> field coverage</span>
                    <div style="margin-top:8px;font-size:13px">
                        <div>Source fields: ${comp.source_field_count||0}</div>
                        <div>Lua fields: ${comp.lua_field_count||0}</div>
                        <div>Mapped: ${(comp.mapped_fields||[]).length}</div>
                    </div>`;
                const unmapped = comp.unmapped_source_fields || [];
                const newFields = comp.new_lua_fields || [];
                let detail = '';
                if (unmapped.length) detail += `<h3 style="margin-top:12px;color:#fbbf24">Unmapped Source Fields (${unmapped.length})</h3>
                    <div style="font-size:12px;color:#fbbf24">${unmapped.map(esc).join(', ')}</div>`;
                if (newFields.length) detail += `<h3 style="margin-top:12px;color:#60a5fa">New Lua Fields (${newFields.length})</h3>
                    <div style="font-size:12px;color:#60a5fa">${newFields.map(esc).join(', ')}</div>`;
                $('fieldComparisonDetail').innerHTML = detail;
            }
        }

        function renderTestResults(checks) {
            const exec = checks.test_execution || {};
            if (exec.error || exec.skipped) {
                $('testResults').innerHTML = `<div class="st-skipped">${esc(exec.reason || exec.error || 'Skipped')}</div>`;
                $('testSummary').textContent = '';
                return;
            }
            $('testSummary').textContent = `${exec.passed||0}/${exec.total_events||0} passed` +
                (exec.function_signature ? ` | Signature: ${exec.function_signature}()` : '');

            const results = exec.results || [];
            $('testResults').innerHTML = results.map(r => `<div class="test-card">
                <div class="test-header">
                    <span class="test-name">${esc(r.test_name||'Test')}</span>
                    <span class="test-${r.status}">${r.status.toUpperCase()}</span>
                </div>
                ${r.error ? `<div style="color:#f87171;font-size:12px;margin-bottom:6px">${esc(r.error)}</div>` : ''}
                <div class="test-split">
                    <div><div style="font-size:11px;color:#94a3b8;margin-bottom:4px">INPUT</div><pre>${esc(JSON.stringify(r.input_event||{}, null, 2))}</pre></div>
                    <div><div style="font-size:11px;color:#94a3b8;margin-bottom:4px">OUTPUT</div><pre>${esc(JSON.stringify(r.output_event||{}, null, 2))}</pre></div>
                </div>
                ${r.ocsf_validation ? `<div style="margin-top:6px;font-size:11px;color:#94a3b8">
                    OCSF Coverage: ${(r.ocsf_validation.coverage_pct||0).toFixed(0)}%
                    ${(r.ocsf_validation.required_missing||[]).length ? ' | Missing: ' + r.ocsf_validation.required_missing.join(', ') : ''}
                </div>` : ''}
                ${r.execution_time_ms !== undefined ? `<div style="font-size:11px;color:#6b7280;margin-top:4px">${r.execution_time_ms.toFixed(1)}ms</div>` : ''}
            </div>`).join('') || '<div class="st-skipped">No test results</div>';
        }

        async function runValidation() {
            if (!currentParser) return;
            const version = $('ocsfVersionSelect').value;
            setStatus(`Running testing harness for ${currentParser}...`);
            $('validateBtn').disabled = true;

            try {
                const resp = await fetch(`/api/v1/workbench/validate/${encodeURIComponent(currentParser)}?ocsf_version=${version}`);
                const report = await resp.json();
                if (!resp.ok) { setStatus(`Validation failed: ${report.error}`); return; }

                lastReport = report;
                updateConfidence(report);
                updateCheckBar(report);
                renderLintResults(report.checks || {});
                renderOCSFResults(report.checks || {});
                renderSourceFields(report.checks || {});
                renderTestResults(report.checks || {});
                setStatus(`Validation complete (${report.elapsed_seconds}s). Confidence: ${report.confidence_score}% Grade ${report.confidence_grade}`);
            } catch(e) {
                setStatus(`Validation error: ${e.message}`);
            } finally {
                $('validateBtn').disabled = false;
            }
        }

        async function runCustomTest() {
            if (!currentParser || !csrfToken) return;
            const raw = $('customEventInput').value.trim();
            if (!raw) return;
            try {
                const evt = JSON.parse(raw);
                setStatus('Running custom test event...');
                const resp = await fetch(`/api/v1/workbench/test-run/${encodeURIComponent(currentParser)}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({test_events: [{name: 'Custom Event', description: 'User-provided', event: evt, expected_behavior: 'User-defined'}]})
                });
                const data = await resp.json();
                const r = (data.results || [])[0] || {};
                $('customResult').innerHTML = `<div class="test-card" style="margin-top:8px">
                    <div class="test-header"><span class="test-name">Custom Event</span><span class="test-${r.status||'error'}">${(r.status||'error').toUpperCase()}</span></div>
                    ${r.error ? `<div style="color:#f87171;font-size:12px">${esc(r.error)}</div>` : ''}
                    <div class="test-split">
                        <div><div style="font-size:11px;color:#94a3b8;margin-bottom:4px">INPUT</div><pre>${esc(JSON.stringify(r.input_event||evt,null,2))}</pre></div>
                        <div><div style="font-size:11px;color:#94a3b8;margin-bottom:4px">OUTPUT</div><pre>${esc(JSON.stringify(r.output_event||{},null,2))}</pre></div>
                    </div>
                </div>`;
                setStatus('Custom test complete.');
            } catch(e) {
                $('customResult').innerHTML = `<div style="color:#f87171">Invalid JSON: ${esc(e.message)}</div>`;
            }
        }

        async function aiGenerate(forceRegen = false) {
            const parserName = $('parserSelect').value;
            if (!parserName) return;
            if (!csrfToken) await loadCsrf();

            $('aiGenBtn').disabled = true;
            setStatus(`AI generating Lua for ${parserName}${forceRegen ? ' (force regenerate)' : ''}... (this may take 15-60s)`);

            try {
                const resp = await fetch('/api/v1/workbench/agent-build', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({parser_name: parserName, force_regenerate: forceRegen})
                });
                const payload = await resp.json();
                if (!resp.ok) {
                    setStatus(`AI generation failed: ${payload.error || 'unknown'}`);
                    return;
                }
                if (payload.error) {
                    setStatus(`AI generation error: ${payload.error}`);
                    return;
                }

                currentParser = parserName;
                currentLua = payload.lua_code || '';
                $('luaCode').textContent = currentLua;
                $('lintLuaRef').textContent = currentLua;
                $('exampleLog').textContent = payload.example_log || '';
                renderMeta({...payload, generated_source: `agent_generated (${payload.ocsf_class || ''})`});
                $('validateBtn').disabled = false;
                $('runTestsBtn').disabled = false;
                $('runCustomBtn').disabled = false;
                $('uploadPrBtn').style.display = '';

                // If harness report came back, render it
                if (payload.harness_report) {
                    lastReport = payload.harness_report;
                    updateConfidence(payload.harness_report);
                    updateCheckBar(payload.harness_report);
                    renderLintResults(payload.harness_report.checks || {});
                    renderOCSFResults(payload.harness_report.checks || {});
                    renderSourceFields(payload.harness_report.checks || {});
                    renderTestResults(payload.harness_report.checks || {});
                }

                const q = payload.quality === 'accepted' ? '' : ' (below threshold)';
                setStatus(`AI generated ${parserName}: ${payload.confidence_score}% Grade ${payload.confidence_grade} | ${payload.iterations} iteration(s)${q}`);
            } catch(e) {
                setStatus(`AI generation error: ${e.message}`);
            } finally {
                $('aiGenBtn').disabled = false;
            }
        }

        async function uploadPR() {
            if (!currentParser || !currentLua || !csrfToken) return;
            if (!confirm(`Create a PR with this Lua for ${currentParser}?`)) return;

            setStatus('Creating PR...');
            $('uploadPrBtn').disabled = true;
            try {
                const resp = await fetch('/api/v1/workbench/upload-pr', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrfToken},
                    body: JSON.stringify({parser_name: currentParser, lua_code: currentLua})
                });
                const data = await resp.json();
                if (data.pr_url) {
                    setStatus(`PR created: ${data.pr_url}`);
                    window.open(data.pr_url, '_blank');
                } else {
                    setStatus(`PR failed: ${data.error || 'unknown'}`);
                }
            } catch(e) {
                setStatus(`PR error: ${e.message}`);
            } finally {
                $('uploadPrBtn').disabled = false;
            }
        }

        function applyFilter() {
            const q = $('filterInput').value.toLowerCase().trim();
            const filtered = q ? parsers.filter(p => p.parser_name.toLowerCase().includes(q)) : parsers;
            populateSelect(filtered);
            setStatus(`${filtered.length} parsers.`);
        }

        document.addEventListener('DOMContentLoaded', async () => {
            $('aiGenBtn').addEventListener('click', () => aiGenerate(false));
            $('aiGenBtn').addEventListener('dblclick', () => aiGenerate(true));
            $('uploadPrBtn').addEventListener('click', uploadPR);
            $('validateBtn').addEventListener('click', runValidation);
            $('runTestsBtn').addEventListener('click', runValidation);
            $('runCustomBtn').addEventListener('click', runCustomTest);
            $('filterInput').addEventListener('input', applyFilter);
            $('ocsfVersionSelect').addEventListener('change', () => { if (lastReport) runValidation(); });
            await Promise.all([loadCsrf(), loadParsers()]);
        });
    </script>
</body>
</html>
"""


def register_routes(app: Flask, service, feedback_queue, runtime_service, event_loop, require_auth, rate_limiter=None):
    """
    Register all Flask routes for the web UI.

    Args:
        app: Flask application instance
        service: Continuous conversion service instance
        feedback_queue: Asyncio queue for feedback
        runtime_service: Runtime service instance
        event_loop: Event loop for async operations
        require_auth: Authentication decorator function
        rate_limiter: Optional rate limiter instance
    """

    # Apply rate limiting decorator if available
    def rate_limit(limit_string):
        if rate_limiter:
            return rate_limiter.limit(limit_string)
        else:
            # No-op decorator if rate limiting not available
            def decorator(f):
                return f
            return decorator

    workbench = ParserLuaWorkbench()
    harness = HarnessOrchestrator()

    # ========================================================================
    # ROUTE: Health Check (public, no auth)
    # ========================================================================
    @app.route('/health')
    def health_check():
        """Public health check endpoint (no authentication required)."""
        try:
            status = {
                'status': 'healthy',
                'service': 'purple-pipeline-parser-eater',
                'version': '9.0.0',
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }

            if hasattr(service, 'get_status') and service:
                try:
                    service_status = service.get_status()
                    status['is_running'] = service_status.get('is_running', False)
                except Exception as e:
                    request_id = getattr(g, 'request_id', 'unknown')
                    logger.warning(f"Failed to get service status [Request {request_id}]: {e}")
                    status['is_running'] = False
            else:
                status['is_running'] = False

            status['request_id'] = getattr(g, 'request_id', 'unknown')
            http_status = 200 if status.get('is_running', False) else 503
            return jsonify(status), http_status

        except Exception as e:
            request_id = getattr(g, 'request_id', 'unknown')
            logger.error(f"Health check failed [Request {request_id}]: {e}")
            return jsonify({
                'status': 'unhealthy',
                'error': 'Health check failed',
                'request_id': request_id
            }), 503

    # ========================================================================
    # ROUTE: Home Page / Status Dashboard
    # ========================================================================
    @app.route('/')
    @require_auth
    @rate_limit("60 per minute")
    def index():
        """Main dashboard with approved/modified/rejected tracking"""
        nonce = getattr(g, 'csp_nonce', get_secure_nonce())
        request_id_raw = getattr(g, 'request_id', 'unknown')
        request_id = sanitize_request_id(request_id_raw) if request_id_raw != 'unknown' else 'unknown'

        return render_template_string(INDEX_TEMPLATE,
            csp_nonce=nonce,
            request_id=request_id,
            status=service.get_status(),
            pending=service.pending_conversions,
            approved=service.approved_conversions,
            rejected=service.rejected_conversions,
            modified=service.modified_conversions
        )

    # ========================================================================
    # ROUTE: Parser Lua Workbench Page
    # ========================================================================
    @app.route('/workbench')
    @require_auth
    @rate_limit("60 per minute")
    def parser_workbench_page():
        nonce = getattr(g, 'csp_nonce', get_secure_nonce())
        return render_template_string(WORKBENCH_TEMPLATE, csp_nonce=nonce)

    # ========================================================================
    # ROUTE: List Parsers for Workbench
    # ========================================================================
    @app.route('/api/v1/workbench/parsers')
    @require_auth
    @rate_limit("60 per minute")
    def parser_workbench_parsers():
        rows = workbench.list_parsers()
        return jsonify({"parsers": rows, "count": len(rows)})

    # ========================================================================
    # ROUTE: Build Parser Lua + Example Log
    # ========================================================================
    @app.route('/api/v1/workbench/build', methods=['POST'])
    @require_auth
    @rate_limit("20 per minute")
    def parser_workbench_build():
        request_id = getattr(g, 'request_id', 'unknown')
        data = request.json or {}
        parser_name = data.get('parser_name')

        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({
                'error': error_msg or 'Invalid parser name format',
                'request_id': request_id
            }), 400

        payload = workbench.build_parser(parser_name)
        if not payload:
            return jsonify({
                'error': 'Parser not found in conversion output',
                'request_id': request_id
            }), 404

        payload['request_id'] = request_id
        return jsonify(payload)

    # ========================================================================
    # ROUTE: Run Full Testing Harness
    # ========================================================================
    @app.route('/api/v1/workbench/validate/<parser_name>', methods=['GET'])
    @require_auth
    @rate_limit("20 per minute")
    def workbench_validate(parser_name):
        """Run all 5 testing harness checks for a parser."""
        request_id = getattr(g, 'request_id', 'unknown')
        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        ocsf_version = request.args.get('ocsf_version', '1.3.0')
        entry = workbench._find_entry(parser_name)
        if not entry:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        from components.lua_exporter import build_lua_content
        lua_data = build_lua_content(entry)
        lua_code = lua_data["content"]
        parser_config = entry.get("config") or entry

        report = harness.run_all_checks(
            lua_code=lua_code,
            parser_config=parser_config,
            ocsf_version=ocsf_version,
        )
        report['request_id'] = request_id
        report['parser_name'] = parser_name
        return jsonify(report)

    # ========================================================================
    # ROUTE: Run Lua Linting Only
    # ========================================================================
    @app.route('/api/v1/workbench/lint/<parser_name>', methods=['GET'])
    @require_auth
    @rate_limit("30 per minute")
    def workbench_lint(parser_name):
        """Run Lua linting for a parser."""
        request_id = getattr(g, 'request_id', 'unknown')
        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        entry = workbench._find_entry(parser_name)
        if not entry:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        from components.lua_exporter import build_lua_content
        lua_code = build_lua_content(entry)["content"]
        result = harness.run_single_check("lua_linting", lua_code)
        result['request_id'] = request_id
        return jsonify(result)

    # ========================================================================
    # ROUTE: OCSF Field Mapping Analysis
    # ========================================================================
    @app.route('/api/v1/workbench/ocsf-mapping/<parser_name>', methods=['GET'])
    @require_auth
    @rate_limit("30 per minute")
    def workbench_ocsf_mapping(parser_name):
        """Analyze OCSF field mapping for a parser."""
        request_id = getattr(g, 'request_id', 'unknown')
        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        ocsf_version = request.args.get('ocsf_version', '1.3.0')
        entry = workbench._find_entry(parser_name)
        if not entry:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        from components.lua_exporter import build_lua_content
        lua_code = build_lua_content(entry)["content"]
        result = harness.run_single_check("ocsf_mapping", lua_code, ocsf_version=ocsf_version)
        result['request_id'] = request_id
        return jsonify(result)

    # ========================================================================
    # ROUTE: Source Parser Field Inventory
    # ========================================================================
    @app.route('/api/v1/workbench/source-fields/<parser_name>', methods=['GET'])
    @require_auth
    @rate_limit("30 per minute")
    def workbench_source_fields(parser_name):
        """Get source parser field inventory."""
        request_id = getattr(g, 'request_id', 'unknown')
        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        entry = workbench._find_entry(parser_name)
        if not entry:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        parser_config = entry.get("config") or entry
        result = harness.run_single_check("source_fields", "", parser_config=parser_config)
        result['request_id'] = request_id
        return jsonify(result)

    # ========================================================================
    # ROUTE: Run Test Events
    # ========================================================================
    @app.route('/api/v1/workbench/test-run/<parser_name>', methods=['POST'])
    @require_auth
    @rate_limit("10 per minute")
    def workbench_test_run(parser_name):
        """Execute test events against generated Lua."""
        request_id = getattr(g, 'request_id', 'unknown')
        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        entry = workbench._find_entry(parser_name)
        if not entry:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        from components.lua_exporter import build_lua_content
        lua_code = build_lua_content(entry)["content"]

        data = request.json or {}
        custom_events = data.get('test_events')

        parser_config = entry.get("config") or entry
        report = harness.run_all_checks(
            lua_code=lua_code,
            parser_config=parser_config,
            custom_test_events=custom_events,
        )
        result = report.get("checks", {}).get("test_execution", {})
        result['request_id'] = request_id
        return jsonify(result)

    # ========================================================================
    # ROUTE: List OCSF Versions and Classes
    # ========================================================================
    @app.route('/api/v1/workbench/ocsf-versions', methods=['GET'])
    @require_auth
    @rate_limit("60 per minute")
    def workbench_ocsf_versions():
        """List available OCSF versions and classes."""
        request_id = getattr(g, 'request_id', 'unknown')
        version = request.args.get('version', '1.3.0')
        return jsonify({
            'versions': harness.ocsf_registry.list_versions(),
            'classes': harness.ocsf_registry.list_classes(version),
            'request_id': request_id
        })

    # ========================================================================
    # ROUTE: AI Agent Generate Lua
    # ========================================================================
    @app.route('/api/v1/workbench/agent-build', methods=['POST'])
    @require_auth
    @rate_limit("5 per minute")
    def workbench_agent_build():
        """Generate Lua via the agentic LLM workflow with harness feedback loop."""
        request_id = getattr(g, 'request_id', 'unknown')
        data = request.json or {}
        parser_name = data.get('parser_name')

        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400

        force = data.get('force_regenerate', False)
        result = workbench.build_parser_with_agent(parser_name, force_regenerate=force)
        if not result:
            return jsonify({'error': 'Parser not found', 'request_id': request_id}), 404

        result['request_id'] = request_id
        return jsonify(result)

    # ========================================================================
    # ROUTE: Agent Cache Stats
    # ========================================================================
    @app.route('/api/v1/workbench/agent-cache-stats', methods=['GET'])
    @require_auth
    @rate_limit("30 per minute")
    def workbench_agent_cache_stats():
        """Get agent cache statistics."""
        request_id = getattr(g, 'request_id', 'unknown')
        agent = workbench._get_agent()
        if not agent:
            return jsonify({'error': 'Agent not available', 'request_id': request_id}), 503
        stats = agent.get_cache_stats()
        stats['request_id'] = request_id
        return jsonify(stats)

    # ========================================================================
    # ROUTE: Batch Status
    # ========================================================================
    @app.route('/api/v1/workbench/batch-status', methods=['GET'])
    @require_auth
    @rate_limit("30 per minute")
    def workbench_batch_status():
        """Get batch generation results and aggregate stats."""
        request_id = getattr(g, 'request_id', 'unknown')
        import json as _json
        from pathlib import Path as _Path
        batch_file = _Path("output/batch_agent_results.json")
        if not batch_file.exists():
            return jsonify({
                'status': 'no_results',
                'message': 'No batch run results found. Run scripts/batch_agent_generate.py first.',
                'request_id': request_id,
            })
        try:
            data = _json.loads(batch_file.read_text())
            return jsonify({
                'status': 'ok',
                'summary': data.get('summary', {}),
                'started_at': data.get('started_at'),
                'completed_at': data.get('completed_at'),
                'config': data.get('config', {}),
                'parsers': data.get('parsers', []),
                'request_id': request_id,
            })
        except Exception as e:
            return jsonify({
                'status': 'error',
                'error': str(e),
                'request_id': request_id,
            }), 500

    # ========================================================================
    # ROUTE: Upload Lua as PR (optional)
    # ========================================================================
    @app.route('/api/v1/workbench/upload-pr', methods=['POST'])
    @require_auth
    @rate_limit("3 per minute")
    def workbench_upload_pr():
        """Create a GitHub PR with the generated Lua for review."""
        request_id = getattr(g, 'request_id', 'unknown')
        data = request.json or {}
        parser_name = data.get('parser_name')
        lua_code = data.get('lua_code')

        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            return jsonify({'error': error_msg, 'request_id': request_id}), 400
        if not lua_code:
            return jsonify({'error': 'No Lua code provided', 'request_id': request_id}), 400

        import os
        github_token = os.environ.get('GITHUB_TOKEN')
        if not github_token or github_token == 'dry-run-mode':
            return jsonify({
                'error': 'GITHUB_TOKEN not configured - set it to create PRs',
                'request_id': request_id
            }), 503

        try:
            import subprocess
            from components.ai_siem_pipeline_converter import normalize_name
            slug = normalize_name(parser_name) or 'unknown'
            branch_name = f"lua/{slug}"

            # Create branch, write file, commit, push, create PR
            lua_path = f"output/parser_lua_serializers/{slug}.lua"
            subprocess.run(['git', 'checkout', '-b', branch_name], check=True, capture_output=True)
            Path(lua_path).parent.mkdir(parents=True, exist_ok=True)
            Path(lua_path).write_text(lua_code, encoding='utf-8')
            subprocess.run(['git', 'add', lua_path], check=True, capture_output=True)
            subprocess.run(
                ['git', 'commit', '-m', f'Add agent-generated Lua for {parser_name}'],
                check=True, capture_output=True
            )
            subprocess.run(['git', 'push', '-u', 'origin', branch_name], check=True, capture_output=True)

            # Create PR via gh CLI
            pr_result = subprocess.run(
                ['gh', 'pr', 'create',
                 '--title', f'Add Lua transformation: {parser_name}',
                 '--body', f'Agent-generated OCSF Lua for `{parser_name}`.\n\nReview the transformation and approve for merge.'],
                check=True, capture_output=True, text=True
            )
            pr_url = pr_result.stdout.strip()

            # Return to original branch
            subprocess.run(['git', 'checkout', '-'], capture_output=True)

            return jsonify({
                'status': 'pr_created',
                'pr_url': pr_url,
                'branch': branch_name,
                'parser_name': parser_name,
                'request_id': request_id
            })

        except subprocess.CalledProcessError as e:
            # Clean up: return to original branch
            subprocess.run(['git', 'checkout', '-'], capture_output=True)
            return jsonify({
                'error': f'Git operation failed: {e.stderr.decode() if e.stderr else str(e)}',
                'request_id': request_id
            }), 500
        except Exception as e:
            return jsonify({'error': str(e), 'request_id': request_id}), 500

    # ========================================================================
    # ROUTE: Get Pending Conversions
    # ========================================================================
    @app.route('/api/v1/pending')
    @rate_limit("30 per minute")
    @require_auth
    def get_pending():
        """Get pending conversions"""
        request_id = getattr(g, 'request_id', 'unknown')
        return jsonify({
            'pending': list(service.pending_conversions.values()),
            'request_id': request_id
        })

    # ========================================================================
    # ROUTE: Get Conversion Details
    # ========================================================================
    @app.route('/api/v1/conversion/<parser_name>')
    @require_auth
    def get_conversion(parser_name):
        """Get specific conversion details"""
        request_id = getattr(g, 'request_id', 'unknown')

        is_valid, error_msg = validate_parser_name(parser_name)
        if not is_valid:
            safe_parser_name = sanitize_log_input(parser_name)
            logger.warning(f"Invalid parser name format [Request {request_id}]: {safe_parser_name}")
            return jsonify({
                'error': error_msg or 'Invalid parser name format',
                'request_id': request_id
            }), 400

        conversion = service.pending_conversions.get(parser_name)
        if not conversion:
            return jsonify({
                'error': 'Not found',
                'request_id': request_id
            }), 404

        conversion_response = dict(conversion)
        conversion_response['request_id'] = request_id
        return jsonify(conversion_response)

    # ========================================================================
    # ROUTE: Approve Conversion
    # ========================================================================
    @app.route('/api/v1/approve', methods=['POST'])
    @rate_limit("5 per minute")
    @require_auth
    def approve_conversion():
        """Approve a conversion"""
        request_id = getattr(g, 'request_id', 'unknown')
        max_json_size = int(__import__('os').environ.get('MAX_JSON_SIZE', 1024 * 1024))

        if request.content_length and request.content_length > max_json_size:
            logger.warning(f"Payload too large [Request {request_id}]: {request.content_length} bytes")
            return jsonify({
                'error': 'Payload too large',
                'max_size': max_json_size,
                'request_id': request_id
            }), 413

        data = request.json
        parser_name = data.get('parser_name')

        if parser_name not in service.pending_conversions:
            return jsonify({
                'error': 'Not found',
                'request_id': request_id
            }), 404

        conversion = service.pending_conversions[parser_name]
        if conversion.get('status') == 'processing':
            return jsonify({
                'error': 'Already processing',
                'request_id': request_id
            }), 409

        conversion['status'] = 'processing'
        conversion['processing_action'] = 'approve'
        conversion['processing_timestamp'] = datetime.now().isoformat()

        if not event_loop:
            return jsonify({
                'error': 'Event loop not configured',
                'request_id': request_id
            }), 500

        asyncio.run_coroutine_threadsafe(
            feedback_queue.put({
                'parser_name': parser_name,
                'action': 'approve',
                'timestamp': datetime.now().isoformat()
            }),
            event_loop
        )

        return jsonify({
            'status': 'approved',
            'parser_name': parser_name,
            'request_id': request_id
        })

    # ========================================================================
    # ROUTE: Reject Conversion
    # ========================================================================
    @app.route('/api/v1/reject', methods=['POST'])
    @rate_limit("5 per minute")
    @require_auth
    def reject_conversion():
        """Reject a conversion"""
        request_id = getattr(g, 'request_id', 'unknown')
        max_json_size = int(__import__('os').environ.get('MAX_JSON_SIZE', 1024 * 1024))

        if request.content_length and request.content_length > max_json_size:
            logger.warning(f"Payload too large [Request {request_id}]: {request.content_length} bytes")
            return jsonify({
                'error': 'Payload too large',
                'max_size': max_json_size,
                'request_id': request_id
            }), 413

        data = request.json
        parser_name = data.get('parser_name')
        reason = data.get('reason', 'User rejected')
        retry = data.get('retry', False)

        if parser_name not in service.pending_conversions:
            return jsonify({
                'error': 'Not found',
                'request_id': request_id
            }), 404

        conversion = service.pending_conversions[parser_name]
        if conversion.get('status') == 'processing':
            return jsonify({
                'error': 'Already processing',
                'request_id': request_id
            }), 409

        conversion['status'] = 'processing'
        conversion['processing_action'] = 'reject'
        conversion['processing_timestamp'] = datetime.now().isoformat()

        if not event_loop:
            return jsonify({
                'error': 'Event loop not configured',
                'request_id': request_id
            }), 500

        asyncio.run_coroutine_threadsafe(
            feedback_queue.put({
                'parser_name': parser_name,
                'action': 'reject',
                'reason': reason,
                'retry': retry,
                'timestamp': datetime.now().isoformat()
            }),
            event_loop
        )

        return jsonify({
            'status': 'rejected',
            'parser_name': parser_name,
            'request_id': request_id
        })

    # ========================================================================
    # ROUTE: Modify Conversion
    # ========================================================================
    @app.route('/api/v1/modify', methods=['POST'])
    @rate_limit("5 per minute")
    @require_auth
    def modify_conversion():
        """Modify a conversion"""
        request_id = getattr(g, 'request_id', 'unknown')
        max_json_size = int(__import__('os').environ.get('MAX_JSON_SIZE', 1024 * 1024))

        if request.content_length and request.content_length > max_json_size:
            logger.warning(f"Payload too large [Request {request_id}]: {request.content_length} bytes")
            return jsonify({
                'error': 'Payload too large',
                'max_size': max_json_size,
                'request_id': request_id
            }), 413

        data = request.json
        parser_name = data.get('parser_name')
        corrected_lua = data.get('corrected_lua')
        reason = data.get('reason', 'User modification')

        if parser_name not in service.pending_conversions:
            return jsonify({
                'error': 'Not found',
                'request_id': request_id
            }), 404

        if not corrected_lua:
            return jsonify({
                'error': 'No corrected LUA provided',
                'request_id': request_id
            }), 400

        conversion = service.pending_conversions[parser_name]
        if conversion.get('status') == 'processing':
            return jsonify({
                'error': 'Already processing',
                'request_id': request_id
            }), 409

        conversion['status'] = 'processing'
        conversion['processing_action'] = 'modify'
        conversion['processing_timestamp'] = datetime.now().isoformat()

        if not event_loop:
            return jsonify({
                'error': 'Event loop not configured',
                'request_id': request_id
            }), 500

        asyncio.run_coroutine_threadsafe(
            feedback_queue.put({
                'parser_name': parser_name,
                'action': 'modify',
                'corrected_lua': corrected_lua,
                'reason': reason,
                'timestamp': datetime.now().isoformat()
            }),
            event_loop
        )

        return jsonify({
            'status': 'modified',
            'parser_name': parser_name,
            'request_id': request_id
        })

    # ========================================================================
    # ROUTE: Get Service Status
    # ========================================================================
    @app.route('/api/v1/status')
    @require_auth
    def get_status():
        """Get service status"""
        return jsonify(service.get_status())

    # ========================================================================
    # ROUTE: Get Runtime Status
    # ========================================================================
    @app.route('/api/v1/runtime/status')
    @require_auth
    def runtime_status():
        """Runtime metrics endpoint."""
        runtime_svc = runtime_service or service
        return jsonify(runtime_svc.get_runtime_status())

    # ========================================================================
    # ROUTE: Request Runtime Reload
    # ========================================================================
    @app.route('/api/v1/runtime/reload/<parser_id>', methods=['POST'])
    @require_auth
    def runtime_reload(parser_id: str):
        """Request runtime reload"""
        runtime_svc = runtime_service or service
        if runtime_svc.request_runtime_reload(parser_id):
            return jsonify({"status": "reload_requested", "parser_id": parser_id})
        return jsonify({"error": "not_found"}), 404

    # ========================================================================
    # ROUTE: Clear Runtime Reload
    # ========================================================================
    @app.route('/api/v1/runtime/reload/<parser_id>', methods=['DELETE'])
    @require_auth
    def runtime_reload_ack(parser_id: str):
        """Clear runtime reload request"""
        runtime_svc = runtime_service or service
        if runtime_svc.pop_runtime_reload(parser_id):
            return jsonify({"status": "reload_cleared", "parser_id": parser_id})
        return jsonify({"error": "not_found"}), 404

    # ========================================================================
    # ROUTE: Request Canary Promotion
    # ========================================================================
    @app.route('/api/v1/runtime/canary/<parser_id>/promote', methods=['POST'])
    @require_auth
    def runtime_canary_promote(parser_id: str):
        """Request canary promotion"""
        runtime_svc = runtime_service or service
        if runtime_svc.request_canary_promotion(parser_id):
            return jsonify({"status": "promotion_requested", "parser_id": parser_id})
        return jsonify({"error": "not_found"}), 404

    # ========================================================================
    # ROUTE: Clear Canary Promotion
    # ========================================================================
    @app.route('/api/v1/runtime/canary/<parser_id>/promote', methods=['DELETE'])
    @require_auth
    def runtime_canary_promote_ack(parser_id: str):
        """Clear canary promotion request"""
        runtime_svc = runtime_service or service
        if runtime_svc.pop_canary_promotion(parser_id):
            return jsonify({"status": "promotion_cleared", "parser_id": parser_id})
        return jsonify({"error": "not_found"}), 404

    # ========================================================================
    # ROUTE: Get Prometheus Metrics
    # ========================================================================
    @app.route('/api/v1/metrics')
    def get_metrics():
        """
        Get Prometheus metrics.
        SECURITY: This endpoint does NOT require authentication to allow
        Prometheus scraping without credentials.
        """
        try:
            from services.output_service import get_metrics
            return get_metrics()
        except ImportError:
            return """# HELP pppe_status System status
# TYPE pppe_status gauge
pppe_status 1
"""

    # ========================================================================
    # ROUTE: Get CSRF Token
    # ========================================================================
    @app.route('/api/csrf-token', methods=['GET'])
    @require_auth
    def get_csrf_token():
        """
        Get CSRF token for client-side requests
        SECURITY: Required for all POST/PUT/DELETE requests
        """
        token = generate_csrf()
        return jsonify({'csrf_token': token})

    # ========================================================================
    # ERROR HANDLER: CSRF Error
    # ========================================================================
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Handle CSRF validation failures"""
        logger.warning(f"CSRF validation failed: {e.description}")
        return jsonify({
            'error': 'CSRF validation failed',
            'message': 'Invalid or missing CSRF token. Please refresh the page.',
            'code': 'CSRF_ERROR'
        }), 400

    logger.info("[OK] All routes registered successfully")
