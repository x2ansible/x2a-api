#!/usr/bin/env python3
"""
Test Results Analyzer
====================

This script analyzes stored test results and generates reports.
"""

import json
import os
import glob
from typing import Dict, Any, List
from datetime import datetime

def load_test_results(results_dir: str = "test_results") -> List[Dict[str, Any]]:
    """Load all test results from the results directory"""
    results = []
    
    if not os.path.exists(results_dir):
        print(f"Results directory '{results_dir}' not found")
        return results
    
    # Find all JSON files
    json_files = glob.glob(os.path.join(results_dir, "*.json"))
    
    for filepath in json_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
                data['_source_file'] = filepath
                results.append(data)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    
    return results

def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Analyze test results and generate insights"""
    if not results:
        return {"error": "No results to analyze"}
    
    # Separate individual test results from summary reports
    test_results = [r for r in results if 'test_name' in r and 'error' not in r]
    summary_reports = [r for r in results if 'total_tests' in r]
    detailed_reports = [r for r in results if 'capability_assessment' in r]
    
    analysis = {
        "total_files_processed": len(results),
        "test_results_count": len(test_results),
        "summary_reports_count": len(summary_reports),
        "detailed_reports_count": len(detailed_reports),
        "test_runs": []
    }
    
    # Analyze each test run
    for detailed_report in detailed_reports:
        test_run = {
            "test_run_id": detailed_report.get('summary', {}).get('test_run_id', 'unknown'),
            "timestamp": detailed_report.get('summary', {}).get('timestamp', 'unknown'),
            "total_tests": detailed_report.get('summary', {}).get('total_tests', 0),
            "successful_tests": detailed_report.get('summary', {}).get('successful_tests', 0),
            "failed_tests": detailed_report.get('summary', {}).get('failed_tests', 0),
            "success_rate": detailed_report.get('summary', {}).get('success_rate', 0),
            "total_time": detailed_report.get('summary', {}).get('total_time', 0),
            "capability_assessment": detailed_report.get('capability_assessment', {}),
            "performance_metrics": detailed_report.get('performance_metrics', {}),
            "recommendations": detailed_report.get('recommendations', {})
        }
        analysis["test_runs"].append(test_run)
    
    # Calculate overall statistics
    if analysis["test_runs"]:
        total_runs = len(analysis["test_runs"])
        avg_success_rate = sum(run['success_rate'] for run in analysis["test_runs"]) / total_runs
        avg_total_time = sum(run['total_time'] for run in analysis["test_runs"]) / total_runs
        
        analysis["overall_stats"] = {
            "total_test_runs": total_runs,
            "average_success_rate": round(avg_success_rate, 1),
            "average_total_time": round(avg_total_time, 1),
            "best_success_rate": max(run['success_rate'] for run in analysis["test_runs"]),
            "worst_success_rate": min(run['success_rate'] for run in analysis["test_runs"])
        }
    
    return analysis

def generate_report(analysis: Dict[str, Any]) -> str:
    """Generate a human-readable report"""
    if "error" in analysis:
        return f"Error: {analysis['error']}"
    
    report = []
    report.append("=" * 60)
    report.append("CHEF AGENT TEST RESULTS ANALYSIS")
    report.append("=" * 60)
    report.append("")
    
    # Overall statistics
    report.append("OVERALL STATISTICS:")
    report.append("-" * 30)
    report.append(f"Files processed: {analysis['total_files_processed']}")
    report.append(f"Test results: {analysis['test_results_count']}")
    report.append(f"Summary reports: {analysis['summary_reports_count']}")
    report.append(f"Detailed reports: {analysis['detailed_reports_count']}")
    report.append("")
    
    if "overall_stats" in analysis:
        stats = analysis["overall_stats"]
        report.append("PERFORMANCE SUMMARY:")
        report.append("-" * 30)
        report.append(f"Total test runs: {stats['total_test_runs']}")
        report.append(f"Average success rate: {stats['average_success_rate']}%")
        report.append(f"Average total time: {stats['average_total_time']:.1f}s")
        report.append(f"Best success rate: {stats['best_success_rate']}%")
        report.append(f"Worst success rate: {stats['worst_success_rate']}%")
        report.append("")
    
    # Individual test runs
    if analysis["test_runs"]:
        report.append("INDIVIDUAL TEST RUNS:")
        report.append("-" * 30)
        
        for i, run in enumerate(analysis["test_runs"], 1):
            report.append(f"Run {i}: {run['test_run_id']}")
            report.append(f"  Timestamp: {run['timestamp']}")
            report.append(f"  Tests: {run['successful_tests']}/{run['total_tests']} ({run['success_rate']}%)")
            report.append(f"  Total time: {run['total_time']:.1f}s")
            report.append(f"  Capability: {run['capability_assessment'].get('rating', 'Unknown')}")
            report.append(f"  Production ready: {run['capability_assessment'].get('production_ready', False)}")
            
            if 'performance_metrics' in run and 'error' not in run['performance_metrics']:
                metrics = run['performance_metrics']
                report.append(f"  Avg duration: {metrics.get('average_duration', 'N/A')}s")
                report.append(f"  Performance: {metrics.get('performance_rating', 'N/A')}")
            
            report.append("")
    
    # Recommendations summary
    if analysis["test_runs"]:
        report.append("RECOMMENDATIONS SUMMARY:")
        report.append("-" * 30)
        
        # Count different ratings
        ratings = {}
        production_ready_count = 0
        
        for run in analysis["test_runs"]:
            rating = run['capability_assessment'].get('rating', 'Unknown')
            ratings[rating] = ratings.get(rating, 0) + 1
            
            if run['capability_assessment'].get('production_ready', False):
                production_ready_count += 1
        
        report.append(f"Production ready runs: {production_ready_count}/{len(analysis['test_runs'])}")
        report.append("Capability ratings:")
        for rating, count in ratings.items():
            report.append(f"  {rating}: {count} runs")
        
        report.append("")
    
    report.append("=" * 60)
    return "\n".join(report)

def save_analysis_report(analysis: Dict[str, Any], output_file: str = "analysis_report.json"):
    """Save analysis report to file"""
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"Analysis report saved to: {output_file}")

def main():
    """Main analyzer"""
    print("Chef Agent Test Results Analyzer")
    print("=" * 40)
    
    # Load results
    print("Loading test results...")
    results = load_test_results()
    
    if not results:
        print("No test results found. Run the test suite first.")
        return
    
    print(f"Loaded {len(results)} result files")
    
    # Analyze results
    print("Analyzing results...")
    analysis = analyze_results(results)
    
    # Generate report
    print("Generating report...")
    report = generate_report(analysis)
    
    # Display report
    print("\n" + report)
    
    # Save analysis
    save_analysis_report(analysis)
    
    print("\nAnalysis complete!")

if __name__ == "__main__":
    main() 