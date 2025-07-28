#!/usr/bin/env python3
"""
Test script for Chef Analysis Agent (robust to LLM streaming output).
Place in your tests/ folder and run with --sync or --stream.
Requires: pip install requests sseclient-py
"""

import os
import sys
import json
import logging
from pathlib import Path
import requests
import argparse

# ---------------- CONFIGURATION ----------------
API_BASE = "http://localhost:8000"
COOKBOOK_DIR = "input/chef_demo_cookbook"
MAX_FILES = 10  # Limit number of files sent to the agent
MAX_FILE_LENGTH = 4000  # Max chars per file (truncate after this)
CORE_DIRS = {"recipes", "attributes"}
CORE_FILES = {"metadata.rb"}
# -----------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def read_cookbook_files(cookbook_dir: Path, only_core: bool = True):
    """
    Reads cookbook files and returns a {filename: content} dictionary.
    If only_core is True, sends only main .rb files and metadata.rb.
    """
    files = {}
    count = 0
    for p in sorted(cookbook_dir.rglob("*")):
        rel_path = p.relative_to(cookbook_dir)
        if not p.is_file():
            continue

        # Filter: Only .rb, metadata.rb, recipes/, attributes/ unless --all given
        if only_core:
            if rel_path.name == "metadata.rb":
                pass
            elif len(rel_path.parts) > 1 and rel_path.parts[0] in CORE_DIRS and rel_path.suffix == ".rb":
                pass
            else:
                continue

        # Enforce max files
        if count >= MAX_FILES:
            break

        # Read and truncate content
        try:
            content = p.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Could not read {rel_path}: {e}")
            continue
        if len(content) > MAX_FILE_LENGTH:
            content = content[:MAX_FILE_LENGTH] + "\n... [TRUNCATED] ..."
        files[str(rel_path)] = content
        logger.info(f"Added file: {rel_path} ({len(content)} chars)")
        count += 1
    logger.info(f"Total files sent: {len(files)}")
    return files

def post_sync(api_base: str, cookbook_name: str, files: dict):
    url = f"{api_base}/chef/analyze"
    payload = {"cookbook_name": cookbook_name, "files": files}
    logger.info(f"POST {url} ({len(files)} files)...")
    resp = requests.post(url, json=payload, timeout=90)
    logger.info(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        logger.info("Sync API Result:")
        print(json.dumps(resp.json(), indent=2))
    else:
        logger.error(f"Sync API error: {resp.status_code} {resp.text}")

def post_stream(api_base: str, cookbook_name: str, files: dict):
    try:
        import sseclient  # pip install sseclient-py
    except ImportError:
        logger.error("sseclient-py not installed. Run: pip install sseclient-py")
        return
        
    url = f"{api_base}/chef/analyze/stream"
    payload = {"cookbook_name": cookbook_name, "files": files}
    logger.info(f"POST (streaming) {url} ({len(files)} files)...")
    resp = requests.post(url, json=payload, stream=True, headers={"Accept": "text/event-stream"}, timeout=90)
    logger.info(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        client = sseclient.SSEClient(resp)
        saw_final = False
        for event in client.events():
            if not event.data.strip():
                continue
            print(f"RAW EVENT: {event.data}")  # Always print raw for debug
            try:
                data = json.loads(event.data)
            except Exception:
                logger.warning("Could not parse event data as JSON.")
                continue
            # Handle known event types
            if "type" in data:
                if data["type"] == "progress":
                    logger.info(f"Progress: {data.get('message')}")
                elif data["type"] == "final_analysis":
                    logger.info("Final analysis:")
                    print(json.dumps(data.get("data", {}), indent=2))
                    saw_final = True
                elif data["type"] == "partial_analysis":
                    logger.info("Partial analysis (truncated):")
                    print(json.dumps(data.get("data", {}), indent=2)[:400])
                elif data["type"] == "error":
                    logger.error(f"Error: {data.get('error')}")
                elif data["type"] == "complete":
                    logger.info("Stream: Analysis complete.")
                else:
                    logger.info(f"Other event type: {data['type']}")
                    print(json.dumps(data, indent=2))
            else:
                logger.info("Unknown event structure:")
                print(json.dumps(data, indent=2))
        if not saw_final:
            logger.warning("Did not see a final_analysis event in the stream.")
    else:
        logger.error(f"Error: {resp.status_code} {resp.text}")

def main():
    parser = argparse.ArgumentParser(description="Test Chef Analysis Agent API")
    parser.add_argument("--api-base", type=str, default=API_BASE)
    parser.add_argument("--cookbook", type=str, default=COOKBOOK_DIR)
    parser.add_argument("--all", action="store_true", help="Send all files (may hit context limit!)")
    parser.add_argument("--sync", action="store_true", help="Run sync API test")
    parser.add_argument("--stream", action="store_true", help="Run streaming API test")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    
    args = parser.parse_args()

    # Read files
    cookbook_dir = Path(args.cookbook)
    if not cookbook_dir.exists():
        logger.error(f"Cookbook directory not found: {cookbook_dir}")
        return
        
    files = read_cookbook_files(cookbook_dir, only_core=not args.all)

    if args.sync:
        post_sync(args.api_base, cookbook_dir.name, files)
    if args.stream:
        post_stream(args.api_base, cookbook_dir.name, files)
    if args.debug:
        logger.info("Debug mode enabled - additional logging")
        
    if not args.sync and not args.stream:
        logger.info("Nothing to do. Use --sync and/or --stream.")

if __name__ == "__main__":
    main()