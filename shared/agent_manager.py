#!/usr/bin/env python3
"""
LlamaStack Agent Manager
Helps manage agents in LlamaStack - list, delete, and clean up duplicates.
"""

import requests
import json
import sys
import argparse
from datetime import datetime

def list_all_agents(llamastack_url):
    """List all agents in LlamaStack"""
    try:
        response = requests.get(f"{llamastack_url}/v1/agents")
        if response.status_code != 200:
            print(f" Failed to list agents: {response.status_code}")
            return []
        
        data = response.json()
        agents = data.get('data', [])
        
        print(f"📋 Found {len(agents)} agents in LlamaStack:")
        print()
        
        # Group by name
        by_name = {}
        for agent in agents:
            agent_config = agent.get('agent_config', {})
            name = agent_config.get('name', 'unnamed')
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(agent)
        
        for name, agent_list in by_name.items():
            print(f"🤖 Agent Name: {name} ({len(agent_list)} instances)")
            for i, agent in enumerate(agent_list):
                agent_id = agent.get('agent_id', 'unknown')
                created_at = agent.get('created_at', 'unknown')
                model = agent.get('agent_config', {}).get('model', 'unknown')
                print(f"   {i+1}. ID: {agent_id}")
                print(f"      Model: {model}")
                print(f"      Created: {created_at}")
            print()
        
        return agents
        
    except Exception as e:
        print(f" Error listing agents: {e}")
        return []

def delete_agent(llamastack_url, agent_id):
    """Delete a specific agent"""
    try:
        response = requests.delete(f"{llamastack_url}/v1/agents/{agent_id}")
        if response.status_code in [200, 204]:
            print(f" Deleted agent: {agent_id}")
            return True
        else:
            print(f" Failed to delete agent {agent_id}: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    except Exception as e:
        print(f" Error deleting agent {agent_id}: {e}")
        return False

def delete_duplicate_agents(llamastack_url, keep_latest=True):
    """Delete duplicate agents, keeping only one per name"""
    agents = list_all_agents(llamastack_url)
    if not agents:
        return
    
    # Group by name
    by_name = {}
    for agent in agents:
        agent_config = agent.get('agent_config', {})
        name = agent_config.get('name', 'unnamed')
        if name not in by_name:
            by_name[name] = []
        by_name[name].append(agent)
    
    deleted_count = 0
    
    for name, agent_list in by_name.items():
        if len(agent_list) <= 1:
            print(f" {name}: Only 1 instance, no duplicates to remove")
            continue
        
        print(f"🔄 {name}: Found {len(agent_list)} instances, cleaning up...")
        
        # Sort by created_at to keep the latest (or earliest)
        try:
            sorted_agents = sorted(agent_list, key=lambda x: x.get('created_at', ''), reverse=keep_latest)
        except:
            # If sorting fails, just use the list as-is
            sorted_agents = agent_list
        
        # Keep the first one, delete the rest
        keep_agent = sorted_agents[0]
        delete_agents = sorted_agents[1:]
        
        print(f"   Keeping: {keep_agent.get('agent_id')} (created: {keep_agent.get('created_at')})")
        
        for agent in delete_agents:
            agent_id = agent.get('agent_id')
            created_at = agent.get('created_at', 'unknown')
            print(f"   Deleting: {agent_id} (created: {created_at})")
            
            if delete_agent(llamastack_url, agent_id):
                deleted_count += 1
    
    print(f"\n Cleanup complete! Deleted {deleted_count} duplicate agents")

def delete_all_agents(llamastack_url, confirm=False):
    """Delete ALL agents (use with caution!)"""
    if not confirm:
        print(" This will delete ALL agents! Use --confirm to proceed.")
        return
    
    agents = list_all_agents(llamastack_url)
    if not agents:
        print(" No agents to delete")
        return
    
    print(f"🗑️  Deleting ALL {len(agents)} agents...")
    deleted_count = 0
    
    for agent in agents:
        agent_id = agent.get('agent_id')
        name = agent.get('agent_config', {}).get('name', 'unnamed')
        print(f"   Deleting {name}: {agent_id}")
        
        if delete_agent(llamastack_url, agent_id):
            deleted_count += 1
    
    print(f"\n Deleted {deleted_count} agents")

def get_llamastack_url_from_config():
    """Try to get LlamaStack URL from your config"""
    try:
        # Try to import your config loader
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        
        from config.config_loader import ConfigLoader
        config_loader = ConfigLoader()
        base_url = config_loader.get_llamastack_base_url()
        if base_url:
            return base_url.rstrip('/')
    except:
        pass
    
    # Fallback URL
    return "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"

def main():
    parser = argparse.ArgumentParser(description="LlamaStack Agent Manager")
    parser.add_argument("--llamastack-url", type=str, help="LlamaStack URL (will auto-detect if not provided)")
    parser.add_argument("--list", action="store_true", help="List all agents")
    parser.add_argument("--delete-duplicates", action="store_true", help="Delete duplicate agents (keep latest)")
    parser.add_argument("--delete-duplicates-keep-oldest", action="store_true", help="Delete duplicates (keep oldest)")
    parser.add_argument("--delete-all", action="store_true", help="Delete ALL agents")
    parser.add_argument("--delete-agent", type=str, help="Delete specific agent by ID")
    parser.add_argument("--confirm", action="store_true", help="Confirm destructive operations")
    
    args = parser.parse_args()
    
    # Get LlamaStack URL
    if args.llamastack_url:
        llamastack_url = args.llamastack_url.rstrip('/')
    else:
        llamastack_url = get_llamastack_url_from_config()
        print(f"🔗 Using LlamaStack URL: {llamastack_url}")
        print("   (Use --llamastack-url to override)")
        print()
    
    if args.list:
        list_all_agents(llamastack_url)
    
    elif args.delete_duplicates:
        print("🧹 Deleting duplicate agents (keeping latest)...")
        delete_duplicate_agents(llamastack_url, keep_latest=True)
    
    elif args.delete_duplicates_keep_oldest:
        print("🧹 Deleting duplicate agents (keeping oldest)...")
        delete_duplicate_agents(llamastack_url, keep_latest=False)
    
    elif args.delete_all:
        print("🗑️  Deleting ALL agents...")
        delete_all_agents(llamastack_url, args.confirm)
    
    elif args.delete_agent:
        print(f"🗑️  Deleting agent: {args.delete_agent}")
        delete_agent(llamastack_url, args.delete_agent)
    
    else:
        print("No action specified. Use --list, --delete-duplicates, etc.")
        print("\nQuick commands:")
        print("  python agent_manager.py --list")
        print("  python agent_manager.py --delete-duplicates")
        print("  python agent_manager.py --delete-all --confirm")

if __name__ == "__main__":
    main()