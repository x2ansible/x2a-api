"""
x2a Test Configuration Management

Enterprise-grade configuration management for x2a test framework.
Provides centralized configuration for test environments, timeouts, thresholds,
and platform-specific settings.

Key Features:
- Environment-specific configuration (dev, test, prod)
- Platform-specific test data and thresholds
- Performance and timeout configuration
- Test data management and validation
- Configuration validation and defaults
- Enterprise logging and audit trails
"""

import os
import logging
from typing import Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("x2a_test_framework.config")


class TestEnvironment(Enum):
    """Test environment types for x2a testing."""
    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"
    CI_CD = "ci_cd"


class PerformanceProfile(Enum):
    """Performance profiles for different testing scenarios."""
    FAST = "fast"          # Quick tests, lower thresholds
    STANDARD = "standard"  # Normal testing thresholds
    THOROUGH = "thorough"  # Comprehensive testing, higher thresholds
    STRESS = "stress"      # Stress testing with very high thresholds


@dataclass
class PerformanceThresholds:
    """Performance thresholds for test validation."""
    max_execution_time: float = 30.0      # Maximum execution time in seconds
    max_memory_increase: float = 100.0    # Maximum memory increase in MB
    min_confidence: float = 0.5           # Minimum confidence threshold
    max_confidence: float = 1.0           # Maximum confidence threshold
    max_worker_assignments: int = 10      # Maximum worker assignments
    min_worker_assignments: int = 1       # Minimum worker assignments
    
    def __post_init__(self):
        """Validate thresholds after initialization."""
        if self.max_execution_time <= 0:
            raise ValueError("max_execution_time must be positive")
        if not 0 <= self.min_confidence <= self.max_confidence <= 1:
            raise ValueError("Confidence thresholds must be between 0 and 1")


@dataclass
class PlatformTestConfig:
    """Configuration for platform-specific testing."""
    platform_name: str
    test_code: str
    expected_complexity: str = "medium"
    min_confidence: float = 0.7
    specific_validations: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        """Validate platform configuration."""
        valid_complexities = ["low", "medium", "high"]
        if self.expected_complexity not in valid_complexities:
            raise ValueError(f"Invalid complexity: {self.expected_complexity}")


