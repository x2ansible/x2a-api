#!/usr/bin/env python3
"""
Chef Analysis Test Runner
=========================

This script runs all Chef analysis tests and provides a simple interface.
"""

import sys
import os
import argparse
from pathlib import Path

# Add the project root to the path so we can import modules
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from .test_capabilities import ChefAgentTesterWithStorage
from .analyze_results import load_test_results, analyze_results, generate_report

def run_capability_tests(results_dir: str = "test_results"):
    """Run the capability tests"""
    print("Running Chef Agent Capability Tests...")
    print("=" * 50)
    
    tester = ChefAgentTesterWithStorage(results_dir)
    tester.run_all_tests()
    
    print(f"\nTests completed. Results saved to: {results_dir}")

def analyze_stored_results(results_dir: str = "test_results"):
    """Analyze stored test results"""
    print("Analyzing stored test results...")
    print("=" * 50)
    
    results = load_test_results(results_dir)
    
    if not results:
        print("No test results found. Run the tests first.")
        return
    
    analysis = analyze_results(results)
    report = generate_report(analysis)
    
    print(report)

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Chef Analysis Test Runner")
    parser.add_argument(
        "action",
        choices=["test", "analyze", "both"],
        help="Action to perform: test (run tests), analyze (analyze results), both (run tests then analyze)"
    )
    parser.add_argument(
        "--results-dir",
        default="test_results",
        help="Directory to store/load test results (default: test_results)"
    )
    
    args = parser.parse_args()
    
    if args.action == "test":
        run_capability_tests(args.results_dir)
    elif args.action == "analyze":
        analyze_stored_results(args.results_dir)
    elif args.action == "both":
        run_capability_tests(args.results_dir)
        print("\n" + "=" * 50)
        analyze_stored_results(args.results_dir)

if __name__ == "__main__":
    main() 