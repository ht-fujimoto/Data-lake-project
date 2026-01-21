"""
Configuration Loader

Loads configuration from YAML files for the data lake construction.
"""

import yaml
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)


class ConfigLoader:
    """設定ファイルローダー"""
    
    def __init__(self, config_path: str = None):
        """
        Initialize the configuration loader
        
        Args:
            config_path: Path to the configuration file (optional)
                        Defaults to datalake/config/datalake_config.yaml
        """
        if config_path is None:
            # Default to datalake/config/datalake_config.yaml
            config_path = Path(__file__).parent / "config" / "datalake_config.yaml"
        
        self.config_path = Path(config_path)
        self.config = self._load_config()
    
    @staticmethod
    def load_config(config_path: str) -> Dict[str, Any]:
        """
        Load configuration from YAML file (static method)
        
        Args:
            config_path: Path to the configuration file
        
        Returns:
            Configuration dictionary
        """
        config_path = Path(config_path)
        
        if not config_path.exists():
            logger.error(f"Config file not found: {config_path}")
            raise FileNotFoundError(f"Config file not found: {config_path}")
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded config from {config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from YAML file
        
        Returns:
            Configuration dictionary
        """
        if not self.config_path.exists():
            logger.error(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded config from {self.config_path}")
                return config
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            raise
    
    def load(self) -> Dict[str, Any]:
        """
        Load and return configuration
        
        Returns:
            Configuration dictionary
        """
        return self.config
    
    def get_aws_config(self) -> Dict[str, Any]:
        """
        Get AWS configuration
        
        Returns:
            AWS configuration dictionary with:
            - database: Glue database name
            - s3_bucket: S3 bucket name for Iceberg tables
            - workgroup: Athena workgroup
            - region: AWS region
        """
        return self.config.get("aws", {})
    
    def get_s3_bucket(self) -> str:
        """
        Get S3 bucket name for Iceberg tables
        
        Returns:
            S3 bucket name
        """
        return self.config.get("aws", {}).get("s3_bucket", "estat-iceberg-datalake")
    
    def get_database(self) -> str:
        """
        Get Glue database name
        
        Returns:
            Database name
        """
        return self.config.get("aws", {}).get("database", "estat_db")
    
    def get_workgroup(self) -> str:
        """
        Get Athena workgroup
        
        Returns:
            Workgroup name
        """
        return self.config.get("aws", {}).get("workgroup", "estat-mcp-workgroup")
    
    def get_region(self) -> str:
        """
        Get AWS region
        
        Returns:
            Region name
        """
        return self.config.get("aws", {}).get("region", "ap-northeast-1")
    
    def get_table_config(self) -> Dict[str, Any]:
        """
        Get table configuration
        
        Returns:
            Table configuration dictionary
        """
        return self.config.get("tables", {})
    
    def get_metadata_config(self) -> Dict[str, Any]:
        """
        Get metadata configuration
        
        Returns:
            Metadata configuration dictionary
        """
        return self.config.get("metadata", {})
    
    def get_domain_table_location(self, domain: str) -> str:
        """
        Get S3 location for a domain table
        
        Args:
            domain: Domain name (population, economy, generic)
        
        Returns:
            S3 location for the domain table
        """
        domain_tables = self.config.get("tables", {}).get("domain_tables", {})
        return domain_tables.get(domain, f"s3://{self.get_s3_bucket()}/iceberg-tables/{domain}/")


# グローバル設定インスタンス
_config_instance = None


def get_config(config_path: str = None) -> ConfigLoader:
    """
    Get the global configuration instance
    
    Args:
        config_path: Path to the configuration file (optional)
    
    Returns:
        ConfigLoader instance
    """
    global _config_instance
    
    if _config_instance is None or config_path is not None:
        _config_instance = ConfigLoader(config_path)
    
    return _config_instance
