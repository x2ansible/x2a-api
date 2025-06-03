#!/usr/bin/env python3
"""
Simple test to debug the processor
"""
import sys
import os

# Add the parent directory to the path so we can import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.chef_analysis.processor import extract_and_validate_analysis

# Test data
test_response = """
{
  "version_requirements": {
    "min_chef_version": "15.0",
    "min_ruby_version": "2.7",
    "migration_effort": "LOW",
    "estimated_hours": 4.0,
    "deprecated_features": []
  },
  "dependencies": {
    "is_wrapper": false,
    "wrapped_cookbooks": [],
    "direct_deps": ["nginx"],
    "runtime_deps": [],
    "circular_risk": "none"
  },
  "functionality": {
    "primary_purpose": "Web server configuration",
    "services": ["nginx"],
    "packages": ["nginx"],
    "files_managed": ["/etc/nginx/nginx.conf"],
    "reusability": "HIGH",
    "customization_points": ["port", "document_root"]
  },
  "recommendations": {
    "consolidation_action": "REUSE",
    "rationale": "Standard nginx cookbook with good reusability",
    "migration_priority": "LOW",
    "risk_factors": []
  }
}
"""

cookbook_content = """
Cookbook: test
=== metadata.rb ===
name 'nginx'
depends 'nginx'
=== recipes/default.rb ===
package 'nginx' do
  action :install
end

service 'nginx' do
  action :start
end
"""

print("Testing processor with cookbook content...")
result = extract_and_validate_analysis(test_response, "test123", cookbook_content)

print("Result:")
print(f"detailed_analysis: {result.get('detailed_analysis')}")
print(f"key_operations: {result.get('key_operations')}")
print(f"configuration_details: {result.get('configuration_details')}")
print(f"complexity_level: {result.get('complexity_level')}")
print(f"convertible: {result.get('convertible')}")
print(f"conversion_notes: {result.get('conversion_notes')}")
print(f"confidence_source: {result.get('confidence_source')}")