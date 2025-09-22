#!/usr/bin/env python3
"""
Container Readiness Test for Validation Agent

Uses the x2a_test_framework to verify validation agent is ready for container deployment.
Leverages existing ValidationTestHelpers and comprehensive end-to-end tests.
"""

import sys
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

async def main():
    """Run container readiness validation using x2a_test_framework."""
    
    print("🐳 VALIDATION AGENT - CONTAINER READINESS CHECK")
    print("=" * 60)
    print("Using x2a_test_framework for comprehensive validation\n")
    
    try:
        # Import framework components
        from x2a_test_framework.agents.validation import ValidationTestHelpers
        from testing.functional.test_validation_agent_end_to_end import ValidationAgentE2ETest
        
        # Step 1: Check prerequisites using framework
        print("🔍 CONTAINER PREREQUISITES CHECK")
        print("=" * 50)
        
        prereq_passed, prereq_checks = ValidationTestHelpers.check_container_prerequisites()
        
        for check_name, passed in prereq_checks.items():
            status = "✅" if passed else "❌"
            print(f"{status} {check_name.replace('_', ' ').title()}: {'Available' if passed else 'Failed'}")
        
        print(f"\n📊 Prerequisites: {sum(prereq_checks.values())}/{len(prereq_checks)} passed")
        
        if not prereq_passed:
            print("\n❌ CONTAINER NOT READY")
            print("Prerequisites check failed. Fix the issues above before containerizing.")
            return 1
        
        # Step 2: Run comprehensive validation test
        print("\n🚀 RUNNING COMPREHENSIVE VALIDATION TEST")
        print("=" * 50)
        
        tester = ValidationAgentE2ETest()
        test_results = await tester.run_comprehensive_test()
        
        # Step 3: Assert container readiness using framework
        print(f"\n🎯 CONTAINER READINESS ASSESSMENT")
        print("=" * 50)
        
        try:
            ValidationTestHelpers.assert_container_readiness(test_results)
            
            # If we get here, all assertions passed
            print("🎉 CONTAINER READY FOR DEPLOYMENT")
            print("=" * 50)
            print("✅ All prerequisites satisfied")
            print("✅ Validation agent working correctly")
            print("✅ Test suite passing")
            print("✅ Framework validation complete")
            print("\n🐳 Safe to build and deploy container!")
            
            return 0
            
        except AssertionError as e:
            print(f"❌ CONTAINER NOT READY")
            print(f"Readiness assertion failed: {e}")
            return 1
            
    except Exception as e:
        print(f"❌ Framework error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
