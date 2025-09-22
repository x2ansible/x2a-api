#!/usr/bin/env python3
"""
Master Infrastructure Analysis Test Runner

Centralized test runner for all infrastructure analysis agents using x2a_test_framework.
Provides comprehensive testing coverage for the complete infrastructure analysis system.

Usage:
    python run_all_infrastructure_tests.py                    # Run all tests
    python run_all_infrastructure_tests.py --quick           # Quick validation
    python run_all_infrastructure_tests.py --orchestrator    # Orchestrator only
    python run_all_infrastructure_tests.py --agent <name>    # Specific agent
"""

import sys
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add v1 directory to Python path for imports
v1_dir = Path(__file__).parent.parent.parent
sys.path.insert(0, str(v1_dir))

# Import x2a test framework components
from x2a_test_framework.core.test_utilities import AsyncTestRunner
from x2a_test_framework.fixtures.sample_codes import X2ATestCodes


class InfrastructureAnalysisTestRunner:
    """
    Master test runner for all infrastructure analysis agents.
    
    Coordinates testing across orchestrator, universal_extractor, structured_analyzer,
    spec_generator, storage_manager, and synthesizer agents.
    """
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.results = {}
        
        # Define all infrastructure analysis agents and their test configurations
        self.agents = {
            "orchestrator": {
                "name": "Orchestrator Agent",
                "description": "Task planning and worker coordination",
                "test_files": [
                    "test_orchestrator_unit.py",
                    "test_structured_output.py"
                ],
                "quick_test": "test_structured_output.py::TestOrchestratorStructuredOutput::test_structured_output_schema_validation"
            },
            "universal_extractor": {
                "name": "Universal Extractor Agent", 
                "description": "Platform detection and fact extraction",
                "test_files": [
                    "test_universal_extractor_unit.py",
                    "test_platform_detection.py"
                ],
                "quick_test": "test_platform_detection.py::TestPlatformDetection::test_chef_detection"
            },
            "structured_analyzer": {
                "name": "Structured Analyzer Agent",
                "description": "Infrastructure analysis and complexity assessment", 
                "test_files": [
                    "test_structured_analyzer_unit.py",
                    "test_analysis_patterns.py"
                ],
                "quick_test": "test_analysis_patterns.py::TestAnalysisPatterns::test_basic_analysis"
            },
            "spec_generator": {
                "name": "Specification Generator Agent",
                "description": "GitHub Spec Kit specification generation",
                "test_files": [
                    "test_spec_generator_unit.py",
                    "test_spec_kit_integration.py"
                ],
                "quick_test": "test_spec_kit_integration.py::TestSpecKitIntegration::test_basic_spec_generation"
            },
            "storage_manager": {
                "name": "Storage Manager Agent",
                "description": "Neo4j storage and retrieval operations",
                "test_files": [
                    "test_storage_manager_unit.py",
                    "test_neo4j_integration.py"
                ],
                "quick_test": "test_storage_manager_unit.py::TestStorageManager::test_basic_storage"
            },
            "synthesizer": {
                "name": "Synthesizer Agent",
                "description": "Result synthesis and final output generation",
                "test_files": [
                    "test_synthesizer_unit.py",
                    "test_result_synthesis.py"
                ],
                "quick_test": "test_synthesizer_unit.py::TestSynthesizer::test_basic_synthesis"
            }
        }
    
    def run_agent_tests(self, agent_name: str, quick: bool = False) -> Dict[str, Any]:
        """
        Run tests for a specific agent.
        
        Args:
            agent_name: Name of the agent to test
            quick: Whether to run quick validation only
            
        Returns:
            Dictionary with test results
        """
        if agent_name not in self.agents:
            return {
                "success": False,
                "error": f"Unknown agent: {agent_name}",
                "tests_run": 0
            }
        
        agent_config = self.agents[agent_name]
        agent_dir = self.test_dir / agent_name
        
        print(f"\n🧪 Testing {agent_config['name']}")
        print(f"📝 {agent_config['description']}")
        print("=" * 60)
        
        if not agent_dir.exists():
            print(f"⚠️  Test directory not found: {agent_dir}")
            return {
                "success": False,
                "error": f"Test directory not found for {agent_name}",
                "tests_run": 0
            }
        
        if quick:
            # Run quick validation test only
            test_command = [
                sys.executable, "-m", "pytest", 
                agent_config["quick_test"], "-v"
            ]
            print(f"⚡ Running quick validation: {agent_config['quick_test']}")
        else:
            # Run all tests for this agent
            test_command = [
                sys.executable, "-m", "pytest", 
                str(agent_dir), "-v", "--tb=short"
            ]
            print(f"🔍 Running all tests in: {agent_dir}")
        
        try:
            result = subprocess.run(
                test_command,
                cwd=agent_dir,
                capture_output=True,
                text=True,
                timeout=120  # 2 minute timeout per agent
            )
            
            success = result.returncode == 0
            
            if success:
                print(f"✅ {agent_config['name']} tests PASSED")
            else:
                print(f"❌ {agent_config['name']} tests FAILED")
                print("STDOUT:", result.stdout)
                print("STDERR:", result.stderr)
            
            return {
                "success": success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "tests_run": 1 if quick else len(agent_config["test_files"])
            }
            
        except subprocess.TimeoutExpired:
            print(f"⏰ {agent_config['name']} tests TIMED OUT")
            return {
                "success": False,
                "error": "Test timeout",
                "tests_run": 0
            }
        except Exception as e:
            print(f"💥 {agent_config['name']} tests ERROR: {e}")
            return {
                "success": False,
                "error": str(e),
                "tests_run": 0
            }
    
    def run_all_tests(self, quick: bool = False) -> Dict[str, Any]:
        """
        Run tests for all infrastructure analysis agents.
        
        Args:
            quick: Whether to run quick validation only
            
        Returns:
            Dictionary with overall test results
        """
        print("🚀 Infrastructure Analysis - Master Test Runner")
        print("=" * 70)
        print(f"Testing {len(self.agents)} infrastructure analysis agents")
        if quick:
            print("⚡ Running quick validation tests only")
        else:
            print("🔍 Running comprehensive test suite")
        print()
        
        overall_results = {
            "total_agents": len(self.agents),
            "agents_passed": 0,
            "agents_failed": 0,
            "total_tests": 0,
            "agent_results": {},
            "start_time": Path(__file__).stat().st_mtime
        }
        
        # Test each agent
        for agent_name in self.agents.keys():
            agent_result = self.run_agent_tests(agent_name, quick)
            overall_results["agent_results"][agent_name] = agent_result
            overall_results["total_tests"] += agent_result.get("tests_run", 0)
            
            if agent_result["success"]:
                overall_results["agents_passed"] += 1
            else:
                overall_results["agents_failed"] += 1
        
        # Generate summary
        print("\n" + "=" * 70)
        print("📊 INFRASTRUCTURE ANALYSIS TEST SUMMARY")
        print("=" * 70)
        
        for agent_name, result in overall_results["agent_results"].items():
            agent_config = self.agents[agent_name]
            status = "✅ PASS" if result["success"] else "❌ FAIL"
            print(f"{status} {agent_config['name']}")
        
        success_rate = overall_results["agents_passed"] / overall_results["total_agents"]
        print(f"\n📈 Success Rate: {overall_results['agents_passed']}/{overall_results['total_agents']} agents ({success_rate:.1%})")
        print(f"🧪 Total Tests: {overall_results['total_tests']}")
        
        if overall_results["agents_failed"] == 0:
            print("\n🎉 ALL INFRASTRUCTURE ANALYSIS AGENTS PASSING!")
            print("✅ System ready for production deployment")
        else:
            print(f"\n⚠️  {overall_results['agents_failed']} agents need attention")
            print("🔧 Fix failing agents before deployment")
        
        return overall_results
    
    def validate_test_framework_integration(self) -> bool:
        """Validate that x2a_test_framework integration is working"""
        
        print("🔍 Validating x2a Test Framework Integration")
        print("-" * 50)
        
        try:
            # Test framework imports
            from x2a_test_framework.core.base_test_suites import BaseAgentTestSuite
            from x2a_test_framework.fixtures.sample_codes import X2ATestCodes
            from x2a_test_framework.agents.orchestrator import OrchestratorTestPatterns
            
            print("✅ x2a framework imports successful")
            
            # Test sample codes
            chef_code = X2ATestCodes.get_platform_code("chef", "simple")
            terraform_code = X2ATestCodes.get_platform_code("terraform", "medium")
            
            assert len(chef_code) > 100, "Chef test code should be substantial"
            assert len(terraform_code) > 100, "Terraform test code should be substantial"
            
            print("✅ Test code samples available")
            print(f"📊 Chef code: {len(chef_code)} characters")
            print(f"📊 Terraform code: {len(terraform_code)} characters")
            
            # Test patterns
            print("✅ Test patterns available")
            
            return True
            
        except Exception as e:
            print(f"❌ Framework integration failed: {e}")
            return False