class X2ATestConfig:
    """
    Enterprise configuration manager for x2a test framework.
    
    Provides centralized configuration management with environment-specific
    settings, performance profiles, and platform configurations.
    """
    
    def __init__(self, environment: TestEnvironment = TestEnvironment.TEST):
        self.environment = environment
        self.performance_profile = PerformanceProfile.STANDARD
        self._load_configuration()
        
        logger.info(f"X2A Test Framework initialized for {environment.value} environment")
    
    def _load_configuration(self):
        """Load configuration based on environment."""
        self.timeouts = self._get_timeout_config()
        self.thresholds = self._get_performance_thresholds()
        self.platform_configs = self._get_platform_configs()
        self.test_data_config = self._get_test_data_config()
        self.logging_config = self._get_logging_config()
    
    def _get_timeout_config(self) -> Dict[str, float]:
        """Get timeout configuration based on environment."""
        base_timeouts = {
            "agent_creation": 10.0,
            "node_execution": 30.0,
            "workflow_execution": 300.0,
            "llm_response": 60.0,
            "tool_execution": 30.0
        }
        
        # Adjust timeouts based on environment
        multipliers = {
            TestEnvironment.DEVELOPMENT: 2.0,  # Slower for debugging
            TestEnvironment.TEST: 1.0,         # Standard timeouts
            TestEnvironment.STAGING: 1.0,      # Standard timeouts
            TestEnvironment.PRODUCTION: 0.5,   # Faster for production validation
            TestEnvironment.CI_CD: 0.8         # Slightly faster for CI/CD
        }
        
        multiplier = multipliers.get(self.environment, 1.0)
        return {key: value * multiplier for key, value in base_timeouts.items()}
    
    def _get_performance_thresholds(self) -> PerformanceThresholds:
        """Get performance thresholds based on profile."""
        profiles = {
            PerformanceProfile.FAST: PerformanceThresholds(
                max_execution_time=10.0,
                max_memory_increase=50.0,
                min_confidence=0.6
            ),
            PerformanceProfile.STANDARD: PerformanceThresholds(
                max_execution_time=30.0,
                max_memory_increase=100.0,
                min_confidence=0.5
            ),
            PerformanceProfile.THOROUGH: PerformanceThresholds(
                max_execution_time=120.0,
                max_memory_increase=200.0,
                min_confidence=0.3
            ),
            PerformanceProfile.STRESS: PerformanceThresholds(
                max_execution_time=600.0,
                max_memory_increase=500.0,
                min_confidence=0.1
            )
        }
        
        return profiles.get(self.performance_profile, profiles[PerformanceProfile.STANDARD])
    
    def _get_platform_configs(self) -> Dict[str, PlatformTestConfig]:
        """Get platform-specific test configurations."""
        return {
            "chef": PlatformTestConfig(
                platform_name="chef",
                test_code='''
# x2a Chef Test Configuration
cookbook_name = "x2a_nginx_test"
cookbook_version = "1.0.0"

recipe "default" do
  package "nginx" do
    action :install
  end
  
  service "nginx" do
    action [:enable, :start]
  end
  
  template "/etc/nginx/nginx.conf" do
    source "nginx.conf.erb"
    mode "0644"
    notifies :restart, "service[nginx]"
  end
end
                '''.strip(),
                expected_complexity="medium",
                min_confidence=0.8,
                specific_validations=["cookbook_name", "recipe_structure", "resource_declarations"]
            ),
            
            "terraform": PlatformTestConfig(
                platform_name="terraform",
                test_code='''
# x2a Terraform Test Configuration
terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_instance" "x2a_test" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.micro"
  
  tags = {
    Name = "x2a-test-instance"
    Environment = "test"
  }
}

resource "aws_security_group" "x2a_test_sg" {
  name_description = "x2a test security group"
  
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}
                '''.strip(),
                expected_complexity="medium",
                min_confidence=0.8,
                specific_validations=["provider_declarations", "resource_definitions", "terraform_block"]
            ),
            
            "puppet": PlatformTestConfig(
                platform_name="puppet",
                test_code='''
# x2a Puppet Test Configuration
class x2a_nginx_test {
  package { 'nginx':
    ensure => installed,
  }
  
  service { 'nginx':
    ensure => running,
    enable => true,
    require => Package['nginx'],
  }
  
  file { '/etc/nginx/nginx.conf':
    ensure  => file,
    content => template('nginx/nginx.conf.erb'),
    notify  => Service['nginx'],
  }
}
                '''.strip(),
                expected_complexity="low",
                min_confidence=0.7,
                specific_validations=["class_definitions", "resource_declarations", "dependency_relationships"]
            ),
            
            "mixed_platform": PlatformTestConfig(
                platform_name="mixed",
                test_code='''
# x2a Mixed Platform Test Configuration

# Chef Recipe
cookbook_name = "x2a_mixed_test"

package "docker" do
  action :install
end

# Terraform Configuration  
resource "aws_instance" "docker_host" {
  ami           = "ami-0c02fb55956c7d316"
  instance_type = "t3.medium"
  
  tags = {
    Name = "x2a-docker-host"
  }
}

# Puppet Manifest
class docker_config {
  package { 'docker-ce':
    ensure => installed,
  }
}
                '''.strip(),
                expected_complexity="high",
                min_confidence=0.6,
                specific_validations=["multiple_platforms", "complexity_assessment", "mixed_syntax"]
            )
        }
    
    def _get_test_data_config(self) -> Dict[str, Any]:
        """Get test data configuration."""
        return {
            "default_test_code": self.platform_configs["chef"].test_code,
            "supported_platforms": ["chef", "terraform", "puppet", "salt", "bladelogic"],
            "supported_agents": [
                "orchestrator", "universal_extractor", "structured_analyzer",
                "spec_generator", "storage_manager", "synthesizer"
            ],
            "test_data_directory": str(Path(__file__).parent.parent / "fixtures" / "test_data"),
            "mock_data_enabled": self.environment in [TestEnvironment.TEST, TestEnvironment.DEVELOPMENT],
            "real_llm_enabled": self.environment in [TestEnvironment.STAGING, TestEnvironment.PRODUCTION]
        }
    
    def _get_logging_config(self) -> Dict[str, Any]:
        """Get logging configuration."""
        log_levels = {
            TestEnvironment.DEVELOPMENT: "DEBUG",
            TestEnvironment.TEST: "INFO", 
            TestEnvironment.STAGING: "INFO",
            TestEnvironment.PRODUCTION: "WARNING",
            TestEnvironment.CI_CD: "INFO"
        }
        
        return {
            "level": log_levels.get(self.environment, "INFO"),
            "format": "%(asctime)s - x2a_test_framework - %(name)s - %(levelname)s - %(message)s",
            "enable_file_logging": self.environment != TestEnvironment.DEVELOPMENT,
            "log_file": f"x2a_test_{self.environment.value}.log",
            "enable_performance_logging": True,
            "enable_metrics_collection": self.environment in [TestEnvironment.STAGING, TestEnvironment.PRODUCTION]
        }
    
    def get_platform_test_code(self, platform: str) -> str:
        """Get test code for specific platform."""
        platform_config = self.platform_configs.get(platform.lower())
        if platform_config:
            return platform_config.test_code
        
        # Return default if platform not found
        logger.warning(f"Platform '{platform}' not configured, using default Chef code")
        return self.platform_configs["chef"].test_code
    
    def get_platform_config(self, platform: str) -> Optional[PlatformTestConfig]:
        """Get complete configuration for specific platform."""
        return self.platform_configs.get(platform.lower())
    
    def get_timeout(self, operation: str) -> float:
        """Get timeout for specific operation."""
        return self.timeouts.get(operation, 30.0)
    
    def get_performance_threshold(self, metric: str) -> float:
        """Get performance threshold for specific metric."""
        return getattr(self.thresholds, metric, None)
    
    def set_performance_profile(self, profile: PerformanceProfile):
        """Change performance profile and reload thresholds."""
        self.performance_profile = profile
        self.thresholds = self._get_performance_thresholds()
        logger.info(f"Performance profile changed to {profile.value}")
    
    def validate_configuration(self) -> List[str]:
        """Validate current configuration and return any issues."""
        issues = []
        
        # Validate timeouts
        for operation, timeout in self.timeouts.items():
            if timeout <= 0:
                issues.append(f"Invalid timeout for {operation}: {timeout}")
        
        # Validate platform configs
        for platform, config in self.platform_configs.items():
            if not config.test_code.strip():
                issues.append(f"Empty test code for platform: {platform}")
            if not 0 <= config.min_confidence <= 1:
                issues.append(f"Invalid confidence for platform {platform}: {config.min_confidence}")
        
        # Validate test data config
        test_data_dir = Path(self.test_data_config["test_data_directory"])
        if not test_data_dir.exists():
            issues.append(f"Test data directory does not exist: {test_data_dir}")
        
        return issues
    
    def get_environment_info(self) -> Dict[str, Any]:
        """Get comprehensive environment information."""
        return {
            "environment": self.environment.value,
            "performance_profile": self.performance_profile.value,
            "timeouts": self.timeouts,
            "thresholds": {
                "max_execution_time": self.thresholds.max_execution_time,
                "max_memory_increase": self.thresholds.max_memory_increase,
                "min_confidence": self.thresholds.min_confidence,
                "max_confidence": self.thresholds.max_confidence
            },
            "supported_platforms": self.test_data_config["supported_platforms"],
            "supported_agents": self.test_data_config["supported_agents"],
            "mock_data_enabled": self.test_data_config["mock_data_enabled"],
            "real_llm_enabled": self.test_data_config["real_llm_enabled"]
        }


