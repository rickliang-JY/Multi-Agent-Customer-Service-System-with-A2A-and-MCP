"""
Server Runner for A2A Multi-Agent Customer Service System

Usage:
  python run_servers.py           # Start all servers
  python run_servers.py --mcp     # Start only MCP server
  python run_servers.py --agents  # Start only A2A agents
"""

import subprocess
import sys
import time
import signal
import os

SERVERS = {
    "mcp": {
        "name": "MCP Server",
        "script": "mcp_server.py",
        "port": 8000,
        "args": []
    },
    "customer_data": {
        "name": "Customer Data Agent",
        "script": "customer_data_agent.py",
        "port": 8001,
        "args": ["--port", "8001"]
    },
    "support": {
        "name": "Support Agent",
        "script": "support_agent.py",
        "port": 8002,
        "args": ["--port", "8002"]
    }
}

processes = []


def cleanup(signum=None, frame=None):
    print("\n\nShutting down servers...")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except:
                proc.kill()
    print("[OK] All servers stopped")
    sys.exit(0)


def start_server(name, config):
    script_path = config["script"]
    
    if not os.path.exists(script_path):
        print(f"[ERROR] Script not found: {script_path}")
        return None
    
    print(f"[START] {config['name']} on port {config['port']}...")
    
    cmd = [sys.executable, script_path] + config.get("args", [])
    
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(proc)
        
        time.sleep(3)
        
        if proc.poll() is None:
            print(f"   [OK] {config['name']} started (PID: {proc.pid})")
            return proc
        else:
            print(f"   [FAILED] {config['name']} failed to start")
            try:
                output = proc.stdout.read()
                if output:
                    print(f"   Error:\n{output[:1000]}")
            except:
                pass
            return None
            
    except Exception as e:
        print(f"   [ERROR] {e}")
        return None


def main():
    print("\n" + "=" * 60)
    print("A2A Multi-Agent Customer Service System")
    print("=" * 60)
    
    start_mcp = "--mcp" in sys.argv or len(sys.argv) == 1
    start_agents = "--agents" in sys.argv or len(sys.argv) == 1
    
    signal.signal(signal.SIGINT, cleanup)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, cleanup)
    
    if not os.path.exists("support.db"):
        print("[WARNING] Database not found!")
        print("   Run: python database_setup.py")
        return
    
    print("\nStarting Servers...")
    print("-" * 40)
    
    servers_to_start = {}
    if start_mcp:
        servers_to_start["mcp"] = SERVERS["mcp"]
    if start_agents:
        servers_to_start["customer_data"] = SERVERS["customer_data"]
        servers_to_start["support"] = SERVERS["support"]
    
    started = 0
    for name, config in servers_to_start.items():
        proc = start_server(name, config)
        if proc:
            started += 1
        time.sleep(1)
    
    if started == 0:
        print("\n[ERROR] No servers started!")
        return
    
    print("\n" + "-" * 40)
    print(f"[OK] {started}/{len(servers_to_start)} servers running")
    print("\nServer URLs:")
    for name, config in servers_to_start.items():
        print(f"   - {config['name']}: http://localhost:{config['port']}")
    
    print("\nTo test: python test_scenarios.py")
    print("To demo: python orchestrator.py")
    print("\nPress Ctrl+C to stop")
    print("-" * 40)
    
    try:
        while True:
            time.sleep(5)
            for proc in processes:
                if proc.poll() is not None:
                    print("[WARNING] A server exited")
    except KeyboardInterrupt:
        cleanup()


if __name__ == "__main__":
    main()
