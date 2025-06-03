#!/usr/bin/env python3
"""
Debug script to test LlamaStack streaming response format
Run this to see exactly what the server returns
"""

import asyncio
import aiohttp
import json

BASE_URL = "http://lss-chai.apps.cluster-7nc6z.7nc6z.sandbox2170.opentlc.com"
AGENT_ID = "03bdffb9-0e29-4fca-8fbe-741c30465718"  # Your existing agent

async def debug_streaming():
    print("🔍 Debugging LlamaStack streaming response format")
    
    # Create session
    session_payload = {"session_name": "debug_session_123"}
    
    async with aiohttp.ClientSession() as session:
        # Create session
        print(f"📡 Creating session...")
        async with session.post(f"{BASE_URL}/v1/agents/{AGENT_ID}/session", json=session_payload) as response:
            if response.status != 200:
                error_text = await response.text()
                print(f" Session creation failed: {response.status} - {error_text}")
                return
            
            session_result = await response.json()
            session_id = session_result.get("session_id")
            print(f" Created session: {session_id}")
        
        # Send streaming turn
        turn_payload = {
            "messages": [
                {"role": "user", "content": "Please respond with a simple test message. Just say 'Hello, this is a test response' and nothing else."}
            ],
            "stream": True
        }
        
        print(f"📡 Sending streaming turn...")
        print(f"URL: {BASE_URL}/v1/agents/{AGENT_ID}/session/{session_id}/turn")
        print(f"Payload: {json.dumps(turn_payload, indent=2)}")
        
        async with session.post(f"{BASE_URL}/v1/agents/{AGENT_ID}/session/{session_id}/turn", json=turn_payload) as response:
            print(f"📊 Response status: {response.status}")
            print(f"📊 Response headers: {dict(response.headers)}")
            
            if response.status != 200:
                error_text = await response.text()
                print(f" Turn failed: {response.status} - {error_text}")
                return
            
            print(f" Turn started, processing chunks...")
            
            chunk_count = 0
            total_data = ""
            
            async for line in response.content:
                if not line:
                    continue
                
                chunk_count += 1
                
                try:
                    line_text = line.decode('utf-8').strip()
                    if not line_text:
                        print(f"Chunk {chunk_count}: Empty line")
                        continue
                    
                    print(f"\n=== Chunk {chunk_count} ===")
                    print(f"Raw bytes length: {len(line)}")
                    print(f"Decoded text length: {len(line_text)}")
                    print(f"Raw text: {repr(line_text)}")
                    
                    total_data += line_text + "\n"
                    
                    # Try to parse as JSON
                    if line_text.startswith('data: '):
                        json_text = line_text[6:]
                        print(f"JSON part: {json_text}")
                        
                        try:
                            chunk = json.loads(json_text)
                            print(f" Parsed JSON successfully")
                            print(f"Top-level keys: {list(chunk.keys())}")
                            
                            # Print full structure for first few chunks
                            if chunk_count <= 5:
                                print(f"Full JSON structure:")
                                print(json.dumps(chunk, indent=2))
                            else:
                                print("(Skipping full JSON for brevity)")
                                
                        except json.JSONDecodeError as e:
                            print(f" JSON parse error: {e}")
                            print(f"Failed text: {repr(json_text)}")
                    else:
                        print(f"Non-data line: {repr(line_text)}")
                
                except Exception as e:
                    print(f" Error processing chunk {chunk_count}: {e}")
                
                # Limit chunks for debugging
                if chunk_count >= 20:
                    print("\n... (stopping after 20 chunks for debugging)")
                    break
            
            print(f"\n=== SUMMARY ===")
            print(f"Total chunks processed: {chunk_count}")
            print(f"Total raw data length: {len(total_data)}")
            
            if chunk_count == 0:
                print(" No chunks received - this is the problem!")
                print("Let's check if the response is being buffered...")
                
                # Try to read all at once
                try:
                    remaining = await response.read()
                    if remaining:
                        print(f"Found {len(remaining)} bytes of buffered data:")
                        print(repr(remaining.decode('utf-8', errors='ignore')[:500]))
                    else:
                        print("No buffered data either")
                except Exception as e:
                    print(f"Error reading buffered data: {e}")
            
            print(" Debug completed")

if __name__ == "__main__":
    asyncio.run(debug_streaming())