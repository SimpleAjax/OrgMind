#!/usr/bin/env python3
"""
Setup script for PM Assistant Agent.

This script registers the PM Assistant agent with OrgMind for a given user.

Usage:
    python setup_pm_assistant.py --user-id <user_id>
    python setup_pm_assistant.py --user-id <user_id> --list-tools
    python setup_pm_assistant.py --user-id <user_id> --delete-existing
"""

import argparse
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from orgmind.storage.postgres_adapter import PostgresAdapter
from extensions.project_management.agent import (
    register_pm_assistant_with_orgmind,
    get_pm_assistant_tools,
    PM_ASSISTANT_CAPABILITIES
)


def main():
    parser = argparse.ArgumentParser(description='Setup PM Assistant Agent')
    parser.add_argument('--user-id', required=True, help='User ID to create agent for')
    parser.add_argument('--list-tools', action='store_true', help='List available tools')
    parser.add_argument('--delete-existing', action='store_true', help='Delete existing agent if present')
    parser.add_argument('--capabilities', action='store_true', help='Show agent capabilities')
    
    args = parser.parse_args()
    
    if args.list_tools:
        print("Available PM Assistant Tools:")
        print("-" * 40)
        tools = get_pm_assistant_tools()
        for tool in tools:
            func = tool.get('function', {})
            print(f"\n{func.get('name')}:")
            print(f"  Description: {func.get('description', 'N/A')}")
        return
    
    if args.capabilities:
        print(PM_ASSISTANT_CAPABILITIES)
        return
    
    # Initialize database connection
    print(f"Setting up PM Assistant for user: {args.user_id}")
    
    try:
        adapter = PostgresAdapter()
        
        with adapter.get_session() as session:
            # Check for existing agent
            from extensions.project_management.agent import get_pm_assistant_agent
            
            existing = get_pm_assistant_agent(session, args.user_id)
            if existing:
                if args.delete_existing:
                    print(f"Deleting existing agent: {existing.id}")
                    from orgmind.agents.service import AgentService
                    service = AgentService(session)
                    service.delete_agent(existing.id)
                    session.commit()
                else:
                    print(f"PM Assistant already exists: {existing.id}")
                    print("Use --delete-existing to recreate")
                    return
            
            # Register agent
            result = register_pm_assistant_with_orgmind(session, args.user_id)
            
            if result['success']:
                print(f"\n✅ PM Assistant registered successfully!")
                print(f"   Agent ID: {result['agent_id']}")
                print(f"   Tools enabled: {result['tools_enabled']}")
            else:
                print(f"\n❌ Failed to register PM Assistant")
                print(f"   Error: {result.get('error', 'Unknown error')}")
                sys.exit(1)
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
