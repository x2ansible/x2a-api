# agents/bladelogic_analysis/response_models.py

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class BladeLogicVersionRequirements(BaseModel):
    min_bladelogic_version: Optional[str] = None
    min_nsh_version: Optional[str] = None
    migration_effort: Optional[str] = None  # LOW, MEDIUM, HIGH
    estimated_hours: Optional[float] = None
    deprecated_features: List[str] = Field(default_factory=list)

class BladeLogicDependencies(BaseModel):
    is_composite: Optional[bool] = None  # Similar to wrapper cookbooks
    composite_jobs: List[str] = Field(default_factory=list)  # Jobs that include other jobs
    package_dependencies: List[str] = Field(default_factory=list)
    policy_dependencies: List[str] = Field(default_factory=list)
    external_scripts: List[str] = Field(default_factory=list)
    circular_risk: Optional[str] = None

class BladeLogicFunctionality(BaseModel):
    primary_purpose: Optional[str] = None
    automation_type: Optional[str] = None  # COMPLIANCE, PATCHING, DEPLOYMENT, CONFIGURATION
    target_platforms: List[str] = Field(default_factory=list)  # Windows, Linux, AIX, etc.
    managed_services: List[str] = Field(default_factory=list)
    managed_packages: List[str] = Field(default_factory=list)
    managed_files: List[str] = Field(default_factory=list)
    compliance_policies: List[str] = Field(default_factory=list)
    reusability: Optional[str] = None
    customization_points: List[str] = Field(default_factory=list)

class BladeLogicRecommendations(BaseModel):
    consolidation_action: Optional[str] = None  # REUSE, EXTEND, RECREATE, MODERNIZE
    rationale: Optional[str] = None
    migration_priority: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    ansible_equivalent: Optional[str] = None  # Suggested Ansible approach

class BladeLogicAnalysisMetadata(BaseModel):
    analyzed_at: str
    agent_version: Optional[str] = "1.0.0"
    correlation_id: Optional[str] = None

class BladeLogicAnalysisResponse(BaseModel):
    success: bool = True
    object_name: str  # Job/Package/Policy name
    object_type: str  # JOB, PACKAGE, POLICY, SCRIPT
    version_requirements: BladeLogicVersionRequirements
    dependencies: BladeLogicDependencies
    functionality: BladeLogicFunctionality
    recommendations: BladeLogicRecommendations
    metadata: BladeLogicAnalysisMetadata
    
    # Additional analysis fields
    detailed_analysis: Optional[str] = None
    key_operations: List[str] = Field(default_factory=list)
    automation_details: Optional[str] = None
    complexity_level: Optional[str] = None
    convertible: Optional[bool] = None
    conversion_notes: Optional[str] = None
    confidence_source: Optional[str] = "ai_semantic"