"""Utilities for verification configuration management."""

import logging
from pathlib import Path

import yaml

from agent_pump.models.verification_config import VerificationConfig

logger = logging.getLogger(__name__)


def load_verification_config(project_path: Path) -> VerificationConfig:
    """
    Load verification configuration from .agent-pump.yml file in the project directory.
    
    Args:
        project_path: Path to the project directory
        
    Returns:
        VerificationConfig with settings loaded from the config file
    """
    config_path = project_path / ".agent-pump.yml"

    if not config_path.exists():
        logger.debug(f"No verification config found at {config_path}, using defaults")
        return VerificationConfig()

    try:
        with open(config_path) as f:
            config_data = yaml.safe_load(f) or {}

        # Extract verification-specific settings from the config
        verification_data = config_data.get('verification', {})

        # Create and return the VerificationConfig instance
        return VerificationConfig.model_validate(verification_data)

    except Exception as e:
        logger.error(f"Failed to load verification config from {config_path}: {e}")
        return VerificationConfig()


def save_verification_config(project_path: Path, config: VerificationConfig) -> None:
    """
    Save verification configuration to .agent-pump.yml file in the project directory.
    
    Args:
        project_path: Path to the project directory
        config: VerificationConfig to save
    """
    config_path = project_path / ".agent-pump.yml"

    # Load existing config to preserve other settings
    existing_config = {}
    if config_path.exists():
        try:
            with open(config_path) as f:
                existing_config = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(
                f"Failed to load existing config from {config_path}, starting fresh: {e}"
            )

    # Update only the verification section
    existing_config['verification'] = config.model_dump(exclude_defaults=True)

    # Write the updated config back to the file
    with open(config_path, 'w') as f:
        yaml.safe_dump(existing_config, f, default_flow_style=False, indent=2)

    logger.info(f"Saved verification config to {config_path}")
