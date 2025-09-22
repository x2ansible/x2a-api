#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Neo4j Storage Tools for Infrastructure Analysis

Production-ready tools for storing infrastructure analysis results in Neo4j
with intelligent deduplication and relationship management.
"""

import hashlib
import json
from datetime import datetime, timezone
from ....state_helpers import generate_analysis_id
from typing import Dict, Any, Optional, List
from langchain_core.tools import tool
from neo4j import GraphDatabase

from ....response_models import Neo4jStorageResult, InfrastructureAnalysisStorage


def _load_neo4j_config() -> Dict[str, Any]:
    """Load Neo4j configuration from config.yaml"""
    import yaml
    from pathlib import Path
    
    config_path = Path(__file__).parent.parent.parent.parent.parent / "config.yaml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config.get("neo4j", {})


def _create_content_hash(content: str) -> str:
    """Create SHA256 hash for deduplication"""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _create_neo4j_driver():
    """Create Neo4j driver using configuration"""
    config = _load_neo4j_config()
    
    uri = config.get("uri", "neo4j://localhost:7687")
    username = config.get("username", "neo4j")
    password = config.get("password", "password")
    
    return GraphDatabase.driver(uri, auth=(username, password))


@tool
def check_duplicate_analysis(code_hash: str, content_hash: str) -> Dict[str, Any]:
    """
    Check for duplicate analysis based on code and content hashes.
    
    Args:
        code_hash: SHA256 hash of the original infrastructure code
        content_hash: SHA256 hash of the analysis content
        
    Returns:
        Dictionary with duplicate detection results
    """
    try:
        driver = _create_neo4j_driver()
        
        with driver.session() as session:
            # Check for existing analysis with same code hash
            result = session.run("""
                MATCH (a:InfrastructureAnalysis {code_hash: $code_hash})
                RETURN a.id as analysis_id, a.content_hash as existing_content_hash,
                       a.platform as platform, a.analysis_timestamp as timestamp
                ORDER BY a.analysis_timestamp DESC
                LIMIT 1
            """, code_hash=code_hash)
            
            record = result.single()
            
            if record:
                existing_content_hash = record["existing_content_hash"]
                if existing_content_hash == content_hash:
                    # Exact duplicate found
                    return {
                        "duplicate_found": True,
                        "duplicate_type": "exact",
                        "existing_analysis_id": record["analysis_id"],
                        "existing_platform": record["platform"],
                        "existing_timestamp": record["timestamp"],
                        "recommendation": "use_existing"
                    }
                else:
                    # Same code, different analysis (possible updated analysis)
                    return {
                        "duplicate_found": True,
                        "duplicate_type": "code_only",
                        "existing_analysis_id": record["analysis_id"],
                        "existing_platform": record["platform"],
                        "existing_timestamp": record["timestamp"],
                        "recommendation": "update_existing"
                    }
            
            # No duplicate found
            return {
                "duplicate_found": False,
                "duplicate_type": "none",
                "recommendation": "create_new"
            }
            
    except Exception as e:
        return {
            "duplicate_found": False,
            "error": str(e),
            "recommendation": "create_new"
        }
    finally:
        driver.close()


@tool
def store_infrastructure_analysis(analysis_data: Dict[str, Any]) -> Neo4jStorageResult:
    """
    Store complete infrastructure analysis in Neo4j with deduplication.
    
    Creates nodes for:
    - InfrastructureAnalysis (main analysis results)
    - Specification (natural language spec)
    - Platform (detected platform info)
    - Resources (individual infrastructure resources)
    
    Args:
        analysis_data: Complete analysis data including facts, specs, and metadata
        
    Returns:
        Neo4jStorageResult with storage operation details
    """
    try:
        # Parse and validate input data
        analysis = InfrastructureAnalysisStorage(**analysis_data)
        
        # Create content hashes for deduplication
        content_for_hash = json.dumps({
            "structured_analysis": analysis.structured_analysis,
            "extracted_facts": analysis.extracted_facts,
            "natural_specification": analysis.natural_specification
        }, sort_keys=True)
        content_hash = _create_content_hash(content_for_hash)
        
        # Check for duplicates
        duplicate_check = check_duplicate_analysis.invoke({"code_hash": analysis.code_hash, "content_hash": content_hash})
        
        storage_timestamp = datetime.now(timezone.utc).isoformat()
        
        if duplicate_check.get("duplicate_found") and duplicate_check.get("duplicate_type") == "exact":
            # Exact duplicate - return existing IDs
            return Neo4jStorageResult(
                storage_successful=True,
                analysis_node_id=duplicate_check["existing_analysis_id"],
                spec_node_id=f"{duplicate_check['existing_analysis_id']}_spec",
                content_hash=content_hash,
                duplicate_detected=True,
                existing_analysis_id=duplicate_check["existing_analysis_id"],
                deduplication_method="exact_content_match",
                storage_timestamp=storage_timestamp
            )
        
        # Create new storage
        driver = _create_neo4j_driver()
        analysis_id = generate_analysis_id()
        spec_id = f"{analysis_id}_spec"
        relationships_created = 0
        
        with driver.session() as session:
            # Create main analysis node
            session.run("""
                CREATE (a:InfrastructureAnalysis {
                    id: $analysis_id,
                    platform: $platform,
                    complexity_score: $complexity_score,
                    confidence_score: $confidence_score,
                    analysis_timestamp: $analysis_timestamp,
                    storage_timestamp: $storage_timestamp,
                    code_hash: $code_hash,
                    content_hash: $content_hash,
                    original_code: $original_code,
                    file_names: $file_names,
                    structured_analysis: $structured_analysis,
                    extracted_facts: $extracted_facts,
                    parsing_errors: $parsing_errors,
                    warnings: $warnings
                })
            """, 
                analysis_id=analysis_id,
                platform=analysis.platform,
                complexity_score=analysis.complexity_score,
                confidence_score=analysis.confidence_score,
                analysis_timestamp=analysis.analysis_timestamp,
                storage_timestamp=storage_timestamp,
                code_hash=analysis.code_hash,
                content_hash=content_hash,
                original_code=analysis.original_code[:10000],  # Limit size
                file_names=analysis.file_names,
                structured_analysis=json.dumps(analysis.structured_analysis),
                extracted_facts=json.dumps(analysis.extracted_facts),
                parsing_errors=analysis.parsing_errors,
                warnings=analysis.warnings
            )
            
            # Create specification node
            session.run("""
                CREATE (s:InfrastructureSpecification {
                    id: $spec_id,
                    analysis_id: $analysis_id,
                    platform: $platform,
                    content: $content,
                    word_count: $word_count,
                    creation_timestamp: $storage_timestamp,
                    content_hash: $content_hash
                })
            """,
                spec_id=spec_id,
                analysis_id=analysis_id,
                platform=analysis.platform,
                content=analysis.natural_specification,
                word_count=len(analysis.natural_specification.split()),
                storage_timestamp=storage_timestamp,
                content_hash=content_hash
            )
            relationships_created += 1
            
            # Create relationship between analysis and specification
            session.run("""
                MATCH (a:InfrastructureAnalysis {id: $analysis_id})
                MATCH (s:InfrastructureSpecification {id: $spec_id})
                CREATE (a)-[:HAS_SPECIFICATION]->(s)
            """, analysis_id=analysis_id, spec_id=spec_id)
            relationships_created += 1
            
            # Create platform node if it doesn't exist
            session.run("""
                MERGE (p:Platform {name: $platform})
                ON CREATE SET p.created_timestamp = $storage_timestamp,
                             p.analysis_count = 1
                ON MATCH SET p.analysis_count = p.analysis_count + 1
            """, platform=analysis.platform, storage_timestamp=storage_timestamp)
            
            # Create relationship to platform
            session.run("""
                MATCH (a:InfrastructureAnalysis {id: $analysis_id})
                MATCH (p:Platform {name: $platform})
                CREATE (a)-[:TARGETS_PLATFORM]->(p)
            """, analysis_id=analysis_id, platform=analysis.platform)
            relationships_created += 1
            
            # Create resource nodes from extracted facts
            if isinstance(analysis.extracted_facts, dict):
                resources = analysis.extracted_facts.get("resources", {})
                if isinstance(resources, dict):
                    for resource_type, resource_list in resources.items():
                        if isinstance(resource_list, list):
                            for i, resource in enumerate(resource_list):
                                if isinstance(resource, dict):
                                    resource_id = f"{analysis_id}_resource_{resource_type}_{i}"
                                    session.run("""
                                        CREATE (r:InfrastructureResource {
                                            id: $resource_id,
                                            analysis_id: $analysis_id,
                                            resource_type: $resource_type,
                                            name: $name,
                                            properties: $properties,
                                            platform: $platform
                                        })
                                    """,
                                        resource_id=resource_id,
                                        analysis_id=analysis_id,
                                        resource_type=resource_type,
                                        name=resource.get("name", "unnamed"),
                                        properties=json.dumps(resource),
                                        platform=analysis.platform
                                    )
                                    
                                    # Link resource to analysis
                                    session.run("""
                                        MATCH (a:InfrastructureAnalysis {id: $analysis_id})
                                        MATCH (r:InfrastructureResource {id: $resource_id})
                                        CREATE (a)-[:CONTAINS_RESOURCE]->(r)
                                    """, analysis_id=analysis_id, resource_id=resource_id)
                                    relationships_created += 1
        
        driver.close()
        
        return Neo4jStorageResult(
            storage_successful=True,
            analysis_node_id=analysis_id,
            spec_node_id=spec_id,
            content_hash=content_hash,
            duplicate_detected=False,
            relationships_created=relationships_created,
            deduplication_method="content_hash",
            storage_timestamp=storage_timestamp
        )
        
    except Exception as e:
        return Neo4jStorageResult(
            storage_successful=False,
            content_hash=content_hash if 'content_hash' in locals() else "",
            duplicate_detected=False,
            relationships_created=0,
            deduplication_method="content_hash",
            storage_timestamp=datetime.now(timezone.utc).isoformat(),
            error_details=str(e)
        )


@tool
def create_analysis_relationships(analysis_id: str, related_patterns: List[str] = None) -> Dict[str, Any]:
    """
    Create relationships between stored analysis and existing automation patterns.
    
    Args:
        analysis_id: ID of the stored infrastructure analysis
        related_patterns: List of automation pattern IDs to link
        
    Returns:
        Dictionary with relationship creation results
    """
    try:
        driver = _create_neo4j_driver()
        relationships_created = 0
        
        with driver.session() as session:
            # Link to automation patterns if provided
            if related_patterns:
                for pattern_id in related_patterns:
                    session.run("""
                        MATCH (a:InfrastructureAnalysis {id: $analysis_id})
                        MATCH (p:AutomationPattern {id: $pattern_id})
                        CREATE (a)-[:RELATES_TO_PATTERN]->(p)
                    """, analysis_id=analysis_id, pattern_id=pattern_id)
                    relationships_created += 1
            
            # Create similarity relationships with other analyses of same platform
            result = session.run("""
                MATCH (a1:InfrastructureAnalysis {id: $analysis_id})
                MATCH (a2:InfrastructureAnalysis)
                WHERE a1.platform = a2.platform 
                  AND a1.id <> a2.id
                  AND NOT EXISTS((a1)-[:SIMILAR_TO]-(a2))
                WITH a1, a2, 
                     CASE 
                       WHEN abs(a1.complexity_score - a2.complexity_score) < 0.2 THEN 0.8
                       WHEN abs(a1.complexity_score - a2.complexity_score) < 0.4 THEN 0.6
                       ELSE 0.4
                     END as similarity_score
                WHERE similarity_score > 0.5
                CREATE (a1)-[:SIMILAR_TO {score: similarity_score}]->(a2)
                RETURN count(*) as relationships_created
            """, analysis_id=analysis_id)
            
            similarity_relationships = result.single()["relationships_created"]
            relationships_created += similarity_relationships
        
        driver.close()
        
        return {
            "success": True,
            "relationships_created": relationships_created,
            "pattern_links": len(related_patterns) if related_patterns else 0,
            "similarity_links": similarity_relationships
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "relationships_created": 0
        }
