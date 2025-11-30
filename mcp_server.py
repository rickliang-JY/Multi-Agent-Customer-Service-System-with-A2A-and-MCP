# MCP Server for Customer Management
# Standalone version - Run in terminal: python mcp_server.py

from flask import Flask, request, Response, jsonify
from flask_cors import CORS
import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, Any, Optional

# ============================================================
# Configuration
# ============================================================

# Database path - Ensure support.db is in the same directory
DB_PATH = "support.db"

# Server configuration
SERVER_HOST = '127.0.0.1'
SERVER_PORT = 5000

# ============================================================
# Flask App
# ============================================================

app = Flask(__name__)
CORS(app)

# ============================================================
# Database Functions
# ============================================================

def get_db_connection():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
    """Convert database row to dictionary"""
    return {key: row[key] for key in row.keys()}


# ============================================================
# Tool Functions (5 tools)
# ============================================================

def get_customer(customer_id: int) -> Dict[str, Any]:
    """TOOL 1: Get customer information by ID"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return {'success': True, 'customer': row_to_dict(row)}
        else:
            return {'success': False, 'error': f'Customer with ID {customer_id} not found'}
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}


def list_customers(status: Optional[str] = None, limit: int = 100) -> Dict[str, Any]:
    """TOOL 2: List customers, optionally filter by status"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        if status and status not in ['active', 'disabled']:
            return {'success': False, 'error': 'Status must be "active", "disabled", or null'}

        limit = max(1, min(limit, 1000))

        if status:
            cursor.execute('SELECT * FROM customers WHERE status = ? ORDER BY name LIMIT ?', (status, limit))
        else:
            cursor.execute('SELECT * FROM customers ORDER BY name LIMIT ?', (limit,))

        rows = cursor.fetchall()
        conn.close()
        customers = [row_to_dict(row) for row in rows]

        return {'success': True, 'count': len(customers), 'customers': customers}
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}


def update_customer(customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """TOOL 3: Update customer information"""
    try:
        if not data or not isinstance(data, dict):
            return {'success': False, 'error': 'Data must be a non-empty dictionary'}

        allowed_fields = {'name', 'email', 'phone', 'status'}
        invalid_fields = set(data.keys()) - allowed_fields
        if invalid_fields:
            return {'success': False, 'error': f'Invalid fields: {invalid_fields}'}

        if 'status' in data and data['status'] not in ['active', 'disabled']:
            return {'success': False, 'error': 'Status must be "active" or "disabled"'}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return {'success': False, 'error': f'Customer with ID {customer_id} not found'}

        updates = []
        params = []
        for field, value in data.items():
            if value is not None:
                updates.append(f'{field} = ?')
                params.append(value.strip() if isinstance(value, str) else value)

        if not updates:
            conn.close()
            return {'success': False, 'error': 'No valid fields to update'}

        updates.append('updated_at = CURRENT_TIMESTAMP')
        params.append(customer_id)

        cursor.execute(f'UPDATE customers SET {", ".join(updates)} WHERE id = ?', params)
        conn.commit()

        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        conn.close()

        return {'success': True, 'message': f'Customer {customer_id} updated', 'customer': row_to_dict(row)}
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}


def create_ticket(customer_id: int, issue: str, priority: str = 'medium') -> Dict[str, Any]:
    """TOOL 4: Create a support ticket"""
    try:
        if not issue or not issue.strip():
            return {'success': False, 'error': 'Issue description is required'}

        valid_priorities = ['low', 'medium', 'high', 'urgent']
        if priority not in valid_priorities:
            return {'success': False, 'error': f'Priority must be one of: {valid_priorities}'}

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT id, name FROM customers WHERE id = ?', (customer_id,))
        customer = cursor.fetchone()
        if not customer:
            conn.close()
            return {'success': False, 'error': f'Customer with ID {customer_id} not found'}

        cursor.execute('''
            INSERT INTO tickets (customer_id, issue, priority, status)
            VALUES (?, ?, ?, 'open')
        ''', (customer_id, issue.strip(), priority))

        ticket_id = cursor.lastrowid
        conn.commit()

        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        ticket_row = cursor.fetchone()
        conn.close()

        return {'success': True, 'message': f'Ticket #{ticket_id} created', 'ticket': row_to_dict(ticket_row)}
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}