class FrameworkConfig:
    """
    Global framework configuration manager.
    
    Provides singleton access to framework configuration and utilities
    for configuration management across the entire test suite.
    """
    
    _instance = None
    _config = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            # Determine environment from environment variables
            env_name = os.getenv("X2A_TEST_ENVIRONMENT", "test").lower()
            
            try:
                environment = TestEnvironment(env_name)
            except ValueError:
                logger.warning(f"Invalid environment '{env_name}', defaulting to test")
                environment = TestEnvironment.TEST
            
            self._config = X2ATestConfig(environment)
            
            # Configure logging
            self._configure_logging()
            
            # Validate configuration
            issues = self._config.validate_configuration()
            if issues:
                logger.warning(f"Configuration issues found: {issues}")
    
    def _configure_logging(self):
        """Configure framework logging based on configuration."""
        log_config = self._config.logging_config
        
        # Set log level
        logger.setLevel(log_config["level"])
        
        # Configure formatters
        formatter = logging.Formatter(log_config["format"])
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler if enabled
        if log_config["enable_file_logging"]:
            try:
                file_handler = logging.FileHandler(log_config["log_file"])
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
            except Exception as e:
                logger.warning(f"Could not configure file logging: {e}")
    
    @property
    def config(self) -> X2ATestConfig:
        """Get the framework configuration."""
        return self._config
    
    @classmethod
    def get_instance(cls) -> 'FrameworkConfig':
        """Get the singleton framework configuration instance."""
        if cls._instance is None:
            cls()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the framework configuration (useful for testing)."""
        cls._instance = None
        cls._config = None


# Global configuration instance
def get_config() -> X2ATestConfig:
    """Get the global x2a test framework configuration."""
    return FrameworkConfig.get_instance().config


# Convenience functions for common configuration access
def get_platform_test_code(platform: str) -> str:
    """Get test code for specified platform."""
    return get_config().get_platform_test_code(platform)


def get_timeout(operation: str) -> float:
    """Get timeout for specified operation."""
    return get_config().get_timeout(operation)


def get_performance_threshold(metric: str) -> float:
    """Get performance threshold for specified metric."""
    return get_config().get_performance_threshold(metric)


def get_environment_info() -> Dict[str, Any]:
    """Get current environment information."""
    return get_config().get_environment_info()
