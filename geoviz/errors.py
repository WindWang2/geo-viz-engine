from enum import StrEnum


class ErrorCode(StrEnum):
    UNSUPPORTED = "unsupported"
    INVALID_DATA = "invalid_data"
    DEPENDENCY_MISSING = "dependency_missing"
    IO_ERROR = "io_error"
    RESOURCE_LIMIT = "resource_limit"
    RENDER_ERROR = "render_error"


class GeoVizError(RuntimeError):
    def __init__(self, code: ErrorCode, message: str, *, detail: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.detail = detail