def get_customer_history(customer_id: int) -> Dict[str, Any]:
    """TOOL 5: Get customer's ticket history"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        customer_row = cursor.fetchone()
        if not customer_row:
            conn.close()
            return {'success': False, 'error': f'Customer with ID {customer_id} not found'}

        cursor.execute('SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC', (customer_id,))
        ticket_rows = cursor.fetchall()
        conn.close()

        tickets = [row_to_dict(row) for row in ticket_rows]
        customer = row_to_dict(customer_row)

        total_tickets = len(tickets)
        open_tickets = sum(1 for t in tickets if t['status'] in ['open', 'in_progress'])
        resolved_tickets = sum(1 for t in tickets if t['status'] in ['resolved', 'closed'])

        return {
            'success': True,
            'customer': customer,
            'summary': {
                'total_tickets': total_tickets,
                'open_tickets': open_tickets,
                'resolved_tickets': resolved_tickets
            },
            'tickets': tickets
        }
    except Exception as e:
        return {'success': False, 'error': f'Database error: {str(e)}'}


# ============================================================
# MCP Protocol Implementation
# ============================================================

# MCP Tool Definitions
MCP_TOOLS = [
    {
        "name": "get_customer",
        "description": "Retrieve a specific customer by their ID.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "The unique ID of the customer"
                }
            },
            "required": ["customer_id"]
        }
    },
    {
        "name": "list_customers",
        "description": "List all customers. Can filter by status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["active", "disabled"],
                    "description": "Optional filter by status"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results (default: 100)"
                }
            }
        }
    },
    {
        "name": "update_customer",
        "description": "Update customer information.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "Customer ID"
                },
                "data": {
                    "type": "object",
                    "description": "Fields to update: name, email, phone, status",
                    "properties": {
                        "name": {"type": "string"},
                        "email": {"type": "string"},
                        "phone": {"type": "string"},
                        "status": {"type": "string", "enum": ["active", "disabled"]}
                    }
                }
            },
            "required": ["customer_id", "data"]
        }
    },
    {
        "name": "create_ticket",
        "description": "Create a support ticket.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "Customer ID"
                },
                "issue": {
                    "type": "string",
                    "description": "Issue description"
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "urgent"],
                    "description": "Priority (default: medium)"
                }
            },
            "required": ["customer_id", "issue"]
        }
    },
    {
        "name": "get_customer_history",
        "description": "Get ticket history for a customer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {
                    "type": "integer",
                    "description": "Customer ID"
                }
            },
            "required": ["customer_id"]
        }
    }
]

# Tool function mapping
TOOL_FUNCTIONS = {
    "get_customer": get_customer,
    "list_customers": list_customers,
    "update_customer": update_customer,
    "create_ticket": create_ticket,
    "get_customer_history": get_customer_history,
}


def create_sse_message(data: Dict[str, Any]) -> str:
    """Format SSE message"""
    return f"data: {json.dumps(data)}\n\n"


def handle_initialize(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle initialize request"""
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {}},
            "serverInfo": {
                "name": "customer-management-server",
                "version": "1.0.0"
            }
        }
    }


def handle_tools_list(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tools/list request"""
    return {
        "jsonrpc": "2.0",
        "id": message.get("id"),
        "result": {"tools": MCP_TOOLS}
    }


def handle_tools_call(message: Dict[str, Any]) -> Dict[str, Any]:
    """Handle tools/call request"""
    params = message.get("params", {})
    tool_name = params.get("name")
    arguments = params.get("arguments", {})

    if tool_name not in TOOL_FUNCTIONS:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32601, "message": f"Tool not found: {tool_name}"}
        }

    try:
        result = TOOL_FUNCTIONS[tool_name](**arguments)
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "result": {
                "content": [{"type": "text", "text": json.dumps(result, indent=2)}]
            }
        }
    except Exception as e:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32603, "message": f"Tool execution error: {str(e)}"}
        }


def process_mcp_message(message: Dict[str, Any]) -> Dict[str, Any]:
    """Route MCP message to appropriate handler"""
    method = message.get("method")

    if method == "initialize":
        return handle_initialize(message)
    elif method == "tools/list":
        return handle_tools_list(message)
    elif method == "tools/call":
        return handle_tools_call(message)
    else:
        return {
            "jsonrpc": "2.0",
            "id": message.get("id"),
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


# ============================================================
# Flask Routes
# ============================================================

@app.route('/mcp', methods=['POST'])
def mcp_endpoint():
    """MCP main endpoint - SSE response"""
    message = request.get_json()

    def generate():
        try:
            print(f"[MCP] Method: {message.get('method')}")
            response = process_mcp_message(message)
            print(f"[MCP] Response sent")
            yield create_sse_message(response)
        except Exception as e:
            print(f"[ERROR] {e}")
            yield create_sse_message({
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": f"Error: {str(e)}"}
            })

    return Response(generate(), mimetype='text/event-stream')


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "server": "customer-management-mcp-server",
        "version": "1.0.0",
        "tools": [t["name"] for t in MCP_TOOLS]
    })


# ============================================================
# Main Entry Point
# ============================================================

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("MCP Server for Customer Management")
    print("=" * 60)
    print(f"Database: {DB_PATH}")
    print(f"Tools: {[t['name'] for t in MCP_TOOLS]}")
    print(f"MCP Endpoint: http://{SERVER_HOST}:{SERVER_PORT}/mcp")
    print(f"Health Check: http://{SERVER_HOST}:{SERVER_PORT}/health")
    print("=" * 60)
    print()
    print("MCP Inspector:")
    print("   1. Run: npx @modelcontextprotocol/inspector")
    print(f"   2. URL: http://{SERVER_HOST}:{SERVER_PORT}/mcp")
    print("   3. Transport: Streamable HTTP")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 60)
    print()

    # Check if database exists
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] Database file {DB_PATH} not found!")
        print("   Make sure support.db is in the current directory")
        print()

    # Start server
    app.run(host=SERVER_HOST, port=SERVER_PORT, debug=False, threaded=True)