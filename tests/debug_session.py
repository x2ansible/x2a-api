#!/usr/bin/env python3
"""
Simple debug script to fetch a known session
"""

import asyncio
import httpx
import json

async def simple_fetch():
    # Use the session IDs from your previous test run
    base_url = "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"
    agent_id = "0b967710-3518-4caa-b699-1dbbc7b492ab"  # From your last run
    session_id = "ab4bbabd-2fd5-4bc9-b90d-a65ca8e85add"  # From your last run
    
    url = f"{base_url}/v1/agents/{agent_id}/session/{session_id}"
    
    print(f"Fetching: {url}")
    
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code == 200:
                data = resp.json()
                print("Success! Session data:")
                print(json.dumps(data, indent=2))
            else:
                print(f"Error: {resp.text}")
                
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(simple_fetch())