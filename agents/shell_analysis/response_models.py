from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ShellVersionRequirements(BaseModel):
    min_shell_version: Optional[str] = None
    shell_type: Optional[str] = None  # bash, zsh, sh, etc.
    migration_effort: Optional[str] = None  # LOW, MEDIUM, HIGH
    estimated_hours: Optional[float] = None
    deprecated_features: List[str] = Field(default_factory=list)

class ShellDependencies(BaseModel):
    system_packages: List[str] = Field(default_factory=list)
    external_commands: List[str] = Field(default_factory=list)
    file_dependencies: List[str] = Field(default_factory=list)
    service_dependencies: List[str] = Field(default_factory=list)
    circular_risk: Optional[str] = None

class ShellFunctionality(BaseModel):
    primary_purpose: Optional[str] = None
    script_type: Optional[str] = None  # DEPLOYMENT, CONFIGURATION, MONITORING, etc.
    target_platforms: List[str] = Field(default_factory=list)
    managed_services: List[str] = Field(default_factory=list)
    managed_packages: List[str] = Field(default_factory=list)
    configuration_files: List[str] = Field(default_factory=list)
    key_operations: List[str] = Field(default_factory=list)
    reusability: Optional[str] = None

class ShellRecommendations(BaseModel):
    conversion_action: Optional[str] = None  # REUSE, EXTEND, RECREATE, MODERNIZE
    rationale: Optional[str] = None
    migration_priority: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    ansible_equivalent: Optional[str] = None

class ShellAnalysisMetadata(BaseModel):
    analyzed_at: str
    agent_version: Optional[str] = "1.0.0"
    correlation_id: Optional[str] = None

class ShellAnalysisResponse(BaseModel):
    success: bool = True
    script_name: str
    script_type: str
    version_requirements: ShellVersionRequirements
    dependencies: ShellDependencies
    functionality: ShellFunctionality
    recommendations: ShellRecommendations
    metadata: ShellAnalysisMetadata
    detailed_analysis: Optional[str] = None
    complexity_level: Optional[str] = None
    convertible: Optional[bool] = None
    conversion_notes: Optional[str] = None
    confidence_source: Optional[str] = "ai_semantic"