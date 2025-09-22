"""
x2a Spec Generator Agent Test Patterns

Specialized test patterns and assertions for the x2a Spec Generator Agent.
Provides comprehensive testing utilities for production-grade specification
generation using GitHub Spec Kit methodology, quality metrics validation,
and specification completeness assessment.

Key Features:
- GitHub Spec Kit methodology compliance testing
- Production-grade specification quality validation
- Review checklist and acceptance criteria testing
- Quality metrics assessment (word count, sections, checklists)
- Specification completeness and structure validation
- Template-based generation testing
- ReAct agent specification behavior validation
"""

import logging
from typing import Dict, Any, List, Optional, Union
import re

logger = logging.getLogger("x2a_test_framework.agents.spec_generator")


class SpecGeneratorTestPatterns:
    """
    Specialized test patterns for x2a Spec Generator Agent.
    
    Provides comprehensive validation patterns for production-grade specification
    generation, Spec Kit compliance, and quality assessment.
    """
    
    @staticmethod
    def assert_successful_spec_generation(
        result: Dict[str, Any],
        min_specification_length: int = 500,
        expected_quality: str = "prod_grade"
    ):
        """
        Assert that specification generation completed successfully with quality output.
        
        Args:
            result: Specification generation result to validate
            min_specification_length: Minimum expected specification length
            expected_quality: Expected specification quality level
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for specification content
        spec_fields = ['spec_kit_specification', 'specification', 'generated_spec']
        specification = None
        for field in spec_fields:
            if field in result:
                specification = result[field]
                break
        
        assert specification is not None, f"No specification found. Available keys: {list(result.keys())}"
        assert isinstance(specification, str), f"Specification must be string, got {type(specification)}"
        assert len(specification) >= min_specification_length, f"Specification too short: {len(specification)} < {min_specification_length}"
        
        # Check for success indicator
        success = result.get('success', True)
        assert success is True, f"Specification generation failed: {result.get('error', 'Unknown error')}"
        
        # Check quality metrics if available
        quality_metrics = result.get('quality_metrics', {})
        if quality_metrics:
            spec_quality = quality_metrics.get('specification_quality')
            if spec_quality:
                assert spec_quality == expected_quality, f"Specification quality mismatch: {spec_quality} != {expected_quality}"
        
        logger.info(f" Spec generation successful: {len(specification)} chars, quality={quality_metrics.get('specification_quality', 'unknown')}")
    
    @staticmethod
    def assert_spec_kit_methodology_compliance(
        specification: str,
        quality_metrics: Dict[str, Any],
        min_sections: int = 3
    ):
        """
        Assert that specification follows GitHub Spec Kit methodology.
        
        Args:
            specification: Generated specification content
            quality_metrics: Quality metrics from spec generation
            min_sections: Minimum number of sections expected
        """
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        assert isinstance(quality_metrics, dict), f"Quality metrics must be dict, got {type(quality_metrics)}"
        
        # Check Spec Kit integration
        spec_kit_integrated = quality_metrics.get('spec_kit_integrated', False)
        assert spec_kit_integrated is True, "Specification must be Spec Kit integrated"
        
        # Check for required Spec Kit elements
        spec_lower = specification.lower()
        
        # Check for sections (markdown headers)
        section_count = quality_metrics.get('section_count', 0)
        assert section_count >= min_sections, f"Too few sections: {section_count} < {min_sections}"
        
        # Check for Spec Kit structural elements
        spec_kit_elements = {
            'headers': specification.count('#') >= min_sections,
            'overview': any(keyword in spec_lower for keyword in ['overview', 'summary', 'description']),
            'requirements': any(keyword in spec_lower for keyword in ['requirement', 'criteria', 'must']),
            'structure': any(keyword in spec_lower for keyword in ['structure', 'architecture', 'design'])
        }
        
        missing_elements = [element for element, present in spec_kit_elements.items() if not present]
        assert len(missing_elements) <= 1, f"Missing Spec Kit elements: {missing_elements}"
        
        logger.info(f" Spec Kit compliance: {section_count} sections, elements present: {list(spec_kit_elements.keys())}")
    
    @staticmethod
    def assert_comprehensive_quality_metrics(
        quality_metrics: Dict[str, Any],
        min_word_count: int = 100,
        min_checklist_items: int = 3
    ):
        """
        Assert that quality metrics indicate comprehensive specification.
        
        Args:
            quality_metrics: Quality metrics from specification generation
            min_word_count: Minimum expected word count
            min_checklist_items: Minimum expected checklist items
        """
        assert isinstance(quality_metrics, dict), f"Quality metrics must be dict, got {type(quality_metrics)}"
        
        # Check word count
        word_count = quality_metrics.get('word_count')
        if word_count is not None:
            assert isinstance(word_count, int), f"Word count must be integer, got {type(word_count)}"
            assert word_count >= min_word_count, f"Word count too low: {word_count} < {min_word_count}"
        
        # Check section count
        section_count = quality_metrics.get('section_count')
        if section_count is not None:
            assert isinstance(section_count, int), f"Section count must be integer, got {type(section_count)}"
            assert section_count >= 1, f"Must have at least 1 section, got {section_count}"
        
        # Check checklist items
        checklist_items = quality_metrics.get('checklist_items')
        if checklist_items is not None:
            assert isinstance(checklist_items, int), f"Checklist items must be integer, got {type(checklist_items)}"
            assert checklist_items >= min_checklist_items, f"Too few checklist items: {checklist_items} < {min_checklist_items}"
        
        # Check required quality indicators
        required_indicators = ['includes_review_checklist', 'includes_acceptance_criteria']
        for indicator in required_indicators:
            value = quality_metrics.get(indicator)
            if value is not None:
                assert value is True, f"Quality indicator {indicator} should be True, got {value}"
        
        logger.info(f" Quality metrics comprehensive: words={word_count}, sections={section_count}, checklist={checklist_items}")
    
    @staticmethod
    def assert_review_checklist_presence(
        specification: str,
        min_checklist_items: int = 3,
        checklist_format: str = "markdown"
    ):
        """
        Assert that specification includes proper review checklists.
        
        Args:
            specification: Generated specification content
            min_checklist_items: Minimum checklist items expected
            checklist_format: Expected checklist format
        """
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        
        # Check for checklist items based on format
        if checklist_format == "markdown":
            # Look for markdown checklist syntax
            checklist_patterns = [
                r'- \[ \]',  # Empty checkbox
                r'- \[x\]',  # Checked checkbox
                r'- \[X\]'   # Checked checkbox (capital)
            ]
            
            checklist_items = 0
            for pattern in checklist_patterns:
                checklist_items += len(re.findall(pattern, specification))
            
            assert checklist_items >= min_checklist_items, f"Too few checklist items: {checklist_items} < {min_checklist_items}"
        
        # Check for review-related sections
        review_keywords = ['review', 'checklist', 'acceptance', 'criteria', 'verification']
        spec_lower = specification.lower()
        review_sections = sum(1 for keyword in review_keywords if keyword in spec_lower)
        
        assert review_sections >= 1, f"No review-related sections found. Keywords checked: {review_keywords}"
        
        logger.info(f" Review checklist present: {checklist_items} items, {review_sections} review sections")
    
    @staticmethod
    def assert_acceptance_criteria_quality(
        specification: str,
        min_criteria_count: int = 2,
        criteria_specificity: float = 0.7
    ):
        """
        Assert that acceptance criteria are well-defined and specific.
        
        Args:
            specification: Generated specification content
            min_criteria_count: Minimum acceptance criteria expected
            criteria_specificity: Minimum specificity score (0-1)
        """
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        
        spec_lower = specification.lower()
        
        # Look for acceptance criteria indicators
        criteria_keywords = ['must', 'should', 'shall', 'will', 'criteria', 'requirement']
        criteria_sentences = []
        
        # Find sentences containing criteria keywords
        sentences = specification.split('.')
        for sentence in sentences:
            sentence_lower = sentence.lower()
            if any(keyword in sentence_lower for keyword in criteria_keywords):
                criteria_sentences.append(sentence.strip())
        
        assert len(criteria_sentences) >= min_criteria_count, f"Too few acceptance criteria: {len(criteria_sentences)} < {min_criteria_count}"
        
        # Check criteria specificity (length and detail)
        specific_criteria = 0
        for criteria in criteria_sentences:
            # Consider criteria specific if it's detailed enough
            if len(criteria) > 20 and any(detail_word in criteria.lower() for detail_word in ['implement', 'configure', 'enable', 'provide', 'ensure']):
                specific_criteria += 1
        
        specificity_score = specific_criteria / len(criteria_sentences) if criteria_sentences else 0
        assert specificity_score >= criteria_specificity, f"Criteria specificity too low: {specificity_score:.2f} < {criteria_specificity}"
        
        logger.info(f" Acceptance criteria quality: {len(criteria_sentences)} criteria, {specificity_score:.2f} specificity")
    
    @staticmethod
    def assert_specification_structure_completeness(
        specification: str,
        required_sections: List[str] = None,
        min_content_per_section: int = 50
    ):
        """
        Assert that specification has complete structure with adequate content.
        
        Args:
            specification: Generated specification content
            required_sections: Required sections to validate
            min_content_per_section: Minimum content length per section
        """
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        
        # Default required sections for infrastructure specifications
        default_sections = ['overview', 'requirements', 'architecture', 'implementation']
        sections_to_check = required_sections or default_sections
        
        spec_lower = specification.lower()
        
        # Check for required sections
        sections_found = []
        for section in sections_to_check:
            section_patterns = [
                f'# {section}',          # H1 header
                f'## {section}',         # H2 header
                f'### {section}',        # H3 header
                f'{section}:',           # Colon format
                section                  # Basic keyword presence
            ]
            
            if any(pattern.lower() in spec_lower for pattern in section_patterns):
                sections_found.append(section)
        
        missing_sections = set(sections_to_check) - set(sections_found)
        assert len(missing_sections) <= 1, f"Missing required sections: {missing_sections}. Found: {sections_found}"
        
        # Check content adequacy (approximate)
        words_per_section = len(specification.split()) / max(len(sections_found), 1)
        assert words_per_section >= min_content_per_section, f"Insufficient content per section: {words_per_section:.1f} words < {min_content_per_section}"
        
        logger.info(f" Structure completeness: {len(sections_found)}/{len(sections_to_check)} sections, {words_per_section:.1f} words/section")
    
    @staticmethod
    def assert_production_grade_quality(
        result: Dict[str, Any],
        specification: str,
        quality_benchmarks: Dict[str, Any] = None
    ):
        """
        Assert that specification meets production-grade quality standards.
        
        Args:
            result: Complete specification generation result
            specification: Generated specification content
            quality_benchmarks: Custom quality benchmarks
        """
        assert isinstance(result, dict), f"Result must be dict, got {type(result)}"
        assert isinstance(specification, str) and specification.strip(), "Specification must be non-empty string"
        
        # Default production quality benchmarks
        default_benchmarks = {
            'min_word_count': 300,
            'min_sections': 4,
            'min_checklist_items': 5,
            'min_criteria_count': 3,
            'methodology_compliance': True,
            'template_integration': True
        }
        benchmarks = quality_benchmarks or default_benchmarks
        
        quality_metrics = result.get('quality_metrics', {})
        
        # Check word count benchmark
        word_count = quality_metrics.get('word_count', len(specification.split()))
        assert word_count >= benchmarks['min_word_count'], f"Word count below production standard: {word_count} < {benchmarks['min_word_count']}"
        
        # Check sections benchmark
        section_count = quality_metrics.get('section_count', specification.count('#'))
        assert section_count >= benchmarks['min_sections'], f"Section count below production standard: {section_count} < {benchmarks['min_sections']}"
        
        # Check methodology compliance
        if benchmarks['methodology_compliance']:
            methodology = result.get('methodology')
            assert methodology and 'spec_kit' in methodology, f"Must use Spec Kit methodology, got: {methodology}"
        
        # Check for production quality indicators
        production_indicators = [
            'review checklist' in specification.lower(),
            'acceptance criteria' in specification.lower() or 'requirements' in specification.lower(),
            len(specification) > 500,
            specification.count('#') >= 3,  # Multiple sections
        ]
        
        production_score = sum(production_indicators) / len(production_indicators)
        assert production_score >= 0.75, f"Production quality score too low: {production_score:.2f} < 0.75"
        
        logger.info(f" Production-grade quality: {word_count} words, {section_count} sections, score={production_score:.2f}")
    
    @staticmethod
    def assert_react_agent_spec_behavior(
        agent_output: Dict[str, Any],
        expected_tool_usage: bool = True,
        expected_methodology: str = "spec_kit"
    ):
        """
        Assert that ReAct agent shows proper specification generation behavior.
        
        Args:
            agent_output: Output from spec generator ReAct agent
            expected_tool_usage: Whether tool usage is expected
            expected_methodology: Expected methodology used
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        assert len(messages) > 0, "Agent should produce at least one message"
        
        # Check for tool usage if expected
        if expected_tool_usage:
            tool_usage_found = False
            for message in messages:
                tool_calls = getattr(message, 'tool_calls', [])
                if tool_calls:
                    for tool_call in tool_calls:
                        tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                        if tool_name and 'spec' in tool_name.lower():
                            tool_usage_found = True
                            break
                if tool_usage_found:
                    break
            
            assert tool_usage_found, "Expected specification tool usage but none found"
        
        # Check for specification-related reasoning
        spec_reasoning = 0
        for message in messages:
            message_content = str(getattr(message, 'content', message)).lower()
            spec_keywords = ['specification', 'spec', 'document', 'requirements', 'criteria']
            if any(keyword in message_content for keyword in spec_keywords):
                spec_reasoning += 1
        
        assert spec_reasoning >= 1, f"Insufficient specification reasoning: {spec_reasoning} < 1"
        
        logger.info(f" ReAct spec behavior valid: {len(messages)} messages, {spec_reasoning} reasoning steps")


