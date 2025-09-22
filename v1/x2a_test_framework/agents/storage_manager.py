"""
x2a Storage Manager Agent Test Patterns

Specialized test patterns and assertions for the x2a Storage Manager Agent.
Provides comprehensive testing utilities for Neo4j storage operations,
data persistence validation, deduplication testing, and relationship management.

Key Features:
- Neo4j storage operation testing
- Infrastructure analysis persistence validation
- Intelligent deduplication testing
- Data integrity and relationship management testing
- Storage performance and reliability testing
- Content hash validation testing
- ReAct agent storage behavior validation
"""

import logging
from typing import Dict, Any, List, Optional, Union
import hashlib
import json

logger = logging.getLogger("x2a_test_framework.agents.storage_manager")


class StorageManagerTestPatterns:
    """
    Specialized test patterns for x2a Storage Manager Agent.
    
    Provides comprehensive validation patterns for Neo4j storage operations,
    data persistence, deduplication, and relationship management.
    """
    
    @staticmethod
    def assert_successful_storage_operation(
        result: Dict[str, Any],
        expected_operation: str = "store",
        min_data_size: int = 100
    ):
        """
        Assert that Neo4j storage operation completed successfully.
        
        Args:
            result: Storage operation result to validate
            expected_operation: Expected storage operation type
            min_data_size: Minimum expected data size stored
        """
        assert isinstance(result, dict), f"Result must be a dictionary, got {type(result)}"
        
        # Check for storage success indicator
        success_fields = ['success', 'storage_success', 'neo4j_success']
        storage_success = None
        for field in success_fields:
            if field in result:
                storage_success = result[field]
                break
        
        assert storage_success is True, f"Storage operation failed: {result.get('error', 'Unknown error')}"
        
        # Check for storage ID or confirmation
        storage_id_fields = ['analysis_id', 'storage_id', 'neo4j_id', 'node_id']
        storage_id = None
        for field in storage_id_fields:
            if field in result:
                storage_id = result[field]
                break
        
        assert storage_id is not None, f"No storage ID found. Available keys: {list(result.keys())}"
        assert isinstance(storage_id, str) and storage_id.strip(), "Storage ID must be non-empty string"
        
        # Check for data size indicator
        data_size_fields = ['data_size', 'stored_bytes', 'content_length']
        data_size = None
        for field in data_size_fields:
            if field in result:
                data_size = result[field]
                break
        
        if data_size is not None:
            assert isinstance(data_size, (int, float)), f"Data size must be numeric, got {type(data_size)}"
            assert data_size >= min_data_size, f"Stored data too small: {data_size} < {min_data_size}"
        
        logger.info(f" Storage operation successful: {expected_operation}, ID={storage_id}, size={data_size}")
    
    @staticmethod
    def assert_valid_deduplication_handling(
        dedup_result: Dict[str, Any],
        input_hash: str,
        expected_duplicate_found: bool = False
    ):
        """
        Assert that deduplication logic works correctly.
        
        Args:
            dedup_result: Deduplication check result
            input_hash: Input content hash used for dedup check
            expected_duplicate_found: Whether duplicate should be found
        """
        assert isinstance(dedup_result, dict), f"Dedup result must be dict, got {type(dedup_result)}"
        assert isinstance(input_hash, str) and input_hash.strip(), "Input hash must be non-empty string"
        
        # Check for duplicate detection result
        duplicate_fields = ['duplicate_found', 'is_duplicate', 'exists']
        duplicate_found = None
        for field in duplicate_fields:
            if field in dedup_result:
                duplicate_found = dedup_result[field]
                break
        
        assert duplicate_found is not None, f"No duplicate detection result found. Available keys: {list(dedup_result.keys())}"
        assert isinstance(duplicate_found, bool), f"Duplicate found must be boolean, got {type(duplicate_found)}"
        assert duplicate_found == expected_duplicate_found, f"Duplicate detection mismatch: {duplicate_found} != {expected_duplicate_found}"
        
        # Check hash consistency
        result_hash_fields = ['code_hash', 'content_hash', 'input_hash']
        result_hash = None
        for field in result_hash_fields:
            if field in dedup_result:
                result_hash = dedup_result[field]
                break
        
        if result_hash is not None:
            assert result_hash == input_hash, f"Hash mismatch: {result_hash} != {input_hash}"
        
        # If duplicate found, check for existing analysis info
        if duplicate_found:
            existing_fields = ['existing_analysis', 'existing_id', 'previous_analysis']
            has_existing_info = any(field in dedup_result for field in existing_fields)
            assert has_existing_info, "Duplicate found but no existing analysis info provided"
        
        logger.info(f" Deduplication handling valid: duplicate={duplicate_found}, hash={input_hash[:8]}...")
    
    @staticmethod
    def assert_comprehensive_data_persistence(
        stored_data: Dict[str, Any],
        original_analysis: Dict[str, Any],
        required_fields: List[str] = None
    ):
        """
        Assert that data persistence is comprehensive and accurate.
        
        Args:
            stored_data: Data that was stored in Neo4j
            original_analysis: Original analysis data
            required_fields: Required fields that must be persisted
        """
        assert isinstance(stored_data, dict), f"Stored data must be dict, got {type(stored_data)}"
        assert isinstance(original_analysis, dict), f"Original analysis must be dict, got {type(original_analysis)}"
        
        # Check for required fields in stored data
        default_required_fields = [
            'platform', 'analysis_timestamp', 'extracted_facts', 'structured_analysis'
        ]
        fields_to_check = required_fields or default_required_fields
        
        for field in fields_to_check:
            field_found = field in stored_data
            if not field_found:
                # Allow for field variations
                field_variations = [f'{field}s', f'{field}_data', f'{field}_result']
                field_found = any(variation in stored_data for variation in field_variations)
            
            assert field_found, f"Required field '{field}' not found in stored data. Available: {list(stored_data.keys())}"
        
        # Check data consistency between original and stored
        consistency_checks = 0
        total_checks = 0
        
        for key, original_value in original_analysis.items():
            total_checks += 1
            if key in stored_data:
                stored_value = stored_data[key]
                # Simple consistency check (can be enhanced based on data types)
                if str(original_value) == str(stored_value):
                    consistency_checks += 1
            elif any(variation in stored_data for variation in [f'{key}s', f'{key}_data']):
                consistency_checks += 1  # Found in variation form
        
        if total_checks > 0:
            consistency_ratio = consistency_checks / total_checks
            assert consistency_ratio >= 0.7, f"Data consistency too low: {consistency_ratio:.2f} < 0.7"
        
        logger.info(f" Data persistence comprehensive: {len(stored_data)} fields, {consistency_ratio:.2f if total_checks > 0 else 'N/A'} consistency")
    
    @staticmethod
    def assert_neo4j_relationship_creation(
        relationship_result: Dict[str, Any],
        analysis_id: str,
        expected_relationship_types: List[str] = None
    ):
        """
        Assert that Neo4j relationships are created correctly.
        
        Args:
            relationship_result: Result from relationship creation
            analysis_id: Analysis ID for relationship validation
            expected_relationship_types: Expected types of relationships
        """
        assert isinstance(relationship_result, dict), f"Relationship result must be dict, got {type(relationship_result)}"
        assert isinstance(analysis_id, str) and analysis_id.strip(), "Analysis ID must be non-empty string"
        
        # Check for relationship creation success
        success_fields = ['success', 'relationships_created', 'creation_success']
        relationships_success = None
        for field in success_fields:
            if field in relationship_result:
                relationships_success = relationship_result[field]
                break
        
        assert relationships_success is True, f"Relationship creation failed: {relationship_result.get('error', 'Unknown error')}"
        
        # Check for relationship details
        relationship_fields = ['relationships', 'created_relationships', 'relationship_ids']
        relationships = None
        for field in relationship_fields:
            if field in relationship_result:
                relationships = relationship_result[field]
                break
        
        if relationships is not None:
            if isinstance(relationships, list):
                assert len(relationships) > 0, "No relationships created"
            elif isinstance(relationships, dict):
                assert len(relationships) > 0, "No relationship data found"
        
        # Check for expected relationship types
        if expected_relationship_types and relationships:
            relationship_text = str(relationships).lower()
            for rel_type in expected_relationship_types:
                rel_found = rel_type.lower() in relationship_text
                assert rel_found, f"Expected relationship type '{rel_type}' not found in: {relationship_text[:100]}..."
        
        logger.info(f" Neo4j relationships created: analysis_id={analysis_id}, types={expected_relationship_types}")
    
    @staticmethod
    def assert_storage_performance_standards(
        processing_time: float,
        data_size: int,
        max_time_per_kb: float = 0.1
    ):
        """
        Assert that storage operations meet performance standards.
        
        Args:
            processing_time: Actual processing time in seconds
            data_size: Size of data being stored
            max_time_per_kb: Maximum time per KB of data
        """
        assert isinstance(processing_time, (int, float)), f"Processing time must be numeric, got {type(processing_time)}"
        assert processing_time > 0, f"Processing time must be positive, got {processing_time}"
        assert isinstance(data_size, (int, float)), f"Data size must be numeric, got {type(data_size)}"
        
        # Calculate expected time based on data size
        data_kb = max(data_size / 1024, 1)  # At least 1KB for calculation
        max_expected_time = data_kb * max_time_per_kb
        
        # Add base time for Neo4j connection overhead
        max_expected_time += 2.0  # 2 second base time
        
        assert processing_time <= max_expected_time, f"Storage too slow: {processing_time:.2f}s > {max_expected_time:.2f}s for {data_kb:.1f}KB"
        
        logger.info(f" Storage performance good: {processing_time:.2f}s for {data_kb:.1f}KB")
    
    @staticmethod
    def assert_content_hash_validation(
        hash_result: str,
        input_content: str,
        expected_hash_algorithm: str = "sha256"
    ):
        """
        Assert that content hash generation is correct and consistent.
        
        Args:
            hash_result: Generated hash from storage system
            input_content: Original content that was hashed
            expected_hash_algorithm: Expected hashing algorithm
        """
        assert isinstance(hash_result, str) and hash_result.strip(), "Hash result must be non-empty string"
        assert isinstance(input_content, str), f"Input content must be string, got {type(input_content)}"
        
        # Validate hash format based on algorithm
        if expected_hash_algorithm == "sha256":
            assert len(hash_result) == 64, f"SHA256 hash should be 64 characters, got {len(hash_result)}"
            assert all(c in '0123456789abcdef' for c in hash_result.lower()), "SHA256 hash should be hexadecimal"
        elif expected_hash_algorithm == "md5":
            assert len(hash_result) == 32, f"MD5 hash should be 32 characters, got {len(hash_result)}"
            assert all(c in '0123456789abcdef' for c in hash_result.lower()), "MD5 hash should be hexadecimal"
        
        # Verify hash consistency by recreating
        if expected_hash_algorithm == "sha256":
            expected_hash = hashlib.sha256(input_content.encode()).hexdigest()
        elif expected_hash_algorithm == "md5":
            expected_hash = hashlib.md5(input_content.encode()).hexdigest()
        else:
            expected_hash = None  # Can't verify unknown algorithms
        
        if expected_hash:
            assert hash_result.lower() == expected_hash.lower(), f"Hash mismatch: {hash_result} != {expected_hash}"
        
        logger.info(f" Content hash valid: {expected_hash_algorithm} hash verified")
    
    @staticmethod
    def assert_data_integrity_preservation(
        retrieved_data: Dict[str, Any],
        original_data: Dict[str, Any],
        critical_fields: List[str] = None
    ):
        """
        Assert that data integrity is preserved during storage and retrieval.
        
        Args:
            retrieved_data: Data retrieved from Neo4j storage
            original_data: Original data before storage
            critical_fields: Critical fields that must match exactly
        """
        assert isinstance(retrieved_data, dict), f"Retrieved data must be dict, got {type(retrieved_data)}"
        assert isinstance(original_data, dict), f"Original data must be dict, got {type(original_data)}"
        
        # Check critical fields for exact matches
        default_critical_fields = ['platform', 'code_hash', 'complexity_score']
        fields_to_check = critical_fields or default_critical_fields
        
        for field in fields_to_check:
            if field in original_data:
                original_value = original_data[field]
                retrieved_value = retrieved_data.get(field)
                
                if retrieved_value is not None:
                    # Type-aware comparison
                    if isinstance(original_value, (int, float)) and isinstance(retrieved_value, (int, float)):
                        assert abs(original_value - retrieved_value) < 0.001, f"Numeric field {field} mismatch: {original_value} != {retrieved_value}"
                    else:
                        assert str(original_value) == str(retrieved_value), f"Field {field} mismatch: {original_value} != {retrieved_value}"
        
        # Check overall data structure preservation
        original_keys = set(original_data.keys())
        retrieved_keys = set(retrieved_data.keys())
        
        # Allow for some key variations in storage
        key_preservation_ratio = len(original_keys.intersection(retrieved_keys)) / len(original_keys) if original_keys else 1.0
        assert key_preservation_ratio >= 0.6, f"Too many keys lost during storage: {key_preservation_ratio:.2f} < 0.6"
        
        logger.info(f" Data integrity preserved: {len(fields_to_check)} critical fields, {key_preservation_ratio:.2f} key preservation")
    
    @staticmethod
    def assert_react_agent_storage_behavior(
        agent_output: Dict[str, Any],
        expected_tool_usage: List[str] = None,
        expected_storage_actions: int = 1
    ):
        """
        Assert that ReAct agent shows proper storage management behavior.
        
        Args:
            agent_output: Output from storage manager ReAct agent
            expected_tool_usage: Expected storage tools to be used
            expected_storage_actions: Expected number of storage actions
        """
        assert isinstance(agent_output, dict), f"Agent output must be dict, got {type(agent_output)}"
        
        messages = agent_output.get('messages', [])
        assert isinstance(messages, list), "Agent output should contain messages list"
        assert len(messages) > 0, "Agent should produce at least one message"
        
        # Check for storage tool usage
        default_expected_tools = ['store_infrastructure_analysis', 'check_duplicate_analysis']
        tools_to_check = expected_tool_usage or default_expected_tools
        
        tools_used = []
        storage_actions = 0
        
        for message in messages:
            tool_calls = getattr(message, 'tool_calls', [])
            if tool_calls:
                for tool_call in tool_calls:
                    tool_name = tool_call.get('name') if isinstance(tool_call, dict) else getattr(tool_call, 'name', None)
                    if tool_name:
                        tools_used.append(tool_name)
                        if 'store' in tool_name.lower() or 'save' in tool_name.lower():
                            storage_actions += 1
        
        # Validate expected tools were used
        for expected_tool in tools_to_check:
            tool_found = any(expected_tool in tool for tool in tools_used)
            assert tool_found, f"Expected storage tool '{expected_tool}' not used. Used: {tools_used}"
        
        # Validate storage actions count
        assert storage_actions >= expected_storage_actions, f"Too few storage actions: {storage_actions} < {expected_storage_actions}"
        
        # Check for storage-related reasoning
        storage_reasoning = 0
        for message in messages:
            message_content = str(getattr(message, 'content', message)).lower()
            storage_keywords = ['store', 'save', 'persist', 'neo4j', 'database']
            if any(keyword in message_content for keyword in storage_keywords):
                storage_reasoning += 1
        
        assert storage_reasoning >= 1, f"Insufficient storage reasoning: {storage_reasoning} < 1"
        
        logger.info(f" ReAct storage behavior valid: {len(tools_used)} tools, {storage_actions} actions, {storage_reasoning} reasoning")


