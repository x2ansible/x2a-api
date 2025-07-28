# Chef Analysis Tests

This directory contains tests for the Chef analysis agent.

## Test Files

### `test_capabilities.py`
Comprehensive capability tests that verify the Chef agent's performance across different complexity levels:
- **Simple cookbooks** (1-2 files) - Should work perfectly
- **Medium complexity** (3-4 files) - Should work well
- **Complex cookbooks** (4-5 files) - May have limitations
- **Enterprise complex** (5+ large files) - May fail/timeout

**Features:**
- Stores results to JSON files for analysis
- Retry logic for reliability
- Performance metrics tracking
- Defensive documentation for user expectations

### `test_agent.py`
Unit tests for the Chef analysis agent functionality:
- Agent initialization
- Session management
- Response processing
- Error handling

### `analyze_results.py`
Analysis tool for stored test results:
- Loads and analyzes JSON result files
- Generates performance reports
- Tracks trends over time
- Provides insights for improvement

### `run_tests.py`
Main test runner with command-line interface:
```bash
# Run capability tests
python run_tests.py test

# Analyze stored results
python run_tests.py analyze

# Run tests and analyze results
python run_tests.py both

# Use custom results directory
python run_tests.py both --results-dir my_results
```

## Usage

### Quick Start
```bash
# From project root
python agents/chef_analysis/tests/run_tests.py both
```

### From Chef Analysis Directory
```bash
cd agents/chef_analysis/tests
python run_tests.py both
```

### Individual Tests
```bash
# Run just the capability tests
python test_capabilities.py

# Analyze existing results
python analyze_results.py
```

## Results Storage

Test results are stored in the `test_results/` directory within the tests folder:
- `test_results/YYYYMMDD_HHMMSS_test_name.json` - Individual test results
- `test_results/YYYYMMDD_HHMMSS_summary_report.json` - Overall statistics
- `test_results/YYYYMMDD_HHMMSS_detailed_report.json` - Comprehensive analysis

## Expected Results

### Success Criteria
- **Simple cookbooks**: 15-30s, high accuracy
- **Medium cookbooks**: 30-60s, good accuracy
- **Complex cookbooks**: 60-120s, moderate accuracy
- **Enterprise cookbooks**: 120s+, reduced accuracy

### Capability Assessment
- **EXCELLENT** (3-4 tests pass): Ready for production
- **GOOD** (2-3 tests pass): Suitable for simple cookbooks
- **LIMITED** (1-2 tests pass): Needs improvement
- **POOR** (0-1 tests pass): Not ready for production

## Integration

### CI/CD Pipeline
```yaml
- name: Run Chef Tests
  run: python agents/chef_analysis/tests/run_tests.py test

- name: Analyze Results
  run: python agents/chef_analysis/tests/run_tests.py analyze

- name: Upload Results
  uses: actions/upload-artifact@v2
  with:
    name: chef-test-results
    path: agents/chef_analysis/tests/test_results/
```

### Performance Monitoring
```python
from analyze_results import load_test_results, analyze_results

results = load_test_results()
analysis = analyze_results(results)

if analysis["overall_stats"]["average_success_rate"] < 70:
    print("WARNING: Success rate below threshold")
```

## Maintenance

### Cleanup Old Results
```bash
# Remove results older than 30 days
find agents/chef_analysis/tests/test_results/ -name "*.json" -mtime +30 -delete
```

### Backup Important Results
```bash
# Archive results before major changes
tar -czf chef_test_results_$(date +%Y%m%d).tar.gz agents/chef_analysis/tests/test_results/
```

## Troubleshooting

### Import Errors
```bash
# Make sure you're in the project root
cd /path/to/x2a-api
python agents/chef_analysis/tests/run_tests.py test
```

### Server Not Running
```bash
# Start the server first
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Permission Issues
```bash
# Make scripts executable
chmod +x agents/chef_analysis/tests/run_tests.py
chmod +x agents/chef_analysis/tests/test_capabilities.py
```

This test suite provides **comprehensive validation** and **defensive documentation** for the Chef analysis agent capabilities. 