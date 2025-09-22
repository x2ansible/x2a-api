"""
Specification Creator Tool for Synthesizer

Creates comprehensive natural language specifications.
"""

from datetime import datetime
from typing import Dict, Any
from langchain_core.tools import tool


@tool
def create_comprehensive_specification(unified_analysis: dict, worker_data: dict) -> Dict[str, Any]:
    """
    Create comprehensive natural language specification.
    
    Generates a complete, human-readable specification that combines
    insights from all workers into a coherent document.
    
    Args:
        unified_analysis: Unified analysis from synthesize_unified_analysis
        worker_data: Raw worker data for additional context
        
    Returns:
        Comprehensive natural language specification
    """
    
    try:
        # Extract real data from worker results
        platform = unified_analysis.get("platform_analysis", {}).get("primary_platform", "unknown")
        completeness = unified_analysis.get("analysis_metadata", {}).get("analysis_completeness", "partial")
        confidence = unified_analysis.get("overall_confidence", 0.5)
        
        # Extract real infrastructure components from worker data
        extracted_data = worker_data.get("extracted_data", {})
        
        # Get real Chef resources from universal_extractor
        universal_facts = extracted_data.get("universal_extractor", {}).get("extracted_facts", {})
        chef_resources = universal_facts.get("resources", [])
        chef_summary = universal_facts.get("summary", "")
        chef_structure = universal_facts.get("structure", "")
        
        # Get structured analysis from structured_analyzer
        structured_data = extracted_data.get("structured_analyzer", {}).get("structured_analysis", {})
        components = structured_data.get("components", [])
        dependencies = structured_data.get("dependencies", [])
        patterns = structured_data.get("patterns", [])
        resource_utilization = structured_data.get("resource_utilization", {})
        platform_specific = structured_data.get("platform_specific", {})
        
        # Build comprehensive specification using real data
        spec_sections = []
        
        # Header with real platform information
        detected_platform = platform if platform != "unknown" else "Chef"
        spec_sections.extend([
            f"# {detected_platform.title()} Infrastructure Specification",
            "",
            f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**Platform**: {detected_platform.title()}",
            f"**Analysis Completeness**: {completeness.title()}",  
            f"**Confidence Score**: {confidence:.1%}",
            ""
        ])
        
        # Executive Summary using real findings
        spec_sections.extend([
            "## Executive Summary",
            ""
        ])
        
        if chef_summary:
            spec_sections.append(f"This specification documents a {detected_platform} infrastructure configuration. {chef_summary}")
        else:
            spec_sections.append(f"This specification documents a {detected_platform} infrastructure configuration with {len(components)} components and {len(dependencies)} dependencies.")
        
        if chef_structure:
            spec_sections.append(f"Structure analysis: {chef_structure}")
            
        spec_sections.append("")
        
        # Technical Overview using real data
        spec_sections.extend([
            "## Technical Overview",
            "",
            "### Platform Analysis",
            f"- **Primary Platform**: {detected_platform}",
            f"- **Component Count**: {len(components)}",
            f"- **Dependencies Count**: {len(dependencies)}",
            ""
        ])
        
        # Real Infrastructure Components
        if components:
            spec_sections.extend([
                "### Infrastructure Components",
                "",
                "The following components were identified in the infrastructure:",
                ""
            ])
            
            for component in components[:10]:  # Limit to first 10 components
                if isinstance(component, dict):
                    comp_name = component.get('name', component.get('type', 'Unknown Component'))
                    comp_desc = component.get('description', component.get('summary', ''))
                    spec_sections.append(f"- **{comp_name}**: {comp_desc}")
                else:
                    spec_sections.append(f"- **{str(component)}**")
            
            spec_sections.append("")
        
        # Real Dependencies  
        if dependencies:
            spec_sections.extend([
                "### Dependencies",
                "",
                "Component dependencies and relationships:",
                ""
            ])
            
            for dependency in dependencies[:10]:  # Limit to first 10 dependencies
                if isinstance(dependency, dict):
                    dep_desc = dependency.get('description', dependency.get('relationship', str(dependency)))
                    spec_sections.append(f"- {dep_desc}")
                else:
                    spec_sections.append(f"- {str(dependency)}")
                    
            spec_sections.append("")
        
        # Real Chef Resources (if available)
        if chef_resources:
            spec_sections.extend([
                f"### {detected_platform} Resources",
                "",
                f"Detected {detected_platform} resources in the configuration:",
                ""
            ])
            
            for resource in chef_resources[:10]:  # Limit to first 10 resources
                if isinstance(resource, dict):
                    res_type = resource.get('type', 'unknown')
                    res_name = resource.get('name', resource.get('rid', 'unnamed'))
                    res_actions = resource.get('actions', [])
                    
                    spec_sections.append(f"- **{res_type}[{res_name}]**")
                    if res_actions:
                        spec_sections.append(f"  - Actions: {', '.join(res_actions) if isinstance(res_actions, list) else res_actions}")
                else:
                    spec_sections.append(f"- {str(resource)}")
                    
            spec_sections.append("")
        
        # Platform-specific patterns
        if patterns:
            spec_sections.extend([
                "### Design Patterns",
                "",
                "Infrastructure patterns identified:",
                ""
            ])
            
            for pattern in patterns[:5]:  # Limit to first 5 patterns
                if isinstance(pattern, dict):
                    pattern_name = pattern.get('name', pattern.get('type', 'Unknown Pattern'))
                    pattern_desc = pattern.get('description', '')
                    spec_sections.append(f"- **{pattern_name}**: {pattern_desc}")
                else:
                    spec_sections.append(f"- {str(pattern)}")
                    
            spec_sections.append("")
        
        # Resource utilization insights
        if resource_utilization:
            spec_sections.extend([
                "### Resource Utilization",
                "",
                "Resource usage analysis:",
                ""
            ])
            
            for key, value in resource_utilization.items():
                if isinstance(value, (str, int, float)):
                    spec_sections.append(f"- **{key.replace('_', ' ').title()}**: {value}")
                    
            spec_sections.append("")
        
        # Platform-specific considerations
        if platform_specific:
            spec_sections.extend([
                f"### {detected_platform}-Specific Considerations",
                "",
            ])
            
            for key, value in platform_specific.items():
                if isinstance(value, (str, int, float)):
                    spec_sections.append(f"- **{key.replace('_', ' ').title()}**: {value}")
                elif isinstance(value, list) and value:
                    spec_sections.append(f"- **{key.replace('_', ' ').title()}**: {', '.join(map(str, value[:3]))}")
                    
            spec_sections.append("")
        
        # Conclusion based on real analysis
        spec_sections.extend([
            "## Implementation Recommendations",
            "",
            f"Based on the analysis of this {detected_platform} infrastructure:",
            "",
            f"1. **Component Management**: {len(components)} components identified requiring coordination",
            f"2. **Dependency Management**: {len(dependencies)} dependencies need careful ordering",
            f"3. **Platform Optimization**: Leverage {detected_platform}-specific best practices",
            "",
            "## Conclusion",
            "",
            f"This {detected_platform} infrastructure specification is based on comprehensive automated analysis.",
            f"The configuration includes {len(components)} components with {len(dependencies)} interdependencies.",
            "Review this specification with your infrastructure team for validation and deployment planning.",
            "",
            "*Generated through automated analysis - validate before production deployment.*"
        ])
        
        specification = "\n".join(spec_sections)
        
        return {
            "success": True,
            "natural_specification": specification,
            "word_count": len(specification.split()),
            "section_count": len([s for s in spec_sections if s.startswith("#")]),
            "specification_quality": "comprehensive"
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "natural_specification": "# Specification Generation Failed\n\nUnable to generate specification due to synthesis error."
        }
