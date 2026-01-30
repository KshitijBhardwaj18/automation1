"""File-based customer configuration storage.

Stores customer configurations as JSON files in a local directory.
Designed with an abstract interface for easy migration to S3 or other backends.
"""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from api.models import CustomerConfig


class ConfigStorageBackend(ABC):
    """Abstract base class for configuration storage backends."""

    @abstractmethod
    def save(self, customer_id: str, config: CustomerConfig) -> None:
        """Save a customer configuration.

        Args:
            customer_id: Unique customer identifier
            config: Customer configuration to save
        """
        pass

    @abstractmethod
    def get(self, customer_id: str) -> Optional[CustomerConfig]:
        """Retrieve a customer configuration.

        Args:
            customer_id: Unique customer identifier

        Returns:
            Customer configuration or None if not found
        """
        pass

    @abstractmethod
    def delete(self, customer_id: str) -> bool:
        """Delete a customer configuration.

        Args:
            customer_id: Unique customer identifier

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def list_all(self) -> list[CustomerConfig]:
        """List all customer configurations.

        Returns:
            List of all customer configurations
        """
        pass

    @abstractmethod
    def exists(self, customer_id: str) -> bool:
        """Check if a customer configuration exists.

        Args:
            customer_id: Unique customer identifier

        Returns:
            True if exists, False otherwise
        """
        pass


class FileConfigStorage(ConfigStorageBackend):
    """File-based configuration storage using JSON files.

    Stores configurations in: {base_path}/{customer_id}.json
    """

    def __init__(self, base_path: str = "config") -> None:
        """Initialize file-based storage.

        Args:
            base_path: Directory path for storing config files
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def _get_config_path(self, customer_id: str) -> Path:
        """Get the file path for a customer's configuration.

        Args:
            customer_id: Unique customer identifier

        Returns:
            Path to the configuration file
        """
        return self.base_path / f"{customer_id}.json"

    def save(self, customer_id: str, config: CustomerConfig) -> None:
        """Save a customer configuration to a JSON file.

        Args:
            customer_id: Unique customer identifier
            config: Customer configuration to save
        """
        config_path = self._get_config_path(customer_id)
        config_data = config.model_dump(mode="json")
        config_path.write_text(json.dumps(config_data, indent=2))

    def get(self, customer_id: str) -> Optional[CustomerConfig]:
        """Retrieve a customer configuration from file.

        Args:
            customer_id: Unique customer identifier

        Returns:
            Customer configuration or None if not found
        """
        config_path = self._get_config_path(customer_id)
        if not config_path.exists():
            return None

        config_data = json.loads(config_path.read_text())
        return CustomerConfig.model_validate(config_data)

    def delete(self, customer_id: str) -> bool:
        """Delete a customer configuration file.

        Args:
            customer_id: Unique customer identifier

        Returns:
            True if deleted, False if not found
        """
        config_path = self._get_config_path(customer_id)
        if not config_path.exists():
            return False

        config_path.unlink()
        return True

    def list_all(self) -> list[CustomerConfig]:
        """List all customer configurations from files.

        Returns:
            List of all customer configurations
        """
        configs: list[CustomerConfig] = []
        for config_file in self.base_path.glob("*.json"):
            try:
                config_data = json.loads(config_file.read_text())
                configs.append(CustomerConfig.model_validate(config_data))
            except (json.JSONDecodeError, ValueError):
                # Skip invalid config files
                continue
        return configs

    def exists(self, customer_id: str) -> bool:
        """Check if a customer configuration file exists.

        Args:
            customer_id: Unique customer identifier

        Returns:
            True if exists, False otherwise
        """
        return self._get_config_path(customer_id).exists()


# Default storage instance
config_storage = FileConfigStorage()
