#!/usr/bin/env python3
"""
Orchestrator Agent Test Runner

Runs orchestrator agent tests using x2a_test_framework.
Migrated from infrastructure_analysis/agents/orchestrator/tests/ for centralized testing.
"""

import sys
import subprocess
from pathlib import Path


def run_orchestrator_tests(quick: bool = False):
    """
    Run orchestrator agent tests with x2a framework integration.
    
    Args:
        quick: Whether to run quick validation only
        
    Returns:
        bool: True if all tests pass, False otherwise
    """
    
    print("🧪 Running Orchestrator Agent Tests (x2a Framework)")
    print("=" * 60)
    print("Testing pure agentic behavior with centralized test framework")
    print()
    
    test_dir = Path(__file__).parent
    
    if quick:
        # Quick validation - use isolated test to avoid dependencies
        test_commands = [
            {
                "name": "Quick Validation",
                "command": [
                    sys.executable, "-m", "pytest", 
                    "test_structured_output_isolated.py::TestOrchestratorStructuredOutputIsolated::test_structured_output_schema_validation",
                    "-v"
                ],
                "description": "Quick structured output validation (isolated)"
            }
        ]
    else:
        # Full test suite
        test_commands = [
            {
                "name": "Agent Creation Tests",
                "command": [sys.executable, "-m", "pytest", "test_agent_creation.py", "-v"],
                "description": "Validates agent creation and tool binding"
            },
            {
                "name": "Structured Output Tests",
                "command": [sys.executable, "-m", "pytest", "test_structured_output.py", "-v"],
                "description": "Validates LangChain structured output compliance"
            },
            {
                "name": "Unit Behavior Tests", 
                "command": [sys.executable, "-m", "pytest", "test_orchestrator_unit.py", "-v"],
                "description": "Tests isolated orchestrator agent functionality"
            },
            {
                "name": "All Tests Summary",
                "command": [sys.executable, "-m", "pytest", "-v", "--tb=short"],
                "description": "Complete test suite execution"
            }
        ]
    
    all_passed = True
    
    for test_group in test_commands:
        print(f"🔍 {test_group['name']}")
        print(f"   {test_group['description']}")
        print()
        
        try:
            result = subprocess.run(
                test_group["command"],
                cwd=test_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per test group
            )
            
            if result.returncode == 0:
                print(f"✅ {test_group['name']} PASSED")
                print()
            else:
                print(f"❌ {test_group['name']} FAILED")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
                print()
                all_passed = False
                
        except subprocess.TimeoutExpired:
            print(f"⏰ {test_group['name']} TIMEOUT")
            print("   Tests took longer than 2 minutes")
            print()
            all_passed = False
            
        except Exception as e:
            print(f"💥 {test_group['name']} ERROR: {e}")
            print()
            all_passed = False
    
    # Final summary
    print("=" * 60)
    if all_passed:
        print("🎉 ALL ORCHESTRATOR TESTS PASSED!")
        print("✅ Pure agentic behavior validated")
        print("✅ Structured output compliance verified")
        print("✅ x2a framework integration successful")
        print("✅ Ready for production use")
    else:
        print("💥 SOME TESTS FAILED!")
        print("❌ Check test output above for details")
        print("🔧 Fix issues before proceeding to next agent")
    
    print("=" * 60)
    return all_passed


def main():
    """Main function"""
    
    # Check for quick flag
    quick = len(sys.argv) > 1 and sys.argv[1] == "--quick"
    
    if quick:
        print("⚡ Running Quick Validation")
        success = run_orchestrator_tests(quick=True)
    else:
        print("🔍 Running Complete Test Suite")
        success = run_orchestrator_tests(quick=False)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