def main():
    """Main test runner function"""
    
    parser = argparse.ArgumentParser(description="Infrastructure Analysis Test Runner")
    parser.add_argument("--quick", action="store_true", help="Run quick validation tests only")
    parser.add_argument("--agent", type=str, help="Test specific agent only")
    parser.add_argument("--orchestrator", action="store_true", help="Test orchestrator agent only")
    parser.add_argument("--validate", action="store_true", help="Validate framework integration only")
    
    args = parser.parse_args()
    
    runner = InfrastructureAnalysisTestRunner()
    
    # Validate framework integration first
    if args.validate or not any([args.agent, args.orchestrator]):
        if not runner.validate_test_framework_integration():
            print("\n❌ Framework integration validation failed")
            return 1
        
        if args.validate:
            print("\n✅ Framework integration validation completed")
            return 0
        print()  # Add spacing before main tests
    
    # Run specific agent tests
    if args.orchestrator or args.agent == "orchestrator":
        result = runner.run_agent_tests("orchestrator", args.quick)
        return 0 if result["success"] else 1
    
    if args.agent:
        result = runner.run_agent_tests(args.agent, args.quick)
        return 0 if result["success"] else 1
    
    # Run all tests
    overall_results = runner.run_all_tests(args.quick)
    return 0 if overall_results["agents_failed"] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
