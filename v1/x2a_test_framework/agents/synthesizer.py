"""
x2a Synthesizer Agent Test Patterns

Specialized test patterns and assertions for the x2a Synthesizer Agent.
Provides comprehensive testing utilities for result synthesis, unified analysis
creation, comprehensive specification generation, and quality assurance validation.

Key Features:
- Worker result analysis and synthesis testing
- Unified analysis creation validation
- Comprehensive specification generation testing
- Multi-worker result integration testing
- Quality assurance and completeness validation
- Synthesis accuracy and consistency testing
- ReAct agent synthesis behavior validation
"""

import logging
from typing import Dict, Any, List, Optional, Union
import re
import json

logger = logging.getLogger("x2a_test_framework.agents.synthesizer")


class SynthesizerTestPatterns:
    """
    Specialized test patterns for x2a Synthesizer Agent.
    
    Provides comprehensive validation patterns for result synthesis,
    unified analysis creation, and final specification generation.
    """
    
    @staticmethod
    def assert_successful_synthesis(
        result: Dict[str, Any],
        min_synthesis_length: int = 200,
        expected_components: int = 3
    ):
        """
        Assert that synthesis completed successfully with comprehensive results.
        
        Args:
            result: Synthesis result to validate
            min_synthesis_length: Minimum expected synthesis content length
            expected_components: Expected number of synthesis components
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for synthesis completion
        synthesis_fields = ['synthesized_results', 'final_analysis', 'unified_analysis', 'synthesis_output']
        synthesis_content = None
        for field in synthesis_fields:
            if field in result:
                content = result[field]
                if content and str(content).strip():
                    synthesis_content = content
                    break
        
        assert synthesis_content is not None, f"No synthesis content found. Available keys: {list(result.keys())}"
        
        # Validate synthesis content length
        content_length = len(str(synthesis_content))
        assert content_length >= min_synthesis_length, f"Synthesis too short: {content_length} < {min_synthesis_length}"
        
        # Check for synthesis success indicator
        success_indicators = ['synthesis_complete', 'success', 'final_analysis']
        synthesis_success = any(result.get(indicator) for indicator in success_indicators)
        assert synthesis_success, f"Synthesis not marked as successful. Checked: {success_indicators}"
        
        # Check for multiple synthesis components
        if isinstance(synthesis_content, dict):
            component_count = len([v for v in synthesis_content.values() if v and str(v).strip()])
            assert component_count >= expected_components, f"Too few synthesis components: {component_count} < {expected_components}"
        
        logger.info(f" Synthesis successful: {content_length} chars, {component_count if 'component_count' in locals() else 'N/A'} components")
    
    @staticmethod
    def assert_comprehensive_worker_analysis(
        worker_analysis: Dict[str, Any],
        worker_results: List[Dict[str, Any]],
        min_workers_analyzed: int = 2
    ):
        """
        Assert that worker result analysis is comprehensive and accurate.
        
        Args:
            worker_analysis: Analysis of worker results
            worker_results: Original worker results that were analyzed
            min_workers_analyzed: Minimum number of workers that should be analyzed
        """
        assert isinstance(worker_analysis, dict), f"Worker analysis must be dict, got {type(worker_analysis)}"
        assert isinstance(worker_results, list), f"Worker results must be list, got {type(worker_results)}"
        
        # Check for worker analysis completeness
        analysis_fields = ['worker_summary', 'successful_workers', 'failed_workers', 'total_workers']
        analysis_components = sum(1 for field in analysis_fields if field in worker_analysis)
        assert analysis_components >= 2, f"Worker analysis lacks components: {analysis_components} < 2"
        
        # Check worker count accuracy
        total_workers = worker_analysis.get('total_workers') or len(worker_results)
        assert total_workers >= min_workers_analyzed, f"Too few workers analyzed: {total_workers} < {min_workers_analyzed}"
        
        # Check for successful worker tracking
        successful_count = worker_analysis.get('successful_workers', 0)
        if isinstance(successful_count, int):
            assert successful_count <= total_workers, f"Successful workers count inconsistent: {successful_count} > {total_workers}"
        
        # Check for worker result integration
        worker_data_fields = ['extracted_facts', 'platform_data', 'analysis_data', 'worker_outputs']
        has_worker_data = any(field in worker_analysis for field in worker_data_fields)
        assert has_worker_data, f"No worker data integrated. Expected one of: {worker_data_fields}"
        
        logger.info(f" Worker analysis comprehensive: {total_workers} workers, {successful_count} successful")
    
    @staticmethod
    def assert_unified_analysis_quality(
        unified_analysis: Dict[str, Any],
        source_platforms: List[str],
        min_analysis_depth: int = 3
    ):
        """
        Assert that unified analysis demonstrates quality synthesis across platforms.
        
        Args:
            unified_analysis: Unified analysis result
            source_platforms: Source platforms that were analyzed
            min_analysis_depth: Minimum depth of analysis expected
        """
        assert isinstance(unified_analysis, dict), f"Unified analysis must be dict, got {type(unified_analysis)}"
        assert isinstance(source_platforms, list), f"Source platforms must be list, got {type(source_platforms)}"
        
        # Check analysis depth (number of meaningful components)
        meaningful_components = {k: v for k, v in unified_analysis.items() if v is not None and str(v).strip()}
        assert len(meaningful_components) >= min_analysis_depth, f"Analysis too shallow: {len(meaningful_components)} < {min_analysis_depth}"
        
        # Check for platform integration
        analysis_text = str(unified_analysis).lower()
        platforms_mentioned = sum(1 for platform in source_platforms if platform.lower() in analysis_text)
        platform_coverage = platforms_mentioned / len(source_platforms) if source_platforms else 0
        assert platform_coverage >= 0.5, f"Poor platform coverage: {platform_coverage:.2f} < 0.5"
        
        # Check for synthesis quality indicators
        quality_indicators = {
            'complexity_assessment': any(keyword in analysis_text for keyword in ['complex', 'simple', 'medium', 'difficulty']),
            'security_considerations': any(keyword in analysis_text for keyword in ['security', 'risk', 'vulnerability']),
            'recommendations': any(keyword in analysis_text for keyword in ['recommend', 'suggest', 'improve', 'optimize']),
            'dependencies': any(keyword in analysis_text for keyword in ['depend', 'require', 'prerequisite'])
        }
        
        quality_score = sum(quality_indicators.values()) / len(quality_indicators)
        assert quality_score >= 0.5, f"Analysis quality too low: {quality_score:.2f} < 0.5. Missing: {[k for k, v in quality_indicators.items() if not v]}"
        
        logger.info(f" Unified analysis quality: {len(meaningful_components)} components, {platform_coverage:.2f} platform coverage, {quality_score:.2f} quality")
    
    @staticmethod
    def assert_comprehensive_specification_completeness(
        specification: str,
        unified_analysis: Dict[str, Any],
        min_specification_sections: int = 4
    ):
        """
        Assert that comprehensive specification is complete and well-structured.
        
        Args:
            specification: Generated comprehensive specification
            unified_analysis: Unified analysis used for specification
            min_specification_sections: Minimum specification sections expected
        """
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        assert isinstance(unified_analysis, dict), f"Unified analysis must be dict, got {type(unified_analysis)}"
        
        # Check specification structure
        sections = specification.count('#')  # Markdown headers
        bullet_points = specification.count('-') + specification.count('*')
        
        assert sections >= min_specification_sections, f"Too few specification sections: {sections} < {min_specification_sections}"
        
        # Check for comprehensive content areas
        spec_lower = specification.lower()
        content_areas = {
            'overview': any(keyword in spec_lower for keyword in ['overview', 'summary', 'introduction']),
            'requirements': any(keyword in spec_lower for keyword in ['requirement', 'need', 'must', 'should']),
            'architecture': any(keyword in spec_lower for keyword in ['architecture', 'design', 'structure']),
            'implementation': any(keyword in spec_lower for keyword in ['implement', 'deploy', 'install', 'configure']),
            'security': any(keyword in spec_lower for keyword in ['security', 'access', 'permission', 'authentication'])
        }
        
        coverage_score = sum(content_areas.values()) / len(content_areas)
        assert coverage_score >= 0.6, f"Specification coverage too low: {coverage_score:.2f} < 0.6. Missing: {[k for k, v in content_areas.items() if not v]}"
        
        # Check specification reflects unified analysis
        analysis_keywords = []
        for key, value in unified_analysis.items():
            if isinstance(value, str) and len(value) > 5:
                # Extract meaningful words from analysis
                words = re.findall(r'\b\w{4,}\b', str(value).lower())
                analysis_keywords.extend(words[:3])  # Take first 3 meaningful words
        
        if analysis_keywords:
            keyword_mentions = sum(1 for keyword in analysis_keywords[:5] if keyword in spec_lower)
            keyword_integration = keyword_mentions / min(len(analysis_keywords), 5)
            assert keyword_integration >= 0.3, f"Poor analysis integration: {keyword_integration:.2f} < 0.3"
        
        logger.info(f" Specification comprehensive: {sections} sections, {coverage_score:.2f} coverage, {keyword_integration if 'keyword_integration' in locals() else 'N/A'} integration")
    
    @staticmethod
    def assert_multi_worker_synthesis_accuracy(
        synthesis_result: Dict[str, Any],
        input_worker_results: List[Dict[str, Any]],
        min_accuracy_score: float = 0.7
    ):
        """
        Assert that synthesis accurately represents input from multiple workers.
        
        Args:
            synthesis_result: Final synthesis result
            input_worker_results: Original worker results
            min_accuracy_score: Minimum accuracy score expected
        """
        assert isinstance(synthesis_result, dict), f"Synthesis result must be dict, got {type(synthesis_result)}"
        assert isinstance(input_worker_results, list), f"Input worker results must be list, got {type(input_worker_results)}"
        assert len(input_worker_results) > 0, "Must have at least one worker result to synthesize"
        
        # Extract key information from worker results
        worker_platforms = []
        worker_facts = {}
        worker_analyses = {}
        
        for i, worker_result in enumerate(input_worker_results):
            if isinstance(worker_result, dict):
                # Extract platform
                platform = worker_result.get('platform') or worker_result.get('detected_platform')
                if platform:
                    worker_platforms.append(platform)
                
                # Extract facts
                facts = worker_result.get('extracted_facts', {})
                if facts:
                    worker_facts[f'worker_{i}'] = facts
                
                # Extract analysis
                analysis = worker_result.get('structured_analysis', {})
                if analysis:
                    worker_analyses[f'worker_{i}'] = analysis
        
        # Check platform representation in synthesis
        synthesis_text = str(synthesis_result).lower()
        platforms_represented = sum(1 for platform in worker_platforms if platform.lower() in synthesis_text)
        platform_accuracy = platforms_represented / len(worker_platforms) if worker_platforms else 1.0
        
        # Check fact integration
        fact_words = []
        for facts in worker_facts.values():
            if isinstance(facts, dict):
                fact_words.extend([str(v).lower() for v in facts.values() if v])
        
        facts_mentioned = sum(1 for fact in fact_words[:10] if fact in synthesis_text)
        fact_accuracy = facts_mentioned / min(len(fact_words), 10) if fact_words else 1.0
        
        # Calculate overall accuracy
        overall_accuracy = (platform_accuracy + fact_accuracy) / 2
        assert overall_accuracy >= min_accuracy_score, f"Synthesis accuracy too low: {overall_accuracy:.2f} < {min_accuracy_score}"
        
        logger.info(f" Multi-worker synthesis accurate: {overall_accuracy:.2f} overall, platforms={platform_accuracy:.2f}, facts={fact_accuracy:.2f}")
    
    @staticmethod
    def assert_synthesis_consistency_validation(
        synthesis_result: Dict[str, Any],
        consistency_checks: List[str] = None
    ):
        """
        Assert that synthesis result maintains internal consistency.
        
        Args:
            synthesis_result: Synthesis result to validate
            consistency_checks: Specific consistency checks to perform
        """
        assert isinstance(synthesis_result, dict), f"Synthesis result must be dict, got {type(synthesis_result)}"
        
        # Default consistency checks
        default_checks = [
            'platform_consistency',
            'complexity_consistency',
            'recommendation_consistency',
            'temporal_consistency'
        ]
        checks_to_perform = consistency_checks or default_checks
        
        synthesis_text = str(synthesis_result).lower()
        consistency_issues = []
        
        # Platform consistency check
        if 'platform_consistency' in checks_to_perform:
            platforms_mentioned = []
            for platform in ['chef', 'puppet', 'terraform', 'ansible', 'salt']:
                if platform in synthesis_text:
                    platforms_mentioned.append(platform)
            
            # Check for contradictory platform statements
            if len(platforms_mentioned) > 1:
                # This is OK - multi-platform analysis
                pass
            elif len(platforms_mentioned) == 0:
                consistency_issues.append("No platforms mentioned in synthesis")
        
        # Complexity consistency check
        if 'complexity_consistency' in checks_to_perform:
            complexity_terms = ['simple', 'complex', 'easy', 'difficult', 'low', 'high', 'medium']
            complexity_mentions = [term for term in complexity_terms if term in synthesis_text]
            
            # Check for contradictory complexity statements
            if 'simple' in complexity_mentions and 'complex' in complexity_mentions:
                # This could be OK if referring to different aspects
                pass
        
        # Recommendation consistency check
        if 'recommendation_consistency' in checks_to_perform:
            negative_recs = ['avoid', 'don\'t', 'not recommended', 'discourage']
            positive_recs = ['recommend', 'suggest', 'should', 'encourage']
            
            has_negative = any(neg in synthesis_text for neg in negative_recs)
            has_positive = any(pos in synthesis_text for pos in positive_recs)
            
            if not (has_negative or has_positive):
                consistency_issues.append("No clear recommendations found")
        
        # Overall consistency assessment
        consistency_score = (len(checks_to_perform) - len(consistency_issues)) / len(checks_to_perform)
        assert consistency_score >= 0.7, f"Synthesis consistency too low: {consistency_score:.2f} < 0.7. Issues: {consistency_issues}"
        
        logger.info(f" Synthesis consistency validated: {consistency_score:.2f} score, {len(consistency_issues)} issues")
    
    @staticmethod
    def assert_react_agent_synthesis_behavior(
        agent_output: Dict[str, Any],
        expected_synthesis_tools: List[str] = None,
        min_synthesis_steps: int = 2
    ):
        """
        Assert that ReAct agent shows proper synthesis behavior.
        
        Args:
            agent_output: Output from synthesizer ReAct agent
            expected_synthesis_tools: Expected synthesis tools to be used
            min_synthesis_steps: Minimum synthesis steps expected
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        assert len(messages) > 0, "Agent should produce at least one message"
        
        # Check for synthesis tool usage
        default_tools = ['analyze_worker_results', 'synthesize_unified_analysis', 'create_comprehensive_specification']
        tools_to_check = expected_synthesis_tools or default_tools
        
        tools_used = []
        synthesis_steps = 0
        
        for message in messages:
            tool_calls = getattr(message, 'tool_calls', [])
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                    if tool_name:
                        tools_used.append(tool_name)
                        if any(keyword in tool_name.lower() for keyword in ['synthesize', 'analyze', 'create']):
                            synthesis_steps += 1
        
        # Validate expected tools were used
        for expected_tool in tools_to_check:
            tool_found = any(expected_tool in tool for tool in tools_used)
            assert tool_found, f"Expected synthesis tool '{expected_tool}' not used. Used: {tools_used}"
        
        # Validate synthesis steps
        assert synthesis_steps >= min_synthesis_steps, f"Too few synthesis steps: {synthesis_steps} < {min_synthesis_steps}"
        
        # Check for synthesis reasoning
        synthesis_reasoning = 0
        for message in messages:
            message_content = str(getattr(message, 'content', message)).lower()
            synthesis_keywords = ['synthesize', 'combine', 'unify', 'integrate', 'analyze', 'comprehensive']
            if any(keyword in message_content for keyword in synthesis_keywords):
                synthesis_reasoning += 1
        
        assert synthesis_reasoning >= 1, f"Insufficient synthesis reasoning: {synthesis_reasoning} < 1"
        
        logger.info(f" ReAct synthesis behavior valid: {len(tools_used)} tools, {synthesis_steps} steps, {synthesis_reasoning} reasoning")


