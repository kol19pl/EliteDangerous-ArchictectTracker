"""
Configuration module for EDMC Architect Tracker plugin.

Provides a simple config object compatible with EDMC's configuration system.
When running within EDMC, this will integrate with EDMC's config.
When testing standalone, it uses default values.
"""

import logging

logger = logging.getLogger("ArchitectTracker")


class Config:
    """Configuration object that manages plugin settings."""
    
    # Default configuration values
    _defaults = {
        'theme': 0,  # 0 = THEME_DEFAULT (light), 1 = THEME_DARK, 2 = THEME_TRANSPARENT
    }
    
    # Runtime configuration storage
    _config = _defaults.copy()
    
    def get_int(self, key: str, default: int = None):
        """
        Get an integer configuration value.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key not found (uses _defaults if not specified)
            
        Returns:
            Integer configuration value
        """
        if default is None:
            default = self._defaults.get(key, 0)
        
        value = self._config.get(key, default)
        
        try:
            return int(value)
        except (ValueError, TypeError):
            logger.warning(f"Config value for '{key}' is not a valid integer: {value}")
            return default
    
    def get_str(self, key: str, default: str = ""):
        """
        Get a string configuration value.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            String configuration value
        """
        return str(self._config.get(key, default))
    
    def get_bool(self, key: str, default: bool = False):
        """
        Get a boolean configuration value.
        
        Args:
            key: Configuration key to retrieve
            default: Default value if key not found
            
        Returns:
            Boolean configuration value
        """
        value = self._config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.lower() in ('true', '1', 'yes', 'on')
        return bool(value)
    
    def set_int(self, key: str, value: int):
        """
        Set an integer configuration value.
        
        Args:
            key: Configuration key to set
            value: Integer value to set
        """
        self._config[key] = int(value)
    
    def set_str(self, key: str, value: str):
        """
        Set a string configuration value.
        
        Args:
            key: Configuration key to set
            value: String value to set
        """
        self._config[key] = str(value)
    
    def set_bool(self, key: str, value: bool):
        """
        Set a boolean configuration value.
        
        Args:
            key: Configuration key to set
            value: Boolean value to set
        """
        self._config[key] = bool(value)


# Global config instance for use throughout the plugin
config = Config()
