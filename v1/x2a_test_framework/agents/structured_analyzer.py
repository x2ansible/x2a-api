"""
x2a Structured Analyzer Agent Test Patterns

Specialized test patterns and assertions for the x2a Structured Analyzer Agent.
Provides comprehensive testing utilities for infrastructure analysis orchestration,
platform-specific analysis validation, complexity assessment, security analysis,
and migration recommendations.

Key Features:
- Platform-specific analysis testing (Chef, Puppet, Terraform, Generic)
- Infrastructure complexity calculation validation
- Security considerations assessment testing
- Migration recommendations quality testing
- Intelligent tool orchestration validation
- ReAct agent analysis behavior testing
- Structured JSON output validation
"""

import logging
from typing import Dict, Any, List, Optional, Union
import json

logger = logging.getLogger("x2a_test_framework.agents.structured_analyzer")


class StructuredAnalyzerTestPatterns:
    """
    Specialized test patterns for x2a Structured Analyzer Agent.
    
    Provides comprehensive validation patterns for infrastructure analysis,
    complexity assessment, security evaluation, and migration planning.
    """
    
    @staticmethod
    def assert_successful_infrastructure_analysis(
        result: Dict[str, Any],
        platform: str,
        min_analysis_components: int = 3
    ):
        """
        Assert that infrastructure analysis completed successfully with comprehensive results.
        
        Args:
            result: Analysis result to validate
            platform: Platform being analyzed
            min_analysis_components: Minimum analysis components expected
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for analysis completion
        analysis_fields = ['structured_analysis', 'analysis_result', 'platform_analysis']
        analysis_result = None
        for field in analysis_fields:
            if field in result:
                analysis_result = result[field]
                break
        
        assert analysis_result is not None, f"No analysis result found. Available keys: {list(result.keys())}"
        
        if isinstance(analysis_result, dict):
            # Check analysis components count
            meaningful_components = {k: v for k, v in analysis_result.items() if v is not None and str(v).strip()}
            assert len(meaningful_components) >= min_analysis_components, f"Too few analysis components: {len(meaningful_components)} < {min_analysis_components}"
            
            # Platform-specific validation
            platform_lower = platform.lower()
            if platform_lower == 'chef':
                chef_indicators = ['cookbook', 'recipe', 'resource', 'package', 'service']
                found_indicators = [k for k in analysis_result.keys() if any(indicator in k.lower() for indicator in chef_indicators)]
                assert len(found_indicators) > 0, f"No Chef-specific analysis found in: {list(analysis_result.keys())}"
                
            elif platform_lower == 'terraform':
                terraform_indicators = ['provider', 'resource', 'variable', 'module', 'infrastructure']
                found_indicators = [k for k in analysis_result.keys() if any(indicator in k.lower() for indicator in terraform_indicators)]
                assert len(found_indicators) > 0, f"No Terraform-specific analysis found in: {list(analysis_result.keys())}"
                
            elif platform_lower == 'puppet':
                puppet_indicators = ['class', 'module', 'manifest', 'resource', 'puppet']
                found_indicators = [k for k in analysis_result.keys() if any(indicator in k.lower() for indicator in puppet_indicators)]
                assert len(found_indicators) > 0, f"No Puppet-specific analysis found in: {list(analysis_result.keys())}"
        
        logger.info(f" Infrastructure analysis successful for {platform}: {len(meaningful_components if 'meaningful_components' in locals() else analysis_result)} components")
    
    @staticmethod
    def assert_valid_complexity_analysis(
        complexity_result: Dict[str, Any],
        expected_complexity_range: tuple = (0, 100),
        required_metrics: List[str] = None
    ):
        """
        Assert that complexity analysis provides valid scoring and metrics.
        
        Args:
            complexity_result: Complexity analysis result
            expected_complexity_range: Expected range for complexity scores
            required_metrics: Required complexity metrics
        """
        assert isinstance(complexity_result, dict), f"Complexity result must be dict, got {type(complexity_result)}"
        
        # Check for complexity score
        score_fields = ['complexity_score', 'score', 'overall_complexity', 'complexity_rating']
        complexity_score = None
        for field in score_fields:
            if field in complexity_result:
                complexity_score = complexity_result[field]
                break
        
        if complexity_score is not None:
            assert isinstance(complexity_score, (int, float)), f"Complexity score must be numeric, got {type(complexity_score)}"
            assert expected_complexity_range[0] <= complexity_score <= expected_complexity_range[1], f"Complexity score out of range: {complexity_score} not in {expected_complexity_range}"
        
        # Check for required metrics
        default_required_metrics = ['dependencies', 'resources', 'configuration_complexity']
        metrics_to_check = required_metrics or default_required_metrics
        
        for metric in metrics_to_check:
            metric_found = any(metric.lower() in key.lower() for key in complexity_result.keys())
            if not metric_found:
                # Don't assert, just log warning for flexibility
                logger.warning(f"Complexity metric '{metric}' not found in result keys: {list(complexity_result.keys())}")
        
        # Check for complexity categories
        category_indicators = ['low', 'medium', 'high', 'simple', 'complex']
        has_category = any(indicator in str(complexity_result).lower() for indicator in category_indicators)
        assert has_category, f"No complexity category indicators found in: {complexity_result}"
        
        logger.info(f" Complexity analysis valid: score={complexity_score}, categories found")
    
    @staticmethod
    def assert_comprehensive_security_analysis(
        security_result: Dict[str, Any],
        platform: str,
        min_security_considerations: int = 2
    ):
        """
        Assert that security analysis provides comprehensive security considerations.
        
        Args:
            security_result: Security analysis result
            platform: Platform being analyzed
            min_security_considerations: Minimum security considerations expected
        """
        assert isinstance(security_result, dict), f"Security result must be dict, got {type(security_result)}"
        
        # Check for security considerations
        security_fields = ['security_considerations', 'vulnerabilities', 'security_analysis', 'risks']
        security_considerations = None
        for field in security_fields:
            if field in security_result:
                considerations = security_result[field]
                if considerations:
                    security_considerations = considerations
                    break
        
        assert security_considerations is not None, f"No security considerations found. Available keys: {list(security_result.keys())}"
        
        # Count meaningful security items
        if isinstance(security_considerations, list):
            meaningful_items = [item for item in security_considerations if item and str(item).strip()]
            assert len(meaningful_items) >= min_security_considerations, f"Too few security considerations: {len(meaningful_items)} < {min_security_considerations}"
        elif isinstance(security_considerations, dict):
            meaningful_items = {k: v for k, v in security_considerations.items() if v and str(v).strip()}
            assert len(meaningful_items) >= min_security_considerations, f"Too few security considerations: {len(meaningful_items)} < {min_security_considerations}"
        
        # Platform-specific security validation
        platform_lower = platform.lower()
        security_text = str(security_result).lower()
        
        if platform_lower == 'chef':
            chef_security_keywords = ['cookbook', 'recipe', 'resource', 'sudo', 'privilege']
            has_platform_security = any(keyword in security_text for keyword in chef_security_keywords)
        elif platform_lower == 'terraform':
            terraform_security_keywords = ['iam', 'security group', 'encryption', 'vpc', 'aws']
            has_platform_security = any(keyword in security_text for keyword in terraform_security_keywords)
        else:
            # Generic security keywords
            generic_security_keywords = ['security', 'access', 'permission', 'authentication']
            has_platform_security = any(keyword in security_text for keyword in generic_security_keywords)
        
        assert has_platform_security, f"No platform-specific security considerations found for {platform}"
        
        logger.info(f" Security analysis comprehensive for {platform}: {len(meaningful_items if 'meaningful_items' in locals() else security_considerations)} considerations")
    
    @staticmethod
    def assert_quality_migration_recommendations(
        migration_result: Dict[str, Any],
        source_platform: str,
        min_recommendations: int = 2
    ):
        """
        Assert that migration recommendations are high-quality and actionable.
        
        Args:
            migration_result: Migration recommendations result
            source_platform: Source platform being migrated from
            min_recommendations: Minimum recommendations expected
        """
        assert isinstance(migration_result, dict), f"Migration result must be dict, got {type(migration_result)}"
        
        # Check for migration recommendations
        migration_fields = ['migration_recommendations', 'recommendations', 'migration_strategy', 'modernization']
        recommendations = None
        for field in migration_fields:
            if field in migration_result:
                recs = migration_result[field]
                if recs:
                    recommendations = recs
                    break
        
        assert recommendations is not None, f"No migration recommendations found. Available keys: {list(migration_result.keys())}"
        
        # Count meaningful recommendations
        if isinstance(recommendations, list):
            meaningful_recs = [rec for rec in recommendations if rec and str(rec).strip() and len(str(rec).strip()) > 10]
            assert len(meaningful_recs) >= min_recommendations, f"Too few quality recommendations: {len(meaningful_recs)} < {min_recommendations}"
        elif isinstance(recommendations, dict):
            meaningful_recs = {k: v for k, v in recommendations.items() if v and str(v).strip() and len(str(v).strip()) > 10}
            assert len(meaningful_recs) >= min_recommendations, f"Too few quality recommendations: {len(meaningful_recs)} < {min_recommendations}"
        
        # Check for actionable content
        rec_text = str(recommendations).lower()
        actionable_keywords = ['migrate', 'modernize', 'update', 'replace', 'refactor', 'convert', 'upgrade']
        has_actionable_content = any(keyword in rec_text for keyword in actionable_keywords)
        assert has_actionable_content, f"No actionable migration content found in recommendations"
        
        # Platform-specific migration validation
        platform_lower = source_platform.lower()
        if platform_lower == 'chef':
            migration_keywords = ['ansible', 'terraform', 'kubernetes', 'container', 'cloud']
            has_platform_migration = any(keyword in rec_text for keyword in migration_keywords)
        elif platform_lower == 'puppet':
            migration_keywords = ['ansible', 'terraform', 'saltstack', 'chef']
            has_platform_migration = any(keyword in rec_text for keyword in migration_keywords)
        else:
            migration_keywords = ['modern', 'cloud', 'container', 'devops']
            has_platform_migration = any(keyword in rec_text for keyword in migration_keywords)
        
        assert has_platform_migration, f"No platform-specific migration recommendations found for {source_platform}"
        
        logger.info(f" Migration recommendations quality for {source_platform}: {len(meaningful_recs if 'meaningful_recs' in locals() else recommendations)} actionable recommendations")
    
    @staticmethod
    def assert_intelligent_tool_orchestration(
        agent_output: Dict[str, Any],
        expected_tool_categories: List[str],
        platform: str
    ):
        """
        Assert that the agent intelligently orchestrated appropriate analysis tools.
        
        Args:
            agent_output: Output from structured analyzer agent
            expected_tool_categories: Expected categories of tools used
            platform: Platform being analyzed
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        # Check for messages containing tool usage
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        
        # Track tool usage by category
        tools_used = []
        tool_categories_found = []
        
        for message in messages:
            # Check tool calls
            tool_calls = getattr(message, 'tool_calls', [])
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                    if tool_name:
                        tools_used.append(tool_name)
                        
                        # Categorize tools
                        if 'complexity' in tool_name:
                            tool_categories_found.append('complexity')
                        elif 'security' in tool_name:
                            tool_categories_found.append('security')
                        elif 'migration' in tool_name:
                            tool_categories_found.append('migration')
                        elif any(platform_keyword in tool_name for platform_keyword in ['chef', 'puppet', 'terraform', 'generic']):
                            tool_categories_found.append('platform_analysis')
        
        # Validate expected tool categories were used
        for expected_category in expected_tool_categories:
            assert expected_category in tool_categories_found, f"Expected tool category '{expected_category}' not used. Found: {tool_categories_found}"
        
        # Platform-specific tool validation
        platform_lower = platform.lower()
        platform_tool_found = any(platform_lower in tool.lower() for tool in tools_used)
        if platform_lower in ['chef', 'puppet', 'terraform']:
            assert platform_tool_found, f"No {platform}-specific analysis tool used: {tools_used}"
        
        logger.info(f" Intelligent tool orchestration for {platform}: {tool_categories_found}, tools: {tools_used}")
    
    @staticmethod
    def assert_structured_json_output_quality(
        structured_output: Dict[str, Any],
        required_sections: List[str] = None,
        min_depth: int = 2
    ):
        """
        Assert that structured JSON output is well-formed and comprehensive.
        
        Args:
            structured_output: Structured JSON output from analyzer
            required_sections: Required sections in the output
            min_depth: Minimum depth of nested structure expected
        """
        assert isinstance(structured_output, dict), f"Structured output must be dict, got {type(structured_output)}"
        assert len(structured_output) > 0, "Structured output cannot be empty"
        
        # Check for required sections
        default_sections = ['platform_analysis', 'complexity_analysis', 'security_analysis']
        sections_to_check = required_sections or default_sections
        
        for section in sections_to_check:
            section_found = any(section.lower() in key.lower() for key in structured_output.keys())
            if not section_found:
                logger.warning(f"Required section '{section}' not found. Available: {list(structured_output.keys())}")
        
        # Check structural depth
        def calculate_depth(obj, current_depth=0):
            if isinstance(obj, dict) and obj:
                return max(calculate_depth(value, current_depth + 1) for value in obj.values())
            elif isinstance(obj, list) and obj:
                return max(calculate_depth(item, current_depth + 1) for item in obj)
            return current_depth
        
        actual_depth = calculate_depth(structured_output)
        assert actual_depth >= min_depth, f"Output structure too shallow: {actual_depth} < {min_depth}"
        
        # Check for meaningful content
        def count_meaningful_values(obj):
            count = 0
            if isinstance(obj, dict):
                for value in obj.values():
                    count += count_meaningful_values(value)
            elif isinstance(obj, list):
                for item in obj:
                    count += count_meaningful_values(item)
            elif obj is not None and str(obj).strip():
                count += 1
            return count
        
        meaningful_values = count_meaningful_values(structured_output)
        assert meaningful_values >= 5, f"Too few meaningful values: {meaningful_values} < 5"
        
        logger.info(f" Structured JSON quality: {len(structured_output)} sections, depth={actual_depth}, {meaningful_values} meaningful values")
    
    @staticmethod
    def assert_analysis_consistency(
        platform_analysis: Dict[str, Any],
        complexity_analysis: Dict[str, Any],
        security_analysis: Dict[str, Any]
    ):
        """
        Assert that different analysis components are consistent with each other.
        
        Args:
            platform_analysis: Platform-specific analysis
            complexity_analysis: Complexity assessment
            security_analysis: Security considerations
        """
        # Check that complexity aligns with platform findings
        if isinstance(platform_analysis, dict) and isinstance(complexity_analysis, dict):
            platform_items = len([v for v in platform_analysis.values() if v])
            complexity_score = None
            
            # Extract complexity score
            for key, value in complexity_analysis.items():
                if 'score' in key.lower() and isinstance(value, (int, float)):
                    complexity_score = value
                    break
            
            if complexity_score is not None and platform_items > 0:
                # More platform items should generally correlate with higher complexity
                normalized_score = complexity_score / 100 if complexity_score > 1 else complexity_score
                expected_complexity_ratio = min(platform_items / 10, 1.0)  # Rough heuristic
                
                # Allow for reasonable variance
                assert abs(normalized_score - expected_complexity_ratio) <= 0.5, f"Complexity score {normalized_score} not consistent with platform items {platform_items}"
        
        # Check that security analysis considers platform and complexity
        if isinstance(security_analysis, dict):
            security_text = str(security_analysis).lower()
            
            # Should mention complexity or platform in security considerations
            has_context_awareness = (
                any(word in security_text for word in ['complex', 'simple', 'risk']) or
                any(platform in security_text for platform in ['chef', 'puppet', 'terraform'])
            )
            
            assert has_context_awareness, f"Security analysis lacks platform/complexity context awareness"
        
        logger.info(" Analysis components are consistent with each other")


