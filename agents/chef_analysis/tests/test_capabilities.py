#!/usr/bin/env python3
"""
Chef Agent Capability Test Suite with Result Storage
==================================================

This version stores test results to files for later analysis and reporting.
"""

import requests
import json
import time
import sys
import os
from typing import Dict, Any, List
from datetime import datetime

# Configuration
API_BASE = "http://localhost:8000"
TIMEOUT = 180  # 3 minutes max per test
MAX_RETRIES = 2

class ChefAgentTesterWithStorage:
    def __init__(self, results_dir: str = "test_results"):
        self.results = []
        self.start_time = time.time()
        self.results_dir = results_dir
        self.test_run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Create results directory
        os.makedirs(self.results_dir, exist_ok=True)
        
    def log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")
        
    def save_result(self, result: Dict[str, Any], test_name: str):
        """Save individual test result to file"""
        filename = f"{self.test_run_id}_{test_name.replace(' ', '_').lower()}.json"
        filepath = os.path.join(self.results_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
        
        self.log(f"Saved result to: {filepath}")
        
    def save_summary_report(self, summary: Dict[str, Any]):
        """Save summary report to file"""
        filename = f"{self.test_run_id}_summary_report.json"
        filepath = os.path.join(self.results_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        
        self.log(f"Saved summary report to: {filepath}")
        
    def save_detailed_report(self, report_data: Dict[str, Any]):
        """Save detailed report to file"""
        filename = f"{self.test_run_id}_detailed_report.json"
        filepath = os.path.join(self.results_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        self.log(f"Saved detailed report to: {filepath}")
        
    def parse_streaming_response(self, response) -> Dict[str, Any]:
        """Improved streaming response parser"""
        try:
            # Handle streaming response properly
            final_data = None
            for line in response.iter_lines(decode_unicode=True):
                if line.startswith('data: '):
                    try:
                        data = json.loads(line[6:])
                        if data.get('type') == 'final_analysis':
                            final_data = data.get('data', {})
                            break
                        elif data.get('type') == 'error':
                            return {"error": data.get('message', 'Unknown error')}
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        return {"error": f"JSON parsing error: {e}"}
            
            return final_data if final_data else {"error": "No final_analysis found"}
            
        except Exception as e:
            return {"error": f"Streaming parse error: {e}"}
    
    def test_simple_cookbook(self) -> Dict[str, Any]:
        """Test 1: Simple cookbook - should work perfectly"""
        self.log("TEST 1: Simple Apache Cookbook")
        
        payload = {
            "cookbook_name": "simple_apache",
            "files": {
                "metadata.rb": "name \"apache\"\nversion \"1.0.0\"\nchef_version \">= 15.0\"",
                "recipes/default.rb": "package \"httpd\" do\n  action :install\nend\n\nservice \"httpd\" do\n  action [:enable, :start]\nend"
            }
        }
        
        return self._run_test_with_retry(payload, "Simple Apache Cookbook", "Should work perfectly", "Simple", 2, "Basic package and service management")
    
    def test_medium_cookbook(self) -> Dict[str, Any]:
        """Test 2: Medium complexity - should work well"""
        self.log("TEST 2: Medium Nginx Cookbook")
        
        payload = {
            "cookbook_name": "nginx_medium",
            "files": {
                "metadata.rb": "name \"nginx\"\nversion \"1.0.0\"\ndepends \"ssl\"\nchef_version \">= 15.0\"",
                "recipes/default.rb": "package \"nginx\" do\n  action :install\nend\n\nservice \"nginx\" do\n  action [:enable, :start]\nend\n\nfile \"/etc/nginx/nginx.conf\" do\n  content \"server { listen 80; location / { root /var/www/html; } }\"\n  mode \"0644\"\n  notifies :reload, \"service[nginx]\", :immediately\nend",
                "templates/default/nginx.conf.erb": "<% @servers.each do |server| %>\nserver {\n  listen <%= server[:port] %>;\n  server_name <%= server[:name] %>;\n}\n<% end %>",
                "attributes/default.rb": "default[\"nginx\"][\"port\"] = 80\ndefault[\"nginx\"][\"server_name\"] = \"localhost\""
            }
        }
        
        return self._run_test_with_retry(payload, "Medium Nginx Cookbook", "Should work well", "Medium", 4, "Templates, attributes, service notifications")
    
    def test_complex_cookbook(self) -> Dict[str, Any]:
        """Test 3: Complex cookbook - may have limitations"""
        self.log("TEST 3: Complex Fullstack Cookbook")
        
        payload = {
            "cookbook_name": "fullstack_app",
            "files": {
                "metadata.rb": "name \"fullstack_app\"\nversion \"3.0.0\"\ndepends \"apache\"\ndepends \"mysql\"\ndepends \"redis\"\nchef_version \">= 15.0\"",
                "recipes/default.rb": "include_recipe \"apache\"\ninclude_recipe \"mysql\"\ninclude_recipe \"redis\"\n\npackage \"nodejs\" do\n  action :install\nend\n\npackage \"npm\" do\n  action :install\nend\n\nservice \"httpd\" do\n  action [:enable, :start]\nend\n\nservice \"mysqld\" do\n  action [:enable, :start]\nend\n\nservice \"redis\" do\n  action [:enable, :start]\nend\n\nfile \"/var/www/html/index.html\" do\n  content \"<html><body><h1>Full Stack App</h1></body></html>\"\n  mode \"0644\"\nend\n\nfile \"/etc/myapp/config.json\" do\n  content \"{\\\"database\\\": \\\"mysql\\\", \\\"cache\\\": \\\"redis\\\"}\"\n  mode \"0644\"\nend",
                "recipes/database.rb": "mysql_database \"myapp\" do\n  connection mysql_connection_info\n  action :create\nend\n\nmysql_database_user \"myapp_user\" do\n  connection mysql_connection_info\n  password \"secret\"\n  database_name \"myapp\"\n  privileges [:all]\n  action [:create, :grant]\nend",
                "recipes/deploy.rb": "git \"/var/www/html\" do\n  repository \"https://github.com/myorg/fullstack-app.git\"\n  revision \"main\"\n  action :sync\nend\n\nbash \"install_dependencies\" do\n  cwd \"/var/www/html\"\n  code \"npm install\"\n  action :run\nend",
                "attributes/default.rb": "default[\"fullstack_app\"][\"db_host\"] = \"localhost\"\ndefault[\"fullstack_app\"][\"db_name\"] = \"myapp\"\ndefault[\"fullstack_app\"][\"redis_host\"] = \"localhost\"\ndefault[\"fullstack_app\"][\"app_port\"] = 3000"
            }
        }
        
        return self._run_test_with_retry(payload, "Complex Fullstack Cookbook", "May have limitations", "Complex", 5, "Multiple dependencies, database ops, git, bash")
    
    def test_edge_case_cookbook(self) -> Dict[str, Any]:
        """Test 4: Edge case - may fail or have reduced accuracy"""
        self.log("TEST 4: Edge Case - Very Complex Cookbook")
        
        payload = {
            "cookbook_name": "enterprise_app",
            "files": {
                "metadata.rb": "name \"enterprise_app\"\nversion \"5.0.0\"\ndepends \"apache\"\ndepends \"mysql\"\ndepends \"redis\"\ndepends \"elasticsearch\"\ndepends \"kafka\"\ndepends \"zookeeper\"\nchef_version \">= 15.0\"",
                "recipes/default.rb": "include_recipe \"apache\"\ninclude_recipe \"mysql\"\ninclude_recipe \"redis\"\ninclude_recipe \"elasticsearch\"\ninclude_recipe \"kafka\"\ninclude_recipe \"zookeeper\"\n\npackage \"java-11-openjdk\" do\n  action :install\nend\n\npackage \"maven\" do\n  action :install\nend\n\npackage \"docker\" do\n  action :install\nend\n\nservice \"httpd\" do\n  action [:enable, :start]\nend\n\nservice \"mysqld\" do\n  action [:enable, :start]\nend\n\nservice \"redis\" do\n  action [:enable, :start]\nend\n\nservice \"elasticsearch\" do\n  action [:enable, :start]\nend\n\nservice \"kafka\" do\n  action [:enable, :start]\nend\n\nservice \"zookeeper\" do\n  action [:enable, :start]\nend\n\nfile \"/etc/enterprise/config.yml\" do\n  content \"database:\\n  host: localhost\\n  port: 3306\\n  name: enterprise\\n  user: admin\\n  password: secret123\\n\\nelasticsearch:\\n  host: localhost\\n  port: 9200\\n  cluster_name: enterprise-cluster\\n\\nkafka:\\n  brokers:\\n    - localhost:9092\\n    - localhost:9093\\n  topic_prefix: enterprise\\n\\nredis:\\n  host: localhost\\n  port: 6379\\n  password: redis123\\n\\nmonitoring:\\n  prometheus_port: 9090\\n  grafana_port: 3000\\n  alertmanager_port: 9093\"\n  mode \"0644\"\nend",
                "recipes/database.rb": "mysql_database \"enterprise\" do\n  connection mysql_connection_info\n  action :create\nend\n\nmysql_database_user \"enterprise_user\" do\n  connection mysql_connection_info\n  password \"enterprise_secret_2024\"\n  database_name \"enterprise\"\n  privileges [:all]\n  action [:create, :grant]\nend\n\nmysql_database_user \"readonly_user\" do\n  connection mysql_connection_info\n  password \"readonly_2024\"\n  database_name \"enterprise\"\n  privileges [:select]\n  action [:create, :grant]\nend",
                "recipes/monitoring.rb": "package \"prometheus\" do\n  action :install\nend\n\npackage \"grafana\" do\n  action :install\nend\n\npackage \"alertmanager\" do\n  action :install\nend\n\nservice \"prometheus\" do\n  action [:enable, :start]\nend\n\nservice \"grafana\" do\n  action [:enable, :start]\nend\n\nservice \"alertmanager\" do\n  action [:enable, :start]\nend\n\nfile \"/etc/prometheus/prometheus.yml\" do\n  content \"global:\\n  scrape_interval: 15s\\n\\nrule_files:\\n  - \\\"first_rules.yml\\\"\\n\\nscrape_configs:\\n  - job_name: 'enterprise-app'\\n    static_configs:\\n      - targets: ['localhost:8080']\"\n  mode \"0644\"\nend",
                "recipes/deploy.rb": "git \"/opt/enterprise\" do\n  repository \"https://github.com/enterprise/enterprise-app.git\"\n  revision \"main\"\n  action :sync\nend\n\nbash \"build_application\" do\n  cwd \"/opt/enterprise\"\n  code \"mvn clean package -DskipTests\"\n  action :run\nend\n\nbash \"deploy_application\" do\n  cwd \"/opt/enterprise\"\n  code \"java -jar target/enterprise-app.jar --spring.profiles.active=production\"\n  action :run\nend\n\nbash \"setup_monitoring\" do\n  cwd \"/opt/enterprise\"\n  code \"docker-compose up -d\"\n  action :run\nend",
                "attributes/default.rb": "default[\"enterprise_app\"][\"db_host\"] = \"localhost\"\ndefault[\"enterprise_app\"][\"db_name\"] = \"enterprise\"\ndefault[\"enterprise_app\"][\"db_user\"] = \"enterprise_user\"\ndefault[\"enterprise_app\"][\"db_password\"] = \"enterprise_secret_2024\"\ndefault[\"enterprise_app\"][\"redis_host\"] = \"localhost\"\ndefault[\"enterprise_app\"][\"redis_port\"] = 6379\ndefault[\"enterprise_app\"][\"elasticsearch_host\"] = \"localhost\"\ndefault[\"enterprise_app\"][\"elasticsearch_port\"] = 9200\ndefault[\"enterprise_app\"][\"kafka_brokers\"] = [\"localhost:9092\", \"localhost:9093\"]\ndefault[\"enterprise_app\"][\"app_port\"] = 8080\ndefault[\"enterprise_app\"][\"monitoring_enabled\"] = true\ndefault[\"enterprise_app\"][\"log_level\"] = \"INFO\"\ndefault[\"enterprise_app\"][\"environment\"] = \"production\""
            }
        }
        
        return self._run_test_with_retry(payload, "Enterprise Complex Cookbook", "May fail or have reduced accuracy", "Very Complex", 5, "Enterprise-scale with many services and dependencies")
    
    def _run_test_with_retry(self, payload: Dict, test_name: str, expected: str, complexity: str, files: int, notes: str) -> Dict[str, Any]:
        """Run a test with retry logic and better error handling"""
        for attempt in range(MAX_RETRIES + 1):
            try:
                start_time = time.time()
                
                self.log(f"   Attempt {attempt + 1}/{MAX_RETRIES + 1}")
                
                response = requests.post(
                    f"{API_BASE}/api/chef/analyze/stream",
                    json=payload,
                    timeout=TIMEOUT,
                    headers={"Accept": "text/event-stream"},
                    stream=True  # Important: Enable streaming
                )
                
                if response.status_code == 200:
                    # Parse streaming response properly
                    final_data = self.parse_streaming_response(response)
                    
                    if "error" in final_data:
                        if attempt < MAX_RETRIES:
                            self.log(f"   Retrying due to error: {final_data['error']}")
                            time.sleep(2)
                            continue
                        else:
                            result = {"test_name": test_name, "error": final_data["error"]}
                            self.save_result(result, test_name)
                            return result
                    
                    duration = time.time() - start_time
                    success = final_data.get('success', False)
                    analysis_time = final_data.get('session_info', {}).get('analysis_time_seconds', 0)
                    
                    result = {
                        "test_name": test_name,
                        "expected": expected,
                        "duration": duration,
                        "analysis_time": analysis_time,
                        "success": success,
                        "complexity": complexity,
                        "files": files,
                        "content_size": len(str(payload)),
                        "accuracy": "High" if success and complexity == "Simple" else "Good" if success and complexity == "Medium" else "Moderate" if success and complexity == "Complex" else "Reduced" if success else "Failed",
                        "notes": notes,
                        "payload": payload,  # Store the test payload
                        "response": final_data,  # Store the full response
                        "timestamp": datetime.now().isoformat(),
                        "test_run_id": self.test_run_id
                    }
                    
                    self.save_result(result, test_name)
                    return result
                else:
                    if attempt < MAX_RETRIES:
                        self.log(f"   Retrying due to HTTP {response.status_code}")
                        time.sleep(2)
                        continue
                    else:
                        result = {"test_name": test_name, "error": f"HTTP {response.status_code}"}
                        self.save_result(result, test_name)
                        return result
                        
            except requests.exceptions.Timeout:
                if attempt < MAX_RETRIES:
                    self.log(f"   Retrying due to timeout")
                    time.sleep(2)
                    continue
                else:
                    result = {"test_name": test_name, "error": "Request timeout"}
                    self.save_result(result, test_name)
                    return result
                    
            except Exception as e:
                if attempt < MAX_RETRIES:
                    self.log(f"   Retrying due to error: {e}")
                    time.sleep(2)
                    continue
                else:
                    result = {"test_name": test_name, "error": str(e)}
                    self.save_result(result, test_name)
                    return result
        
        result = {"test_name": test_name, "error": "Max retries exceeded"}
        self.save_result(result, test_name)
        return result
    
    def run_all_tests(self):
        """Run all capability tests with improved handling and storage"""
        self.log("Starting Chef Agent Capability Tests with Storage")
        self.log("=" * 60)
        
        tests = [
            self.test_simple_cookbook,
            self.test_medium_cookbook,
            self.test_complex_cookbook,
            self.test_edge_case_cookbook
        ]
        
        for i, test in enumerate(tests, 1):
            self.log(f"\nRunning Test {i}/{len(tests)}")
            result = test()
            self.results.append(result)
            
            if "error" in result:
                self.log(f"FAILED {result['test_name']}: {result['error']}")
            else:
                self.log(f"PASSED {result['test_name']}: {result['duration']:.1f}s ({result['accuracy']} accuracy)")
            
            if i < len(tests):  # Don't sleep after last test
                self.log("   Waiting 3 seconds before next test...")
                time.sleep(3)
        
        self.generate_report()
    
    def generate_report(self):
        """Generate comprehensive test report with storage"""
        self.log("\n" + "=" * 60)
        self.log("CHEF AGENT CAPABILITY REPORT WITH STORAGE")
        self.log("=" * 60)
        
        total_time = time.time() - self.start_time
        successful_tests = [r for r in self.results if "error" not in r]
        failed_tests = [r for r in self.results if "error" in r]
        
        # Create summary report
        summary = {
            "test_run_id": self.test_run_id,
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "successful_tests": len(successful_tests),
            "failed_tests": len(failed_tests),
            "total_time": total_time,
            "success_rate": round((len(successful_tests) / len(self.results)) * 100, 1) if self.results else 0,
            "results": self.results
        }
        
        # Create detailed report
        detailed_report = {
            "summary": summary,
            "capability_assessment": self._assess_capabilities(successful_tests),
            "performance_metrics": self._calculate_performance_metrics(successful_tests),
            "recommendations": self._generate_recommendations(len(successful_tests)),
            "expectations": self._generate_expectations()
        }
        
        # Save reports
        self.save_summary_report(summary)
        self.save_detailed_report(detailed_report)
        
        # Display results
        self._display_results(summary, detailed_report)
    
    def _assess_capabilities(self, successful_tests: List[Dict]) -> Dict[str, Any]:
        """Assess agent capabilities based on test results"""
        if len(successful_tests) >= 3:
            return {
                "rating": "EXCELLENT",
                "description": "Agent handles most use cases well",
                "production_ready": True,
                "recommended_use": "Simple to medium complexity cookbooks"
            }
        elif len(successful_tests) >= 2:
            return {
                "rating": "GOOD", 
                "description": "Agent works for common scenarios",
                "production_ready": True,
                "recommended_use": "Simple cookbooks"
            }
        elif len(successful_tests) >= 1:
            return {
                "rating": "LIMITED",
                "description": "Agent works for simple cases only",
                "production_ready": False,
                "recommended_use": "Very simple cookbooks only"
            }
        else:
            return {
                "rating": "POOR",
                "description": "Agent needs improvement",
                "production_ready": False,
                "recommended_use": "Not recommended"
            }
    
    def _calculate_performance_metrics(self, successful_tests: List[Dict]) -> Dict[str, Any]:
        """Calculate performance metrics"""
        if not successful_tests:
            return {"error": "No successful tests to analyze"}
        
        avg_duration = sum(r['duration'] for r in successful_tests) / len(successful_tests)
        avg_analysis = sum(r['analysis_time'] for r in successful_tests) / len(successful_tests)
        
        return {
            "average_duration": round(avg_duration, 1),
            "average_analysis_time": round(avg_analysis, 1),
            "performance_rating": "Fast" if avg_duration < 30 else "Moderate" if avg_duration < 60 else "Slow",
            "test_count": len(successful_tests)
        }
    
    def _generate_recommendations(self, successful_count: int) -> Dict[str, Any]:
        """Generate recommendations based on test results"""
        if successful_count >= 3:
            return {
                "production_use": "Ready for production use",
                "complexity_support": "Good for simple to medium complexity cookbooks",
                "limitations": "Complex cookbooks may have reduced accuracy",
                "next_steps": ["Monitor performance", "Gather user feedback", "Plan improvements"]
            }
        elif successful_count >= 2:
            return {
                "production_use": "Suitable for simple cookbooks",
                "complexity_support": "Medium complexity may have issues",
                "limitations": "Avoid complex cookbooks",
                "next_steps": ["Improve error handling", "Add more test cases", "Optimize performance"]
            }
        else:
            return {
                "production_use": "Not ready for production",
                "complexity_support": "Limited to very simple cookbooks",
                "limitations": "Needs significant improvement",
                "next_steps": ["Fix critical issues", "Improve reliability", "Add comprehensive testing"]
            }
    
    def _generate_expectations(self) -> Dict[str, Any]:
        """Generate user expectations"""
        return {
            "what_it_can_do": [
                "Analyze simple Chef cookbooks (1-2 files)",
                "Identify basic resources (package, service, file)",
                "Detect dependencies and metadata",
                "Provide migration recommendations",
                "Complete analysis in 15-60 seconds"
            ],
            "limitations": [
                "Complex cookbooks may timeout",
                "Very large cookbooks may have reduced accuracy",
                "Tree-sitter parsing not available (fallback mode)",
                "No syntax validation for complex Chef patterns",
                "May miss advanced Chef features"
            ],
            "what_it_cannot_do": [
                "Guarantee 100% accuracy for complex cookbooks",
                "Handle enterprise-scale cookbooks reliably",
                "Provide real-time syntax validation",
                "Analyze custom Chef resources without patterns",
                "Process cookbooks with 10+ files consistently"
            ]
        }
    
    def _display_results(self, summary: Dict, detailed_report: Dict):
        """Display results to console"""
        # Summary
        self.log(f"Total Tests: {summary['total_tests']}")
        self.log(f"Successful: {summary['successful_tests']}")
        self.log(f"Failed: {summary['failed_tests']}")
        self.log(f"Success Rate: {summary['success_rate']}%")
        self.log(f"Total Time: {summary['total_time']:.1f} seconds")
        
        # Capability Assessment
        assessment = detailed_report['capability_assessment']
        self.log(f"\nCAPABILITY ASSESSMENT:")
        self.log(f"Rating: {assessment['rating']}")
        self.log(f"Description: {assessment['description']}")
        self.log(f"Production Ready: {assessment['production_ready']}")
        
        # Performance Metrics
        if 'performance_metrics' in detailed_report and 'error' not in detailed_report['performance_metrics']:
            metrics = detailed_report['performance_metrics']
            self.log(f"\nPERFORMANCE METRICS:")
            self.log(f"Average Duration: {metrics['average_duration']}s")
            self.log(f"Average Analysis Time: {metrics['average_analysis_time']}s")
            self.log(f"Performance Rating: {metrics['performance_rating']}")
        
        # Recommendations
        recommendations = detailed_report['recommendations']
        self.log(f"\nRECOMMENDATIONS:")
        self.log(f"Production Use: {recommendations['production_use']}")
        self.log(f"Complexity Support: {recommendations['complexity_support']}")
        self.log(f"Limitations: {recommendations['limitations']}")
        
        self.log(f"\nResults saved to: {self.results_dir}")
        self.log(f"Test run ID: {self.test_run_id}")
        self.log("=" * 60)

def main():
    """Main test runner"""
    print("Chef Agent Capability Test Suite with Storage")
    print("=" * 50)
    print("This version stores results to files for later analysis.")
    print()
    
    tester = ChefAgentTesterWithStorage()
    tester.run_all_tests()

if __name__ == "__main__":
    main() 