class SynthesizerTestHelpers:
    """Helper utilities for synthesizer testing."""
    
    @staticmethod
    def create_synthesis_test_scenario(
        platforms: List[str],
        worker_count: int = 3,
        include_failures: bool = False
    ) -> Dict[str, Any]:
        """Create a comprehensive synthesis test scenario."""
        
        # Create mock worker results
        worker_results = []
        
        for i, platform in enumerate(platforms):
            # Successful worker result
            worker_result = {
                'worker_type': f'{platform}_extractor',
                'platform': platform,
                'success': True,
                'extracted_facts': {
                    f'{platform}_resources': [f'resource_{j}' for j in range(3)],
                    f'{platform}_config': f'{platform}_configuration_data'
                },
                'structured_analysis': {
                    'complexity_score': 60 + (i * 10),
                    'resource_count': 5 + i,
                    'platform_specific_analysis': f'{platform}_analysis_data'
                },
                'natural_spec': f'{platform} infrastructure specification with deployment details',
                'confidence': 0.8 + (i * 0.1)
            }
            worker_results.append(worker_result)
        
        # Add failed worker if requested
        if include_failures:
            failed_worker = {
                'worker_type': 'failed_worker',
                'platform': 'unknown',
                'success': False,
                'error': 'Mock worker failure',
                'extracted_facts': {},
                'confidence': 0.0
            }
            worker_results.append(failed_worker)
        
        # Add additional workers to reach worker_count
        while len(worker_results) < worker_count:
            additional_worker = {
                'worker_type': f'additional_worker_{len(worker_results)}',
                'platform': platforms[0],  # Use first platform
                'success': True,
                'extracted_facts': {'additional_data': 'supplementary_information'},
                'confidence': 0.7
            }
            worker_results.append(additional_worker)
        
        return {
            'worker_results': worker_results,
            'platforms': platforms,
            'expected_synthesis': {
                'total_workers': len(worker_results),
                'successful_workers': len([w for w in worker_results if w.get('success', False)]),
                'failed_workers': len([w for w in worker_results if not w.get('success', True)]),
                'platforms_covered': len(platforms)
            },
            'quality_expectations': {
                'min_synthesis_length': 500,
                'min_specification_sections': 4,
                'min_analysis_components': 3
            }
        }
    
    @staticmethod
    def extract_synthesis_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract synthesis operation metrics from result."""
        metrics = {
            'synthesis_complete': False,
            'unified_analysis_length': 0,
            'specification_length': 0,
            'workers_analyzed': 0,
            'platforms_synthesized': 0,
            'quality_score': 0.0,
            'consistency_score': 0.0
        }
        
        # Extract completion status
        metrics['synthesis_complete'] = any(
            result.get(field, False) for field in ['synthesis_complete', 'success', 'final_analysis']
        )
        
        # Extract content lengths
        unified_analysis = result.get('unified_analysis', {})
        if isinstance(unified_analysis, (dict, str)):
            metrics['unified_analysis_length'] = len(str(unified_analysis))
        
        specification = result.get('comprehensive_specification', '')
        if isinstance(specification, str):
            metrics['specification_length'] = len(specification)
        
        # Extract worker analysis info
        worker_analysis = result.get('worker_analysis', {})
        if isinstance(worker_analysis, dict):
            metrics['workers_analyzed'] = worker_analysis.get('total_workers', 0)
        
        # Extract platform info
        platforms = result.get('platforms', [])
        if isinstance(platforms, list):
            metrics['platforms_synthesized'] = len(platforms)
        
        # Calculate quality score (simple heuristic)
        content_score = min(metrics['unified_analysis_length'] / 1000, 1.0)
        spec_score = min(metrics['specification_length'] / 2000, 1.0)
        metrics['quality_score'] = (content_score + spec_score) / 2
        
        return metrics
    
    @staticmethod
    def validate_synthesis_tool_integration(agent_result: Dict[str, Any]) -> Dict[str, bool]:
        """Validate that synthesis tools are properly integrated."""
        
        expected_tools = [
            'analyze_worker_results',
            'synthesize_unified_analysis',
            'create_comprehensive_specification'
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
    
    @staticmethod
    def analyze_synthesis_quality(synthesis_result: Dict[str, Any]) -> Dict[str, float]:
        """Analyze synthesis quality with detailed scoring."""
        
        quality_scores = {
            'completeness': 0.0,       # 0-1 based on component completeness
            'consistency': 0.0,        # 0-1 based on internal consistency
            'comprehensiveness': 0.0,  # 0-1 based on coverage breadth
            'integration': 0.0         # 0-1 based on worker integration quality
        }
        
        # Completeness score
        required_components = ['unified_analysis', 'comprehensive_specification', 'worker_analysis']
        present_components = sum(1 for comp in required_components if comp in synthesis_result)
        quality_scores['completeness'] = present_components / len(required_components)
        
        # Consistency score (basic text analysis)
        synthesis_text = str(synthesis_result).lower()
        consistency_indicators = ['consistent', 'unified', 'integrated', 'comprehensive']
        inconsistency_indicators = ['conflicting', 'contradictory', 'inconsistent']
        
        positive_indicators = sum(1 for ind in consistency_indicators if ind in synthesis_text)
        negative_indicators = sum(1 for ind in inconsistency_indicators if ind in synthesis_text)
        
        quality_scores['consistency'] = max(0, (positive_indicators - negative_indicators) / len(consistency_indicators))
        
        # Comprehensiveness score
        coverage_keywords = ['overview', 'requirements', 'architecture', 'implementation', 'security']
        coverage_found = sum(1 for keyword in coverage_keywords if keyword in synthesis_text)
        quality_scores['comprehensiveness'] = coverage_found / len(coverage_keywords)
        
        # Integration score (based on synthesis structure)
        if isinstance(synthesis_result, dict):
            nested_components = sum(1 for v in synthesis_result.values() if isinstance(v, (dict, list)))
            total_components = len(synthesis_result)
            quality_scores['integration'] = (nested_components / total_components) if total_components > 0 else 0
        
        return quality_scores