class StorageManagerTestHelpers:
    """Helper utilities for storage manager testing."""
    
    @staticmethod
    def create_storage_test_scenario(
        platform: str,
        data_complexity: str = "medium",
        include_relationships: bool = True
    ) -> Dict[str, Any]:
        """Create a comprehensive storage test scenario."""
        
        # Platform-specific test data
        platform_test_data = {
            'chef': {
                'extracted_facts': {
                    'cookbook_name': 'test_cookbook',
                    'recipes': ['default', 'install'],
                    'packages': ['nginx', 'ssl-cert'],
                    'services': ['nginx']
                },
                'structured_analysis': {
                    'complexity_score': 65,
                    'resource_count': 8,
                    'dependency_complexity': 'medium'
                }
            },
            'terraform': {
                'extracted_facts': {
                    'resources': ['aws_instance', 'aws_security_group'],
                    'providers': ['aws'],
                    'variables': ['instance_type', 'region']
                },
                'structured_analysis': {
                    'complexity_score': 70,
                    'resource_count': 5,
                    'dependency_complexity': 'medium'
                }
            }
        }
        
        base_data = platform_test_data.get(platform, platform_test_data['chef'])
        
        test_scenario = {
            'platform': platform,
            'analysis_data': {
                'platform': platform,
                'analysis_timestamp': '2024-01-01T00:00:00Z',
                'original_code': f'# Test {platform} code\npackage "nginx" do\n  action :install\nend',
                'code_hash': hashlib.sha256(f'test_{platform}_code'.encode()).hexdigest(),
                'confidence_score': 0.85,
                **base_data
            },
            'expected_storage': {
                'success': True,
                'deduplication_check': True,
                'relationships_created': include_relationships
            },
            'performance_expectations': {
                'max_storage_time': 5.0,
                'max_time_per_kb': 0.1
            }
        }
        
        return test_scenario
    
    @staticmethod
    def generate_test_content_hash(content: str, algorithm: str = "sha256") -> str:
        """Generate content hash for testing purposes."""
        if algorithm == "sha256":
            return hashlib.sha256(content.encode()).hexdigest()
        elif algorithm == "md5":
            return hashlib.md5(content.encode()).hexdigest()
        else:
            raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    @staticmethod
    def extract_storage_metrics(result: Dict[str, Any]) -> Dict[str, Any]:
        """Extract storage operation metrics from result."""
        metrics = {
            'storage_complete': False,
            'storage_id': None,
            'data_size': 0,
            'deduplication_performed': False,
            'relationships_created': False,
            'processing_time': 0.0,
            'hash_verified': False
        }
        
        # Extract basic storage info
        metrics['storage_complete'] = result.get('success', False)
        metrics['storage_id'] = result.get('analysis_id') or result.get('storage_id')
        metrics['data_size'] = result.get('data_size', 0)
        metrics['processing_time'] = result.get('processing_time', 0.0)
        
        # Extract deduplication info
        dedup_fields = ['duplicate_check_performed', 'deduplication_performed']
        metrics['deduplication_performed'] = any(result.get(field, False) for field in dedup_fields)
        
        # Extract relationship info
        rel_fields = ['relationships_created', 'relationship_success']
        metrics['relationships_created'] = any(result.get(field, False) for field in rel_fields)
        
        # Extract hash verification info
        hash_fields = ['hash_verified', 'content_hash', 'code_hash']
        metrics['hash_verified'] = any(field in result for field in hash_fields)
        
        return metrics
    
    @staticmethod
    def create_mock_neo4j_response(
        operation: str,
        success: bool = True,
        analysis_id: str = None
    ) -> Dict[str, Any]:
        """Create a mock Neo4j response for testing."""
        
        base_response = {
            'success': success,
            'operation': operation,
            'timestamp': '2024-01-01T00:00:00Z'
        }
        
        if operation == "store":
            base_response.update({
                'analysis_id': analysis_id or 'test_analysis_123',
                'nodes_created': 1,
                'properties_set': 8,
                'data_size': 1024
            })
        elif operation == "dedup_check":
            base_response.update({
                'duplicate_found': not success,  # If success=True, no duplicate found
                'existing_analysis': None if success else 'existing_analysis_456'
            })
        elif operation == "relationships":
            base_response.update({
                'relationships_created': 3 if success else 0,
                'relationship_types': ['DEPENDS_ON', 'CONTAINS', 'RELATED_TO'] if success else []
            })
        
        if not success:
            base_response['error'] = f"Mock {operation} operation failed"
        
        return base_response
    
    @staticmethod
    def validate_storage_data_structure(stored_data: Dict[str, Any]) -> Dict[str, bool]:
        """Validate the structure of data prepared for storage."""
        
        structure_checks = {
            'has_platform': 'platform' in stored_data,
            'has_timestamp': any(key in stored_data for key in ['analysis_timestamp', 'timestamp']),
            'has_code_hash': any(key in stored_data for key in ['code_hash', 'content_hash']),
            'has_extracted_facts': 'extracted_facts' in stored_data,
            'has_structured_analysis': 'structured_analysis' in stored_data,
            'has_confidence_score': any(key in stored_data for key in ['confidence_score', 'confidence']),
            'has_original_code': 'original_code' in stored_data
        }
        
        return structure_checks