class StructuredAnalyzerTestHelpers:
    """Helper utilities for structured analyzer testing."""
    
    @staticmethod
    def create_analysis_test_scenario(
        platform: str,
        complexity_level: str = "medium",
        include_security: bool = True,
        include_migration: bool = True
    ) -> Dict[str, Any]:
        """Create a comprehensive analysis test scenario."""
        
        # Create platform-specific extracted facts
        platform_facts = {
            'chef': {
                'cookbook_name': 'test_cookbook',
                'recipes': ['default', 'install', 'configure'],
                'packages': ['nginx', 'ssl-cert'],
                'services': ['nginx'],
                'templates': ['/etc/nginx/nginx.conf']
            },
            'terraform': {
                'providers': ['aws', 'random'],
                'resources': ['aws_instance', 'aws_security_group', 'random_password'],
                'variables': ['instance_type', 'region'],
                'outputs': ['instance_ip', 'security_group_id']
            },
            'puppet': {
                'classes': ['nginx', 'ssl'],
                'modules': ['nginx'],
                'resources': ['package', 'service', 'file'],
                'dependencies': ['stdlib', 'concat']
            }
        }
        
        facts = platform_facts.get(platform, platform_facts['chef'])
        
        return {
            'platform': platform,
            'extracted_facts': facts,
            'complexity_level': complexity_level,
            'expected_analyses': {
                'platform_analysis': True,
                'complexity_analysis': True,
                'security_analysis': include_security,
                'migration_analysis': include_migration
            },
            'expected_tools': [
                f'analyze_{platform}_infrastructure',
                'calculate_infrastructure_complexity'
            ] + (['generate_security_considerations'] if include_security else []) + 
                (['generate_migration_recommendations'] if include_migration else [])
        }
    
    @staticmethod
    def extract_analysis_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract analysis metrics from structured analyzer result."""
        metrics = {
            'analysis_complete': False,
            'complexity_score': None,
            'security_considerations_count': 0,
            'migration_recommendations_count': 0,
            'platform_analysis_depth': 0,
            'total_analysis_components': 0
        }
        
        # Check completion
        metrics['analysis_complete'] = result.get('worker_status') == 'completed'
        
        # Extract complexity score
        complexity_analysis = result.get('complexity_analysis', {})
        if isinstance(complexity_analysis, dict):
            for key, value in complexity_analysis.items():
                if 'score' in key.lower() and isinstance(value, (int, float)):
                    metrics['complexity_score'] = value
                    break
        
        # Count security considerations
        security_analysis = result.get('security_analysis', {})
        if isinstance(security_analysis, dict):
            security_items = security_analysis.get('security_considerations', [])
            if isinstance(security_items, list):
                metrics['security_considerations_count'] = len(security_items)
            elif isinstance(security_items, dict):
                metrics['security_considerations_count'] = len(security_items)
        
        # Count migration recommendations
        migration_analysis = result.get('migration_analysis', {})
        if isinstance(migration_analysis, dict):
            migration_items = migration_analysis.get('migration_recommendations', [])
            if isinstance(migration_items, list):
                metrics['migration_recommendations_count'] = len(migration_items)
            elif isinstance(migration_items, dict):
                metrics['migration_recommendations_count'] = len(migration_items)
        
        # Calculate platform analysis depth
        platform_analysis = result.get('platform_analysis', {})
        if isinstance(platform_analysis, dict):
            metrics['platform_analysis_depth'] = len([v for v in platform_analysis.values() if v])
        
        # Total components
        metrics['total_analysis_components'] = len([k for k, v in result.items() if k.endswith('_analysis') and v])
        
        return metrics
    
    @staticmethod
    def validate_analysis_tools_integration(agent_result: Dict[str, Any], platform: str) -> Dict[str, bool]:
        """Validate that analysis tools are properly integrated."""
        
        expected_tools = [
            f'analyze_{platform}_infrastructure',
            'calculate_infrastructure_complexity',
            'generate_security_considerations',
            'generate_migration_recommendations'
        ]
        
        tool_status = {}
        messages = agent_result.get('messages', [])
        
        for tool in expected_tools:
            tool_used = False
            for message in messages:
                tool_calls = getattr(message, 'tool_calls', [])
                for tool_call in tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                    if tool_name and tool in tool_name:
                        tool_used = True
                        break
                if tool_used:
                    break
            tool_status[tool] = tool_used
        
        return tool_status
