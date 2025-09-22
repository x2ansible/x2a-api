"""
Structured Response Models for Infrastructure Analysis

Pydantic models for ensuring structured output from each agent.
These models enforce consistent, parseable results.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class PlatformDetectionResult(BaseModel):
    """Structured output for platform detection"""
    
    detected_platform: str = Field(description="Primary platform detected (chef, puppet, terraform, etc.)")
    confidence: float = Field(description="Confidence score 0.0-1.0", ge=0.0, le=1.0)
    evidence: List[str] = Field(description="Evidence that supports the detection")
    secondary_platforms: List[str] = Field(default_factory=list, description="Other platforms detected")
    platform_versions: Dict[str, str] = Field(default_factory=dict, description="Platform versions if detected")
    analysis_notes: str = Field(default="", description="Additional analysis notes")


class ChefExtractionResult(BaseModel):
    """Structured output for Chef cookbook extraction"""
    
    cookbook_metadata: Dict[str, Any] = Field(default_factory=dict, description="Cookbook metadata (name, version, etc.)")
    resources: Dict[str, List[Dict[str, Any]]] = Field(default_factory=dict, description="Chef resources by type")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Cookbook attributes")
    dependencies: List[str] = Field(default_factory=list, description="Cookbook dependencies")
    recipes: List[str] = Field(default_factory=list, description="Recipe names")
    templates: List[str] = Field(default_factory=list, description="Template files")
    files: List[str] = Field(default_factory=list, description="Static files")
    complexity_score: float = Field(default=0.0, description="Complexity assessment 0.0-1.0")
    parsing_errors: List[str] = Field(default_factory=list, description="Any parsing errors encountered")


class StructuredAnalysisResult(BaseModel):
    """Structured output for infrastructure analysis"""
    
    infrastructure_type: str = Field(description="Type of infrastructure (web_server, database, etc.)")
    components: List[str] = Field(description="Main infrastructure components")
    dependencies: List[str] = Field(description="Component dependencies")
    security_considerations: List[str] = Field(default_factory=list, description="Security aspects")
    performance_considerations: List[str] = Field(default_factory=list, description="Performance aspects")
    maintenance_requirements: List[str] = Field(default_factory=list, description="Maintenance needs")
    complexity_assessment: str = Field(description="Overall complexity (low, medium, high)")
    migration_challenges: List[str] = Field(default_factory=list, description="Potential migration challenges")
    estimated_effort: str = Field(default="", description="Estimated migration effort")
    recommendations: List[str] = Field(default_factory=list, description="Recommendations")


class SpecificationResult(BaseModel):
    """Structured output for specification generation"""
    
    executive_summary: str = Field(description="High-level summary of the infrastructure")
    technical_details: Dict[str, Any] = Field(description="Technical implementation details")
    implementation_guidelines: List[str] = Field(description="Step-by-step implementation guide")
    acceptance_criteria: List[str] = Field(description="Success criteria for implementation")
    review_checklist: List[str] = Field(description="Review checklist items")
    testing_requirements: List[str] = Field(default_factory=list, description="Testing requirements")
    rollback_procedures: List[str] = Field(default_factory=list, description="Rollback procedures")
    estimated_timeline: str = Field(default="", description="Estimated implementation timeline")
    risk_assessment: List[str] = Field(default_factory=list, description="Implementation risks")


class StorageResult(BaseModel):
    """Structured output for storage operations"""
    
    storage_successful: bool = Field(description="Whether storage operation succeeded")
    neo4j_node_id: str = Field(default="", description="Neo4j node ID if created")
    duplicate_detected: bool = Field(default=False, description="Whether duplicate was detected")
    existing_node_id: str = Field(default="", description="Existing node ID if duplicate")
    storage_metadata: Dict[str, Any] = Field(default_factory=dict, description="Storage operation metadata")
    error_details: str = Field(default="", description="Error details if storage failed")
    deduplication_key: str = Field(default="", description="Key used for deduplication")


class SynthesisResult(BaseModel):
    """Structured output for final synthesis"""
    
    overall_assessment: str = Field(description="Overall infrastructure assessment")
    migration_strategy: str = Field(description="Recommended migration approach")
    key_findings: List[str] = Field(description="Key findings from analysis")
    priority_actions: List[str] = Field(description="Priority actions for migration")
    resource_requirements: Dict[str, Any] = Field(default_factory=dict, description="Required resources")
    timeline_estimate: str = Field(default="", description="Overall timeline estimate")
    success_metrics: List[str] = Field(default_factory=list, description="Success measurement criteria")
    next_steps: List[str] = Field(default_factory=list, description="Immediate next steps")


class Neo4jStorageResult(BaseModel):
    """Structured output for Neo4j storage operations"""
    
    storage_successful: bool = Field(description="Whether storage operation succeeded")
    analysis_node_id: str = Field(default="", description="Neo4j node ID for stored analysis")
    spec_node_id: str = Field(default="", description="Neo4j node ID for stored specification")
    content_hash: str = Field(description="SHA256 hash of content for deduplication")
    duplicate_detected: bool = Field(default=False, description="Whether duplicate content was detected")
    existing_analysis_id: str = Field(default="", description="Existing analysis node ID if duplicate")
    existing_spec_id: str = Field(default="", description="Existing spec node ID if duplicate")
    relationships_created: int = Field(default=0, description="Number of relationships created")
    deduplication_method: str = Field(default="content_hash", description="Method used for deduplication")
    storage_timestamp: str = Field(description="ISO timestamp of storage operation")
    error_details: str = Field(default="", description="Error details if storage failed")


class InfrastructureAnalysisStorage(BaseModel):
    """Complete infrastructure analysis for Neo4j storage"""
    
    # Metadata
    platform: str = Field(description="Detected infrastructure platform")
    complexity_score: float = Field(description="Complexity assessment 0.0-1.0")
    analysis_timestamp: str = Field(description="ISO timestamp of analysis")
    
    # Analysis Results
    structured_analysis: Dict[str, Any] = Field(description="Structured analysis results")
    extracted_facts: Dict[str, Any] = Field(description="Extracted infrastructure facts")
    natural_specification: str = Field(description="Natural language specification")
    
    # Source Information
    original_code: str = Field(description="Original infrastructure code analyzed")
    code_hash: str = Field(description="SHA256 hash of original code")
    file_names: List[str] = Field(default_factory=list, description="Source file names")
    
    # Quality Metrics
    confidence_score: float = Field(description="Overall confidence in analysis")
    parsing_errors: List[str] = Field(default_factory=list, description="Any parsing errors")
    warnings: List[str] = Field(default_factory=list, description="Analysis warnings")
