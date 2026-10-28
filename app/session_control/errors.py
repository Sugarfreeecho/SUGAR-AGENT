from __future__ import annotations


class ControlError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 400, details=None):
        super().__init__(message)
        self.code, self.message, self.status, self.details = code, message, status, details


def envelope(data=None, *, request_id="", operation_id=None, error=None):
    return {"schema_version": 1, "ok": error is None, "request_id": request_id,
            "operation_id": operation_id, "data": data if error is None else None,
            "error": None if error is None else {"code": error.code, "message": error.message,
                                                  "details": error.details}}
