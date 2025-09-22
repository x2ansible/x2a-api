"""
Test file to isolate the async issue
"""

def test_analyze_infrastructure_code(state, config=None, *, store=None):
    """Test version with no imports"""
    print("🔍 Test analyzing...")
    source_code = state.get('source_code', '') if isinstance(state, dict) else getattr(state, 'source_code', '')
    platform = "chef"
    return {
        **state,
        "source_platform": platform,
        "infrastructure_analysis": f"Detected {platform}",
        "infrastructure_specification": f"Spec for {platform}"
    }

def test_get_best_practices(state, config=None, *, store=None):
    """Test version with no imports"""
    print("📚 Test best practices...")
    practices = "Use package and service modules"
    return {**state, "best_practices": practices}
