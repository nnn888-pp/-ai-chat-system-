from __future__ import annotations


class BizError(Exception):
    def __init__(self, code: int, message: str, http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status or self._default_http(code)

    @staticmethod
    def _default_http(code: int) -> int:
        mapping = {
            1001: 422, 1002: 401, 1003: 401, 1004: 403, 1005: 409,
            1006: 400, 1007: 404,
            2001: 502, 2002: 500, 2003: 409, 2004: 404,
        }
        return mapping.get(code, 500)
