"""
Core Infrastructure Analysis Tools

Platform-agnostic tools for comprehensive infrastructure analysis:
- chef_facts_extractor: Sophisticated Tree-sitter AST analysis for Chef
- puppet_facts_extractor: Pattern-based fact extraction for Puppet (minimal, extensible)
- terraform_facts_extractor: HCL pattern analysis for Terraform (minimal, extensible)
- bladelogic_facts_extractor: NSH script and job analysis for BladeLogic (minimal, extensible)
- platform_detector: Realistic file pattern detection  
- complexity_analyzer: Real complexity metrics from extracted facts
- migration_assessor: Practical migration guidance
"""

from .chef_extractor import chef_facts_extractor
from .puppet_facts_extractor import puppet_facts_extractor
from .terraform_facts_extractor import terraform_facts_extractor
from .bladelogic_facts_extractor import bladelogic_facts_extractor
from .platform_detector import platform_detector
from .complexity_analyzer import complexity_analyzer  
from .migration_assessor import migration_assessor

# Platform-agnostic tools - minimal implementations that can be extended
__all__ = [
    "chef_facts_extractor",
    "puppet_facts_extractor", 
    "terraform_facts_extractor",
    "bladelogic_facts_extractor",
    "platform_detector", 
    "complexity_analyzer",
    "migration_assessor"
]