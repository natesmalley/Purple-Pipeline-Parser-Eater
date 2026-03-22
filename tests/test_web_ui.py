#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Web UI - Standalone Demo

This script starts just the web UI with mock data to verify it's working.
"""

from flask import Flask, render_template_string, request, jsonify
from datetime import datetime
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Mock data for testing
mock_pending_conversions = {
    'aws_cloudtrail-latest': {
        'parser_info': {
            'parser_name': 'aws_cloudtrail-latest',
            'metadata': {
                'description': 'AWS CloudTrail logs',
                'author': 'SentinelOne',
                'version': 'v1.0'
            }
        },
        'conversion_result': {
            'lua_code': '''-- AWS CloudTrail Parser
function transform(event)
    -- Set OCSF class and activity
    event.class_uid = 3005  -- Authentication
    event.activity_id = 1   -- Logon
    event.category_uid = 3  -- Identity & Access Management

    -- Map user information
    if event.userIdentity and event.userIdentity.userName then
        event.user = event.user or {}
        event.user.name = event.userIdentity.userName
    end

    -- Map source IP
    if event.sourceIPAddress then
        event.src_endpoint = event.src_endpoint or {}
        event.src_endpoint.ip = event.sourceIPAddress
    end

    -- Map event details
    if event.eventName then
        event.activity_name = event.eventName
    end

    return event
end''',
            'generation_time': 5.2,
            'strategy': 'rag_enhanced'
        },
        'status': 'pending_review',
        'timestamp': datetime.now().isoformat()
    },
    'okta_logs-latest': {
        'parser_info': {
            'parser_name': 'okta_logs-latest',
            'metadata': {
                'description': 'Okta authentication logs',
                'author': 'SentinelOne',
                'version': 'v1.0'
            }
        },
        'conversion_result': {
            'lua_code': '''-- Okta Authentication Parser
function transform(event)
    -- Set OCSF class and activity
    event.class_uid = 3002  -- Account Change
    event.activity_id = 1   -- Create
    event.category_uid = 3  -- Identity & Access Management

    -- Map actor information
    if event.actor and event.actor.displayName then
        event.actor = event.actor or {}
        event.actor.user = event.actor.user or {}
        event.actor.user.name = event.actor.displayName
    end

    -- Map target
    if event.target then
        event.user = event.user or {}
        event.user.name = event.target[1].displayName or "unknown"
    end

    return event
end''',
            'generation_time': 4.8,
            'strategy': 'rag_enhanced'
        },
        'status': 'pending_review',
        'timestamp': datetime.now().isoformat()
    },
    'cisco_duo-latest': {
        'parser_info': {
            'parser_name': 'cisco_duo-latest',
            'metadata': {
                'description': 'Cisco Duo MFA logs',
                'author': 'SentinelOne',
                'version': 'v1.0'
            }
        },
        'conversion_result': {
            'lua_code': '''-- Cisco Duo MFA Parser
function transform(event)
    -- Set OCSF class and activity
    event.class_uid = 3005  -- Authentication
    event.activity_id = 1   -- Logon
    event.category_uid = 3  -- Identity & Access Management

    -- Map user
    if event.username then
        event.user = event.user or {}
        event.user.name = event.username
    end

    -- Map device
    if event.device then
        event.device = event.device or {}
        event.device.name = event.device
    end

    -- Map result
    if event.result then
        event.status = event.result == "SUCCESS" and "Success" or "Failure"
    end

    return event
end''',
            'generation_time': 6.1,
            'strategy': 'rag_enhanced'
        },
        'status': 'pending_review',
        'timestamp': datetime.now().isoformat()
    }
}

mock_status = {
    'is_running': True,
    'pending_conversions': len(mock_pending_conversions),
    'approved_conversions': 12,
    'rejected_conversions': 2,
    'queue_size': 5
}

# Flask app
app = Flask(__name__)

# HTML Template (same as in web_feedback_ui.py)
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Purple Pipeline Parser Eater - Feedback UI (DEMO)</title>
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
        .demo-badge {
            display: inline-block;
            background: #ffc107;
            color: #333;
            padding: 5px 15px;
            border-radius: 5px;
            font-weight: bold;
            margin-left: 10px;
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
        .metadata {
            color: #666;
            font-size: 13px;
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
        .success-msg {
            background: #d4edda;
            color: #155724;
            padding: 15px;
            border-radius: 5px;
            margin: 10px 0;
            display: none;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>[PPPE] Purple Pipeline Parser Eater - Feedback UI <span class="demo-badge">DEMO MODE</span></h1>
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

        <div id="successMsg" class="success-msg"></div>

        <div class="conversion-list">
            <h2>Pending Conversions (Demo Data)</h2>

            {% for parser_name, conversion in pending.items() %}
            <div class="conversion-item" id="conversion-{{ parser_name }}">
                <div class="parser-name">{{ parser_name }}</div>
                <div class="metadata">
                    {{ conversion.parser_info.metadata.description }} |
                    Generated in {{ conversion.conversion_result.generation_time }}s |
                    Strategy: {{ conversion.conversion_result.strategy }}
                </div>
                <div class="timestamp">Converted: {{ conversion.timestamp }}</div>

                <div class="code-preview">{{ conversion.conversion_result.lua_code[:500] }}...

(Click "Modify" to see full code)</div>

                <div class="button-group">
                    <button class="btn btn-approve" onclick="approveConversion('{{ parser_name }}')">
                        [OK] Approve
                    </button>
                    <button class="btn btn-reject" onclick="rejectConversion('{{ parser_name }}')">
                        [ERROR] Reject
                    </button>
                    <button class="btn btn-modify" onclick="modifyConversion('{{ parser_name }}')">
                        [EDIT] Modify
                    </button>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <!-- Modify Modal -->
    <div id="modifyModal" class="modal">
        <div class="modal-content">
            <h2>Modify LUA Code</h2>
            <p id="modalParserName" style="color: #666; margin: 10px 0;"></p>
            <textarea id="luaEditor" class="editor"></textarea>
            <div class="button-group">
                <button class="btn btn-approve" onclick="saveModification()">Save & Approve</button>
                <button class="btn btn-reject" onclick="closeModal()">Cancel</button>
            </div>
        </div>
    </div>

    <script>
        let currentParser = null;
        let currentCode = null;

        const conversions = {{ pending | tojson }};

        function showSuccess(message) {
            const msg = document.getElementById('successMsg');
            msg.textContent = message;
            msg.style.display = 'block';
            setTimeout(() => { msg.style.display = 'none'; }, 3000);
        }

        function approveConversion(parserName) {
            if (!confirm(`[OK] Approve conversion for ${parserName}?`)) return;

            showSuccess(`[OK] Approved: ${parserName} (DEMO: No actual deployment)`);
            document.getElementById('conversion-' + parserName).style.opacity = '0.5';

            setTimeout(() => {
                document.getElementById('conversion-' + parserName).remove();
            }, 1000);
        }

        function rejectConversion(parserName) {
            const reason = prompt(`Why are you rejecting ${parserName}?`, 'OCSF class incorrect');
            if (!reason) return;

            const retry = confirm('Retry with different strategy?');

            showSuccess(`[ERROR] Rejected: ${parserName}${retry ? ' (will retry)' : ''} (DEMO)`);
            document.getElementById('conversion-' + parserName).style.opacity = '0.5';

            setTimeout(() => {
                document.getElementById('conversion-' + parserName).remove();
            }, 1000);
        }

        function modifyConversion(parserName) {
            currentParser = parserName;
            currentCode = conversions[parserName].conversion_result.lua_code;

            document.getElementById('modalParserName').textContent = parserName;
            document.getElementById('luaEditor').value = currentCode;
            document.getElementById('modifyModal').style.display = 'block';
        }

        function saveModification() {
            const correctedLua = document.getElementById('luaEditor').value;
            const reason = prompt('What did you change and why?', 'Changed OCSF class from 3005 to 3002');

            if (!reason) return;

            showSuccess(`[EDIT] Modified and approved: ${currentParser} (DEMO: Learning recorded)`);
            closeModal();

            document.getElementById('conversion-' + currentParser).style.opacity = '0.5';
            setTimeout(() => {
                document.getElementById('conversion-' + currentParser).remove();
            }, 1000);
        }

        function closeModal() {
            document.getElementById('modifyModal').style.display = 'none';
            currentParser = null;
            currentCode = null;
        }

        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('modifyModal');
            if (event.target == modal) {
                closeModal();
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(INDEX_TEMPLATE,
        status=mock_status,
        pending=mock_pending_conversions
    )

@app.route('/api/status')
def get_status():
    return jsonify(mock_status)

@app.route('/api/pending')
def get_pending():
    return jsonify({'pending': list(mock_pending_conversions.values())})

if __name__ == '__main__':
    print("\n" + "=" * 70)
    print("WEB UI DEMO MODE")
    print("=" * 70)
    print("\nStarting web server with DEMO DATA...")
    print("\nOpen your browser to: http://localhost:8080")
    print("\nThis is a standalone demo to verify the UI works.")
    print("It shows mock parser conversions that you can interact with.")
    print("\nPress Ctrl+C to stop.\n")
    print("=" * 70 + "\n")

    app.run(host='0.0.0.0', port=8080, debug=False)
