# agents/chef_analysis/response_models.py

from typing import List, Optional
from pydantic import BaseModel, Field

class VersionRequirements(BaseModel):
    min_chef_version: Optional[str] = None
    min_ruby_version: Optional[str] = None
    migration_effort: Optional[str] = None
    estimated_hours: Optional[float] = None
    deprecated_features: List[str] = Field(default_factory=list)

class Dependencies(BaseModel):
    is_wrapper: Optional[bool] = None
    wrapped_cookbooks: List[str] = Field(default_factory=list)
    direct_deps: List[str] = Field(default_factory=list)
    runtime_deps: List[str] = Field(default_factory=list)
    circular_risk: Optional[str] = None

class Functionality(BaseModel):
    primary_purpose: Optional[str] = None
    services: List[str] = Field(default_factory=list)
    packages: List[str] = Field(default_factory=list)
    files_managed: List[str] = Field(default_factory=list)
    reusability: Optional[str] = None
    customization_points: List[str] = Field(default_factory=list)

class Recommendations(BaseModel):
    consolidation_action: Optional[str] = None
    rationale: Optional[str] = None
    migration_priority: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)

class AnalysisMetadata(BaseModel):
    analyzed_at: str
    agent_version: Optional[str]
    correlation_id: Optional[str] = None

class CookbookAnalysisResponse(BaseModel):
    success: bool = True
    cookbook_name: str
    version_requirements: VersionRequirements
    dependencies: Dependencies
    functionality: Functionality
    recommendations: Recommendations
    metadata: AnalysisMetadata
    # Optional semantic/classifier fields:
    detailed_analysis: Optional[str] = None
    key_operations: List[str] = Field(default_factory=list)
    configuration_details: Optional[str] = None
    complexity_level: Optional[str] = None
    convertible: Optional[bool] = None
    conversion_notes: Optional[str] = None
    confidence_source: Optional[str] = "ai_semantic"
