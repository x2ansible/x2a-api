# agents/ansible_upgrade/response_models.py - Analysis Focus

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class AnsibleCurrentState(BaseModel):
    """Current state analysis of Ansible content"""
    estimated_version: Optional[str] = None
    deprecated_modules: List[str] = Field(default_factory=list)
    deprecated_syntax: List[str] = Field(default_factory=list)
    has_collections_block: bool = False
    complexity_indicators: List[str] = Field(default_factory=list)

class AnsibleUpgradeRequirements(BaseModel):
    """Upgrade requirements assessment"""
    fqcn_conversions_needed: List[str] = Field(default_factory=list)
    syntax_modernizations_needed: List[str] = Field(default_factory=list)
    collections_to_add: List[str] = Field(default_factory=list)
    structural_changes_needed: List[str] = Field(default_factory=list)

class ComplexityAssessment(BaseModel):
    """Complexity and effort assessment"""
    level: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")
    factors: List[str] = Field(default_factory=list)
    estimated_effort_hours: float = Field(default=8.0, ge=0)
    risk_level: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH)$")

class UpgradeRecommendations(BaseModel):
    """Upgrade recommendations and approach"""
    upgrade_priority: str = Field(default="MEDIUM", pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    upgrade_approach: str = Field(default="INCREMENTAL", pattern="^(INCREMENTAL|COMPLETE|REWRITE)$")
    key_considerations: List[str] = Field(default_factory=list)
    ansible_equivalent_approach: Optional[str] = None

class TransformationPlan(BaseModel):
    """Step-by-step transformation plan"""
    step_1: str = Field(default="Analyze current content")
    step_2: str = Field(default="Identify deprecated patterns")
    step_3: str = Field(default="Plan modernization approach")
    step_4: str = Field(default="Implement and validate changes")

class ReActReasoning(BaseModel):
    """ReAct pattern reasoning steps"""
    think: Optional[str] = None
    act: Optional[str] = None
    observe: Optional[str] = None

class AnalysisValidation(BaseModel):
    """Validation metrics for analysis quality"""
    completeness_score: float = Field(default=0.0, ge=0, le=100)
    field_validation: Dict[str, bool] = Field(default_factory=dict)
    quality_issues: List[str] = Field(default_factory=list)
    is_complete: bool = False
    validation_timestamp: Optional[str] = None

class AnalysisMetadata(BaseModel):
    """Analysis metadata and tracking"""
    analyzed_at: str
    processor_version: str = "1.0.0"
    correlation_id: str
    fallback_used: bool = False
    fallback_reason: Optional[str] = None
    original_content_length: Optional[int] = None
    original_content_preview: Optional[str] = None

class AnsibleUpgradeAnalysisResponse(BaseModel):
    """Complete Ansible upgrade analysis response"""
    success: bool = True
    analysis_type: str = "ansible_upgrade_assessment"
    filename: Optional[str] = None
    
    # Core analysis sections
    react_reasoning: Optional[ReActReasoning] = None
    current_state: AnsibleCurrentState
    upgrade_requirements: AnsibleUpgradeRequirements
    complexity_assessment: ComplexityAssessment
    recommendations: UpgradeRecommendations
    transformation_plan: TransformationPlan
    
    # Required detailed analysis (100-150 words)
    detailed_analysis: str = Field(
        ..., 
        min_length=50,
        description="Detailed technical summary (100-150 words) covering purpose, complexity, upgrade requirements"
    )
    
    # Analysis quality and validation
    analysis_validation: Optional[AnalysisValidation] = None
    reasoning_steps: List[Dict[str, Any]] = Field(default_factory=list)
    total_react_steps: int = 0
    
    # Session and tracking info
    session_info: Dict[str, Any] = Field(default_factory=dict)
    metadata: AnalysisMetadata
    correlation_id: str

class SimplifiedAnalysisResponse(BaseModel):
    """Simplified response for quick analysis"""
    success: bool
    analysis_type: str = "ansible_upgrade_assessment"
    estimated_version: str
    complexity_level: str
    upgrade_priority: str
    estimated_effort_hours: float
    key_issues: List[str]
    recommendations: List[str]
    correlation_id: str

class AnalysisError(BaseModel):
    """Error response for failed analysis"""
    success: bool = False
    error: str
    error_type: str = "analysis_error"
    correlation_id: str
    timestamp: str
    original_content_preview: Optional[str] = None

class BatchAnalysisResponse(BaseModel):
    """Response for batch analysis of multiple files"""
    success: bool
    total_files: int
    successful_analyses: int
    failed_analyses: int
    results: List[AnsibleUpgradeAnalysisResponse]
    batch_summary: Dict[str, Any]
    correlation_id: str

# Validation helpers and utility models

class AnalysisRequest(BaseModel):
    """Request model for analysis"""
    content: str = Field(..., min_length=1, description="Ansible content to analyze")
    filename: Optional[str] = Field(default="playbook.yml", description="Original filename")
    correlation_id: Optional[str] = None

class StreamAnalysisEvent(BaseModel):
    """Streaming analysis event"""
    type: str = Field(..., pattern="^(start|progress|final_result|error)$")
    message: Optional[str] = None
    progress: Optional[float] = Field(None, ge=0, le=1.0)
    data: Optional[Dict[str, Any]] = None
    correlation_id: str
    timestamp: str

# Legacy compatibility models (for migration from upgrade-focused to analysis-focused)

class LegacyUpgradeResponse(BaseModel):
    """Legacy model for backward compatibility"""
    success: bool
    upgraded_content: Optional[str] = None  # Now optional since we focus on analysis
    analysis_result: Optional[AnsibleUpgradeAnalysisResponse] = None
    correlation_id: str
    
    class Config:
        # Allow extra fields for backward compatibility
        extra = "allow"

# Factory functions for creating responses

def create_analysis_response(
    analysis_data: Dict[str, Any],
    correlation_id: str,
    filename: Optional[str] = None
) -> AnsibleUpgradeAnalysisResponse:
    """Factory function to create analysis response"""
    
    from datetime import datetime
    
    # Ensure required metadata
    if "metadata" not in analysis_data:
        analysis_data["metadata"] = AnalysisMetadata(
            analyzed_at=datetime.utcnow().isoformat(),
            correlation_id=correlation_id
        )
    
    # Set filename if provided
    if filename:
        analysis_data["filename"] = filename
    
    # Ensure correlation_id is set
    analysis_data["correlation_id"] = correlation_id
    
    return AnsibleUpgradeAnalysisResponse(**analysis_data)

def create_error_response(
    error_message: str,
    correlation_id: str,
    error_type: str = "analysis_error",
    content_preview: Optional[str] = None
) -> AnalysisError:
    """Factory function to create error response"""
    
    from datetime import datetime
    
    return AnalysisError(
        error=error_message,
        error_type=error_type,
        correlation_id=correlation_id,
        timestamp=datetime.utcnow().isoformat(),
        original_content_preview=content_preview
    )

def create_simplified_response(
    analysis_result: AnsibleUpgradeAnalysisResponse
) -> SimplifiedAnalysisResponse:
    """Create simplified response from full analysis"""
    
    return SimplifiedAnalysisResponse(
        success=analysis_result.success,
        estimated_version=analysis_result.current_state.estimated_version or "unknown",
        complexity_level=analysis_result.complexity_assessment.level,
        upgrade_priority=analysis_result.recommendations.upgrade_priority,
        estimated_effort_hours=analysis_result.complexity_assessment.estimated_effort_hours,
        key_issues=analysis_result.current_state.deprecated_modules + analysis_result.current_state.deprecated_syntax,
        recommendations=analysis_result.recommendations.key_considerations,
        correlation_id=analysis_result.correlation_id
    )

# Validation schemas for API endpoints

analysis_request_example = {
    "content": """---
- hosts: webservers
  sudo: yes
  tasks:
    - name: Install apache
      yum:
        name: httpd
        state: present
    - name: Start apache
      service:
        name: httpd
        state: started
""",
    "filename": "webserver.yml"
}

analysis_response_example = {
    "success": True,
    "analysis_type": "ansible_upgrade_assessment",
    "filename": "webserver.yml",
    "react_reasoning": {
        "think": "This appears to be legacy Ansible 2.x content with deprecated syntax",
        "act": "Identified sudo usage, non-FQCN modules, and missing collections",
        "observe": "Analysis complete with medium complexity assessment"
    },
    "current_state": {
        "estimated_version": "2.9 or older",
        "deprecated_modules": ["yum", "service"],
        "deprecated_syntax": ["sudo"],
        "has_collections_block": False,
        "complexity_indicators": ["deprecated_modules", "legacy_syntax"]
    },
    "upgrade_requirements": {
        "fqcn_conversions_needed": ["yum", "service"],
        "syntax_modernizations_needed": ["sudo"],
        "collections_to_add": ["ansible.builtin"],
        "structural_changes_needed": ["add_collections_block", "update_become_syntax"]
    },
    "complexity_assessment": {
        "level": "MEDIUM",
        "factors": ["deprecated_modules", "syntax_updates"],
        "estimated_effort_hours": 4.0,
        "risk_level": "LOW"
    },
    "recommendations": {
        "upgrade_priority": "MEDIUM",
        "upgrade_approach": "INCREMENTAL",
        "key_considerations": ["Test after each change", "Validate functionality"],
        "ansible_equivalent_approach": "Modern FQCN with collections block"
    },
    "detailed_analysis": "This Ansible playbook represents legacy 2.x era content requiring modernization. The playbook uses deprecated sudo syntax instead of modern become, non-FQCN module names (yum, service), and lacks a collections block. The upgrade complexity is moderate, involving systematic FQCN conversion, become syntax updates, and collections block addition. The functional logic is straightforward - web server installation and startup - making this a good candidate for incremental modernization with low risk.",
    "transformation_plan": {
        "step_1": "Replace sudo with become: true",
        "step_2": "Add collections block with ansible.builtin",
        "step_3": "Convert modules to FQCN format",
        "step_4": "Test and validate functionality"
    }
}