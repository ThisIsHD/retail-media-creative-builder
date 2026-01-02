class AppError(Exception):
    """Base application error"""


class ConfigError(AppError):
    """Missing or invalid configuration"""


class DatabaseError(AppError):
    """MongoDB connection or query failure"""


class SessionNotFoundError(AppError):
    """Session ID not found in database"""


class TurnPersistenceError(AppError):
    """Failed to persist a turn"""


class AgentExecutionError(AppError):
    """Agent or graph execution failure"""


class ComplianceHardFail(AppError):
    """Raised when compliance returns HARD_FAIL"""


class ToolInvocationError(AppError):
    """Tool execution failed (image ops, compliance, etc.)"""