class SpecGeneratorTestHelpers:
    """Helper utilities for spec generator testing."""
    
    @staticmethod
    def create_spec_generation_scenario(
        platform: str,
        complexity: str = "medium",
        include_analysis: bool = True
    ) -> Dict[str, Any]:
        """Create a specification generation test scenario."""
        
        # Platform-specific analysis data
        platform_analyses = {
            'chef': {
                'platform_analysis': {
                    'cookbook_structure': {'recipes': 3, 'templates': 2},
                    'dependencies': ['nginx', 'ssl-cert'],
                    'services': ['nginx']
                },
                'complexity_analysis': {'score': 60, 'level': 'medium'},
                'security_analysis': {'considerations': ['sudo usage', 'file permissions']}
            },
            'terraform': {
                'platform_analysis': {
                    'resources': ['aws_instance', 'aws_security_group'],
                    'providers': ['aws'],
                    'variables': ['instance_type', 'region']
                },
                'complexity_analysis': {'score': 75, 'level': 'medium'},
                'security_analysis': {'considerations': ['IAM roles', 'security groups']}
            }
        }
        
        unified_analysis = platform_analyses.get(platform, platform_analyses['chef'])
        
        extracted_facts = {
            'chef': {'cookbook_name': 'web_server', 'packages': ['nginx']},
            'terraform': {'resources': ['aws_instance'], 'providers': ['aws']}
        }.get(platform, {'platform': platform})
        
        return {
            'platform': platform,
            'unified_analysis': unified_analysis if include_analysis else {},
            'extracted_facts': extracted_facts,
            'complexity_level': complexity,
            'expected_spec_elements': {
                'sections': 4,
                'checklist_items': 5,
                'word_count': 300,
                'methodology': 'spec_kit_integrated'
            }
        }
    
    @staticmethod
    def extract_spec_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract specification metrics from generation result."""
        metrics = {
            'generation_complete': False,
            'word_count': 0,
            'section_count': 0,
            'checklist_items': 0,
            'spec_kit_integrated': False,
            'quality_level': 'unknown',
            'methodology': 'unknown'
        }
        
        # Extract from quality metrics
        quality_metrics = result.get('quality_metrics', {})
        if isinstance(quality_metrics, dict):
            metrics.update({
                'word_count': quality_metrics.get('word_count', 0),
                'section_count': quality_metrics.get('section_count', 0),
                'checklist_items': quality_metrics.get('checklist_items', 0),
                'spec_kit_integrated': quality_metrics.get('spec_kit_integrated', False),
                'quality_level': quality_metrics.get('specification_quality', 'unknown')
            })
        
        # Extract methodology
        metrics['methodology'] = result.get('methodology', 'unknown')
        
        # Check completion
        metrics['generation_complete'] = result.get('success', False)
        
        return metrics
    
    @staticmethod
    def validate_spec_kit_structure(specification: str) -> Dict[str, bool]:
        """Validate Spec Kit structural elements in specification."""
        
        structure_checks = {
            'has_title': specification.startswith('#') or 'title' in specification.lower(),
            'has_overview': 'overview' in specification.lower() or 'summary' in specification.lower(),
            'has_requirements': 'requirement' in specification.lower() or 'criteria' in specification.lower(),
            'has_checklist': '- [ ]' in specification or '- [x]' in specification,
            'has_sections': specification.count('#') >= 3,
            'has_detailed_content': len(specification.split()) >= 200
        }
        
        return structure_checks
    
    @staticmethod
    def analyze_specification_quality(specification: str) -> Dict[str, float]:
        """Analyze specification quality with scoring."""
        
        quality_scores = {
            'content_depth': 0.0,      # 0-1 based on content richness
            'structure_score': 0.0,    # 0-1 based on structural elements
            'actionability': 0.0,      # 0-1 based on actionable content
            'completeness': 0.0        # 0-1 based on completeness indicators
        }
        
        words = specification.split()
        word_count = len(words)
        
        # Content depth (based on length and detail)
        if word_count >= 500:
            quality_scores['content_depth'] = 1.0
        elif word_count >= 300:
            quality_scores['content_depth'] = 0.8
        elif word_count >= 200:
            quality_scores['content_depth'] = 0.6
        else:
            quality_scores['content_depth'] = word_count / 200
        
        # Structure score
        section_count = specification.count('#')
        checklist_items = specification.count('- [')
        
        structure_elements = min(section_count / 4, 1.0) + min(checklist_items / 5, 1.0)
        quality_scores['structure_score'] = min(structure_elements / 2, 1.0)
        
        # Actionability (based on action words)
        action_words = ['implement', 'configure', 'install', 'deploy', 'setup', 'create', 'enable']
        action_count = sum(1 for word in words if word.lower() in action_words)
        quality_scores['actionability'] = min(action_count / 10, 1.0)
        
        # Completeness (based on key sections)
        key_sections = ['overview', 'requirements', 'implementation', 'review']
        spec_lower = specification.lower()
        sections_present = sum(1 for section in key_sections if section in spec_lower)
        quality_scores['completeness'] = sections_present / len(key_sections)
        
        return quality_scores
