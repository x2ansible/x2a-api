#!/usr/bin/env python3
"""
Test script for Chef Analysis Agent FastAPI endpoints.
Supports both sync and streaming API.
"""

import json
import sys
import logging
import requests
import aiohttp
import asyncio
from pathlib import Path
from datetime import datetime

# ---- CONFIGURE THESE ----
DEFAULT_API_BASE = "http://localhost:8000"  # Or your backend route
DEFAULT_COOKBOOK_DIR = Path("input/chef_demo_cookbook")
DEFAULT_TIMEOUT = 180

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("chef-test")

def read_cookbook_files(cookbook_dir: Path):
    """Recursively read all files in cookbook_dir into a dict."""
    if not cookbook_dir.exists():
        raise FileNotFoundError(f"{cookbook_dir} not found")
    skip_dirs = {'.git', '__pycache__', 'node_modules', '.venv', 'venv'}
    files = {}
    for p in cookbook_dir.rglob("*"):
        if p.is_file() and not any(skip in p.parts for skip in skip_dirs):
            try:
                content = p.read_text(encoding="utf-8", errors="ignore")
                files[str(p.relative_to(cookbook_dir))] = content
            except Exception as e:
                logger.warning(f"Could not read {p}: {e}")
    logger.info(f"Read {len(files)} files from {cookbook_dir}")
    return files

def test_sync_api(api_base, cookbook_dir, timeout=DEFAULT_TIMEOUT):
    url = f"{api_base}/chef/analyze"
    files = read_cookbook_files(cookbook_dir)
    payload = {
        "cookbook_name": cookbook_dir.name,
        "files": files
    }
    logger.info(f"POST {url} ({len(files)} files)...")
    resp = requests.post(url, json=payload, timeout=timeout)
    logger.info(f"Status: {resp.status_code}")
    if resp.status_code == 200:
        result = resp.json()
        logger.info("Analysis complete! Key results:")
        _log_core_result_fields(result)
        _save_json_result("chef_analysis_sync", result)
    else:
        logger.error(f"Sync API error: {resp.status_code} {resp.text[:400]}")

async def test_stream_api(api_base, cookbook_dir, timeout=DEFAULT_TIMEOUT):
    url = f"{api_base}/chef/analyze/stream"
    files = read_cookbook_files(cookbook_dir)
    payload = {
        "cookbook_name": cookbook_dir.name,
        "files": files
    }
    logger.info(f"POST (streaming) {url} ({len(files)} files)...")
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
        async with session.post(
            url, json=payload,
            headers={"Accept": "text/event-stream"}
        ) as resp:
            logger.info(f"Status: {resp.status}")
            if resp.status != 200:
                err = await resp.text()
                logger.error(f"Streaming API error: {resp.status} {err[:400]}")
                return
            final_result = None
            async for line in resp.content:
                if not line:
                    continue
                line_text = line.decode("utf-8").strip()
                if line_text.startswith("data: "):
                    data = line_text[6:]
                    try:
                        event = json.loads(data)
                        # Progress and chunk events
                        if event.get("type") == "progress":
                            logger.info(f"Progress: {event.get('message')}")
                        elif event.get("type") == "partial_analysis":
                            logger.info("Partial analysis received.")
                        elif event.get("type") == "final_analysis":
                            final_result = event.get("data")
                            logger.info("Final analysis received.")
                        elif event.get("type") == "error":
                            logger.error(f"Error: {event.get('error')}")
                        elif event.get("type") == "complete":
                            logger.info("Streaming complete.")
                    except Exception as e:
                        logger.warning(f"Bad event chunk: {e}")
            if final_result:
                _log_core_result_fields(final_result)
                _save_json_result("chef_analysis_stream", final_result)
            else:
                logger.warning("No final analysis result received.")

def _log_core_result_fields(result: dict):
    """Log the most useful analysis fields if present."""
    v = result.get("version_requirements", {})
    d = result.get("dependencies", {})
    r = result.get("recommendations", {})
    logger.info(f"- Chef Version: {v.get('min_chef_version', 'n/a')}")
    logger.info(f"- Migration Effort: {v.get('migration_effort', 'n/a')}")
    logger.info(f"- Is Wrapper: {d.get('is_wrapper', 'n/a')}")
    logger.info(f"- Recommendation: {r.get('consolidation_action', 'n/a')}")
    logger.info(f"- All keys: {list(result.keys())}")

def _save_json_result(prefix, data):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"{prefix}_{ts}.json"
    with open(fname, "w") as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved result: {fname}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test Chef Analysis Agent endpoints.")
    parser.add_argument("--api-base", default=DEFAULT_API_BASE, help="Base API URL")
    parser.add_argument("--cookbook", default=str(DEFAULT_COOKBOOK_DIR), help="Cookbook folder")
    parser.add_argument("--sync", action="store_true", help="Test synchronous endpoint")
    parser.add_argument("--stream", action="store_true", help="Test streaming endpoint")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Request timeout")
    args = parser.parse_args()

    # Default: test both
    if not args.sync and not args.stream:
        args.sync = args.stream = True

    if args.sync:
        test_sync_api(args.api_base, Path(args.cookbook), args.timeout)

    if args.stream:
        asyncio.run(test_stream_api(args.api_base, Path(args.cookbook), args.timeout))
