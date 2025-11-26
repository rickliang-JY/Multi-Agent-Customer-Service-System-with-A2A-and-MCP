"""
MCP Server Implementation for Customer Service System
Provides tools for customer and ticket management
"""

import sqlite3
import json
from datetime import datetime
from typing import Optional, List, Dict, Any
import asyncio

# Database connection
DB_PATH = 'support.db'

def get_db_connection():
    """Create database connection with row factory"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# MCP Tool Implementations

def get_customer(customer_id: int) -> Dict[str, Any]:
    """
    Get customer information by ID
    
    Args:
        customer_id: Customer ID to retrieve
        
    Returns:
        Customer data dictionary or error message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, name, email, phone, status, created_at, updated_at
            FROM customers
            WHERE id = ?
        ''', (customer_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return dict(row)
        else:
            return {"error": f"Customer {customer_id} not found"}
            
    except Exception as e:
        return {"error": str(e)}

def list_customers(status: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """
    List customers with optional status filter
    
    Args:
        status: Filter by status ('active' or 'disabled')
        limit: Maximum number of results
        
    Returns:
        List of customer dictionaries
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT id, name, email, phone, status, created_at, updated_at
                FROM customers
                WHERE status = ?
                LIMIT ?
            ''', (status, limit))
        else:
            cursor.execute('''
                SELECT id, name, email, phone, status, created_at, updated_at
                FROM customers
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        return [{"error": str(e)}]

def update_customer(customer_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update customer information
    
    Args:
        customer_id: Customer ID to update
        data: Dictionary with fields to update (name, email, phone, status, tier)
        
    Returns:
        Updated customer data or error message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Build update query dynamically
        allowed_fields = ['name', 'email', 'phone', 'status']
        update_fields = []
        values = []
        
        for field, value in data.items():
            if field in allowed_fields:
                update_fields.append(f"{field} = ?")
                values.append(value)
        
        if not update_fields:
            return {"error": "No valid fields to update"}
        
        # Add updated_at timestamp
        update_fields.append("updated_at = ?")
        values.append(datetime.now().isoformat())
        values.append(customer_id)
        
        query = f"UPDATE customers SET {', '.join(update_fields)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        
        if cursor.rowcount == 0:
            conn.close()
            return {"error": f"Customer {customer_id} not found"}
        
        conn.close()
        
        # Return updated customer
        return get_customer(customer_id)
        
    except Exception as e:
        return {"error": str(e)}

def create_ticket(customer_id: int, issue: str, priority: str = 'medium') -> Dict[str, Any]:
    """
    Create a new support ticket
    
    Args:
        customer_id: Customer ID for the ticket
        issue: Description of the issue
        priority: Priority level ('low', 'medium', 'high')
        
    Returns:
        Created ticket data or error message
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Validate customer exists
        cursor.execute('SELECT id FROM customers WHERE id = ?', (customer_id,))
        if not cursor.fetchone():
            conn.close()
            return {"error": f"Customer {customer_id} not found"}
        
        # Validate priority
        if priority not in ['low', 'medium', 'high']:
            priority = 'medium'
        
        # Create ticket
        cursor.execute('''
            INSERT INTO tickets (customer_id, issue, status, priority)
            VALUES (?, ?, 'open', ?)
        ''', (customer_id, issue, priority))
        
        ticket_id = cursor.lastrowid
        conn.commit()
        
        # Fetch created ticket
        cursor.execute('''
            SELECT id, customer_id, issue, status, priority, created_at
            FROM tickets
            WHERE id = ?
        ''', (ticket_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return dict(row)
        
    except Exception as e:
        return {"error": str(e)}

def get_customer_history(customer_id: int) -> Dict[str, Any]:
    """
    Get all tickets for a customer
    
    Args:
        customer_id: Customer ID to get history for
        
    Returns:
        Dictionary with customer info and their tickets
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get customer info
        cursor.execute('''
            SELECT id, name, email, status
            FROM customers
            WHERE id = ?
        ''', (customer_id,))
        
        customer_row = cursor.fetchone()
        if not customer_row:
            conn.close()
            return {"error": f"Customer {customer_id} not found"}
        
        customer = dict(customer_row)
        
        # Get tickets
        cursor.execute('''
            SELECT id, issue, status, priority, created_at
            FROM tickets
            WHERE customer_id = ?
            ORDER BY created_at DESC
        ''', (customer_id,))
        
        ticket_rows = cursor.fetchall()
        conn.close()
        
        # Add customer_name to each ticket
        tickets = []
        for row in ticket_rows:
            ticket = dict(row)
            ticket['customer_name'] = customer['name']  # Add customer name
            tickets.append(ticket)
        
        return {
            "customer": customer,
            "tickets": tickets,
            "total_tickets": len(tickets)
        }
        
    except Exception as e:
        return {"error": str(e)}

def get_tickets_by_priority(priority: str, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Get tickets by priority with optional status filter
    
    Args:
        priority: Priority level ('low', 'medium', 'high')
        status: Optional status filter ('open', 'in_progress', 'resolved')
        
    Returns:
        List of ticket dictionaries with customer info
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('''
                SELECT t.id, t.customer_id, c.name as customer_name,
                       t.issue, t.status, t.priority, t.created_at
                FROM tickets t
                JOIN customers c ON t.customer_id = c.id
                WHERE t.priority = ? AND t.status = ?
                ORDER BY t.created_at DESC
            ''', (priority, status))
        else:
            cursor.execute('''
                SELECT t.id, t.customer_id, c.name as customer_name,
                       t.issue, t.status, t.priority, t.created_at
                FROM tickets t
                JOIN customers c ON t.customer_id = c.id
                WHERE t.priority = ?
                ORDER BY t.created_at DESC
            ''', (priority,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
        
    except Exception as e:
        return [{"error": str(e)}]

# MCP Server Protocol Functions
# These would be called by the MCP client (agents)

class MCPServer:
    """MCP Server that exposes tools to agents"""
    
    def __init__(self):
        self.tools = {
            'get_customer': get_customer,
            'list_customers': list_customers,
            'update_customer': update_customer,
            'create_ticket': create_ticket,
            'get_customer_history': get_customer_history,
            'get_tickets_by_priority': get_tickets_by_priority
        }
    
    def call_tool(self, tool_name: str, **kwargs) -> Any:
        """
        Call a tool by name with arguments
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Arguments to pass to the tool
            
        Returns:
            Tool result
        """
        if tool_name not in self.tools:
            return {"error": f"Tool {tool_name} not found"}
        
        try:
            result = self.tools[tool_name](**kwargs)
            return result
        except Exception as e:
            return {"error": f"Tool execution failed: {str(e)}"}
    
    def list_tools(self) -> List[str]:
        """List available tools"""
        return list(self.tools.keys())

# Global MCP server instance
mcp_server = MCPServer()

if __name__ == '__main__':
    # Test the MCP server
    print("Testing MCP Server Tools...\n")
    
    # Test get_customer
    print("1. Get Customer (ID=1):")
    result = mcp_server.call_tool('get_customer', customer_id=1)
    print(json.dumps(result, indent=2))
    
    print("\n2. List Active Customers:")
    result = mcp_server.call_tool('list_customers', status='active', limit=5)
    print(json.dumps(result, indent=2))
    
    print("\n3. Create Ticket:")
    result = mcp_server.call_tool('create_ticket', 
                                   customer_id=1, 
                                   issue="Test issue",
                                   priority='high')
    print(json.dumps(result, indent=2))
    
    print("\n4. Get Customer History (ID=1):")
    result = mcp_server.call_tool('get_customer_history', customer_id=1)
    print(json.dumps(result, indent=2))
    
    print("\n5. Get High Priority Tickets:")
    result = mcp_server.call_tool('get_tickets_by_priority', priority='high')
    print(json.dumps(result, indent=2))