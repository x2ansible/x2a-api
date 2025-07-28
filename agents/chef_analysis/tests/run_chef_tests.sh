#!/bin/bash

# Chef Agent Capability Test Runner
# =================================
# This script runs comprehensive tests to establish realistic expectations
# for the Chef analysis agent.

echo "Chef Agent Capability Test Suite"
echo "==================================="
echo ""
echo "PURPOSE:"
echo "- Demonstrate realistic capabilities"
echo "- Set proper expectations for users"
echo "- Provide defensible test results"
echo "- Show limitations and edge cases"
echo ""
echo "EXPECTATIONS:"
echo "- Simple cookbooks: 15-30 seconds, high accuracy"
echo "- Medium cookbooks: 30-60 seconds, good accuracy"
echo "- Complex cookbooks: 60-120 seconds, moderate accuracy"
echo "- Very complex: May timeout or have reduced accuracy"
echo ""

# Check if server is running
echo "Checking if server is running..."
if curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "Server is running"
else
    echo "Server is not running. Please start the server first:"
    echo "   uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
    exit 1
fi

echo ""
echo "Running capability tests..."
echo "=============================="

# Run the test suite with storage
python3 run_tests.py both --results-dir test_results

echo ""
echo "Test Results Summary:"
echo "========================"
echo ""
echo "Use the detailed report above to:"
echo "1. Set proper expectations with users"
echo "2. Defend against misunderstandings"
echo "3. Document realistic capabilities"
echo "4. Plan improvements based on results"
echo ""
echo "Key Points for Users:"
echo "WHAT WORKS: Simple to medium complexity cookbooks"
echo "LIMITATIONS: Complex cookbooks may have issues"
echo "AVOID: Very large enterprise cookbooks"
echo ""
echo "Test suite completed!" 