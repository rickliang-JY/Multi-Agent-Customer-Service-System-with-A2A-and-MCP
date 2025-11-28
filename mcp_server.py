"""
MCP Server - Model Context Protocol Implementation
HTTP Server with JSON-RPC 2.0 endpoints for tool operations

Endpoints:
- GET  /health         - Health check
- POST /tools/list     - List available tools (MCP protocol)
- POST /tools/call     - Execute a tool (MCP protocol)
- POST /                - Generic JSON-RPC handler

Compatible with MCP Inspector for testing.
"""

import json
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ============================================================================
# Configuration
# ============================================================================

DB_PATH = "support.db"

# ============================================================================
# Database Helpers
# ============================================================================

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ============================================================================
# MCP Tool Functions
# ============================================================================

def get_customer(customer_id: int) -> Dict[str, Any]:
    """Get customer by ID"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {"success": True, "data": dict(row)}
        return {"success": False, "error": f"Customer {customer_id} not found"}
    except Exception as e:
        return {"success": False, "error": str(e)}

def list_customers(status: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
    """List customers with optional filter"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                'SELECT * FROM customers WHERE status = ? LIMIT ?',
                (status, limit)
            )
        else:
            cursor.execute('SELECT * FROM customers LIMIT ?', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        return {"success": True, "data": [dict(row) for row in rows], "count": len(rows)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_customer(customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update customer information"""
    try:
        conn = get_db()
        conn.execute("PRAGMA foreign_keys = ON")
        cursor = conn.cursor()
        
        # Check customer exists
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Customer {customer_id} not found"}
        
        allowed = ['name', 'email', 'phone', 'status']
        updates = []
        values = []
        
        for field, value in data.items():
            if field in allowed:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            conn.close()
            return {"success": False, "error": "No valid fields to update"}
        
        # Note: updated_at is handled by database trigger
        values.append(customer_id)
        
        cursor.execute(
            f"UPDATE customers SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()
        
        # Get updated customer
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        row = cursor.fetchone()
        conn.close()
        
        return {"success": True, "data": dict(row), "updated_fields": list(data.keys())}
    except Exception as e:
        return {"success": False, "error": str(e)}

def create_ticket(customer_id: int, issue: str, priority: str = "medium") -> Dict[str, Any]:
    """Create a support ticket"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Verify customer exists
        cursor.execute('SELECT id FROM customers WHERE id = ?', (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Customer {customer_id} not found"}
        
        if priority not in ['low', 'medium', 'high']:
            priority = 'medium'
        
        cursor.execute('''
            INSERT INTO tickets (customer_id, issue, status, priority)
            VALUES (?, ?, 'open', ?)
        ''', (customer_id, issue, priority))
        
        ticket_id = cursor.lastrowid
        conn.commit()
        
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        
        return {"success": True, "data": dict(row)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_customer_history(customer_id: int) -> Dict[str, Any]:
    """Get customer with ticket history"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM customers WHERE id = ?', (customer_id,))
        customer_row = cursor.fetchone()
        
        if not customer_row:
            conn.close()
            return {"success": False, "error": f"Customer {customer_id} not found"}
        
        cursor.execute('''
            SELECT * FROM tickets WHERE customer_id = ? ORDER BY created_at DESC
        ''', (customer_id,))
        tickets = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {
            "success": True,
            "data": {
                "customer": dict(customer_row),
                "tickets": tickets,
                "ticket_count": len(tickets)
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_tickets_by_priority(priority: str = "high", status: Optional[str] = None) -> Dict[str, Any]:
    """Get tickets by priority"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT t.*, c.name as customer_name, c.email as customer_email
                FROM tickets t
                JOIN customers c ON t.customer_id = c.id
                WHERE t.priority = ? AND t.status = ?
                ORDER BY t.created_at DESC
            ''', (priority, status))
        else:
            cursor.execute('''
                SELECT t.*, c.name as customer_name, c.email as customer_email
                FROM tickets t
                JOIN customers c ON t.customer_id = c.id
                WHERE t.priority = ?
                ORDER BY t.created_at DESC
            ''', (priority,))
        
        tickets = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return {"success": True, "data": tickets, "count": len(tickets)}
    except Exception as e:
        return {"success": False, "error": str(e)}

def update_ticket(ticket_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """Update ticket information"""
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        if not cursor.fetchone():
            conn.close()
            return {"success": False, "error": f"Ticket {ticket_id} not found"}
        
        # Only status and priority can be updated (no resolution/updated_at in this schema)
        allowed = ['status', 'priority']
        updates = []
        values = []
        
        for field, value in data.items():
            if field in allowed:
                updates.append(f"{field} = ?")
                values.append(value)
        
        if not updates:
            conn.close()
            return {"success": False, "error": "No valid fields to update"}
        
        values.append(ticket_id)
        
        cursor.execute(
            f"UPDATE tickets SET {', '.join(updates)} WHERE id = ?",
            values
        )
        conn.commit()
        
        cursor.execute('SELECT * FROM tickets WHERE id = ?', (ticket_id,))
        row = cursor.fetchone()
        conn.close()
        
        return {"success": True, "data": dict(row)}
    except Exception as e:
        return {"success": False, "error": str(e)}

# ============================================================================
# Tool Registry
# ============================================================================

TOOLS = {
    "get_customer": {
        "function": get_customer,
        "description": "Get customer information by ID",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer", "description": "Customer ID"}
            },
            "required": ["customer_id"]
        }
    },
    "list_customers": {
        "function": list_customers,
        "description": "List customers with optional status filter",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Filter by status"},
                "limit": {"type": "integer", "default": 20}
            }
        }
    },
    "update_customer": {
        "function": update_customer,
        "description": "Update customer information",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "data": {"type": "object", "description": "Fields to update"}
            },
            "required": ["customer_id", "data"]
        }
    },
    "create_ticket": {
        "function": create_ticket,
        "description": "Create a support ticket",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"},
                "issue": {"type": "string"},
                "priority": {"type": "string", "default": "medium"}
            },
            "required": ["customer_id", "issue"]
        }
    },
    "get_customer_history": {
        "function": get_customer_history,
        "description": "Get customer with ticket history",
        "inputSchema": {
            "type": "object",
            "properties": {
                "customer_id": {"type": "integer"}
            },
            "required": ["customer_id"]
        }
    },
    "get_tickets_by_priority": {
        "function": get_tickets_by_priority,
        "description": "Get tickets filtered by priority",
        "inputSchema": {
            "type": "object",
            "properties": {
                "priority": {"type": "string", "default": "high"},
                "status": {"type": "string"}
            }
        }
    },
    "update_ticket": {
        "function": update_ticket,
        "description": "Update ticket status or resolution",
        "inputSchema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer"},
                "data": {"type": "object"}
            },
            "required": ["ticket_id", "data"]
        }
    }
}

# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title="MCP Server - Customer Service",
    description="Model Context Protocol server for customer service database",
    version="1.0.0"
)

@app.get("/health")
async def health():
    """Health check"""
    return {"status": "healthy", "service": "mcp-server", "tools": len(TOOLS)}

@app.get("/.well-known/mcp.json")
async def mcp_manifest():
    """MCP server manifest"""
    return {
        "name": "Customer Service MCP Server",
        "version": "1.0.0",
        "description": "MCP server for customer service database operations",
        "tools": list(TOOLS.keys())
    }

@app.post("/tools/list")
async def tools_list():
    """List available MCP tools"""
    tools = []
    for name, info in TOOLS.items():
        tools.append({
            "name": name,
            "description": info["description"],
            "inputSchema": info["inputSchema"]
        })
    
    return {
        "jsonrpc": "2.0",
        "result": {"tools": tools}
    }

@app.post("/tools/call")
async def tools_call(request: Request):
    """Execute an MCP tool"""
    try:
        body = await request.json()
        params = body.get("params", {})
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return JSONResponse(status_code=400, content={
                "jsonrpc": "2.0",
                "error": {"code": -32602, "message": "Missing tool name"}
            })
        
        if tool_name not in TOOLS:
            return JSONResponse(status_code=400, content={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}
            })
        
        result = TOOLS[tool_name]["function"](**arguments)
        
        return {
            "jsonrpc": "2.0",
            "id": body.get("id"),
            "result": {
                "content": [{
                    "type": "text",
                    "text": json.dumps(result, indent=2, default=str)
                }]
            }
        }
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)}
        })

@app.post("/")
async def jsonrpc_handler(request: Request):
    """Generic JSON-RPC handler"""
    try:
        body = await request.json()
        method = body.get("method", "")
        
        if method == "tools/list":
            return await tools_list()
        elif method == "tools/call":
            return await tools_call(request)
        else:
            return JSONResponse(status_code=400, content={
                "jsonrpc": "2.0",
                "error": {"code": -32601, "message": f"Method '{method}' not found"}
            })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "jsonrpc": "2.0",
            "error": {"code": -32603, "message": str(e)}
        })

# ============================================================================
# Direct Access Client (for local use)
# ============================================================================

class MCPClient:
    """Local MCP client for direct tool access"""
    
    def call_tool(self, name: str, **kwargs) -> Dict[str, Any]:
        if name not in TOOLS:
            return {"success": False, "error": f"Tool '{name}' not found"}
        try:
            return TOOLS[name]["function"](**kwargs)
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_tools(self) -> List[str]:
        return list(TOOLS.keys())

mcp_client = MCPClient()

# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              MCP Server - Customer Service                   ║
╠══════════════════════════════════════════════════════════════╣
║  Port: {port}                                                  ║
║                                                              ║
║  Endpoints:                                                  ║
║    GET  /health         - Health check                       ║
║    POST /tools/list     - List tools                         ║
║    POST /tools/call     - Execute tool                       ║
║                                                              ║
║  Tools: {len(TOOLS)}                                                   ║
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=port)
