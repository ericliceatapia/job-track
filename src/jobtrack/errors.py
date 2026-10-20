"""Domain failures shared by every interface."""

class JobTrackError(ValueError):
    """Base class for expected user-correctable failures."""

class ValidationError(JobTrackError):
    """Invalid input or lifecycle operation."""

class ApplicationNotFound(JobTrackError):
    """An update targets an application that does not exist."""
