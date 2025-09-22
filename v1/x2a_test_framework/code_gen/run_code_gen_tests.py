#!/usr/bin/env python3
"""
Code Generation Tests Runner

Easy-to-use runner for code generation integration tests.
Part of the centralized x2a_test_framework.

Usage:
    python run_code_gen_tests.py                    # Test all platforms
    python run_code_gen_tests.py --platform chef    # Test specific platform
    python run_code_gen_tests.py --quick           # Quick validation
    python run_code_gen_tests.py --verbose         # Detailed output
"""

import sys
import subprocess
import argparse
from pathlib import Path

def main():
    """Main test runner"""
    parser = argparse.ArgumentParser(description="Run code generation integration tests")
    parser.add_argument("--platform", "-p", choices=["chef", "terraform"], 
                       help="Test specific platform only")
    parser.add_argument("--verbose", "-v", action="store_true", 
                       help="Enable verbose logging")
    parser.add_argument("--quick", "-q", action="store_true",
                       help="Quick validation test only")
    
    args = parser.parse_args()
    
    # Get the test script path
    test_script = Path(__file__).parent / "test_integration_with_infra_analysis.py"
    
    # Build command
    cmd = [sys.executable, str(test_script)]
    
    if args.platform:
        cmd.extend(["--platform", args.platform])
    
    if args.verbose:
        cmd.append("--verbose")
    
    print("🧪 Running Code Generation Integration Tests")
    print("=" * 60)
    print(f"Command: {' '.join(cmd)}")
    print()
    
    # Run the test
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent)
        return result.returncode
    except KeyboardInterrupt:
        print("\n❌ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Test execution failed: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
