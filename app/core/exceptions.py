"""Project-level exceptions."""


class ApplicationError(Exception):
    """Base error for the application."""


class ConfigurationError(ApplicationError):
    """Raised when configuration cannot be loaded or validated."""


class RegistryError(ApplicationError):
    """Raised when a registry cannot be built or queried."""
