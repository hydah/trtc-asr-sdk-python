"""Error codes and error types for TRTC-ASR SDK."""

# Error codes
ERR_INVALID_PARAM = 1001
ERR_CONNECT_FAILED = 1002
ERR_WRITE_FAILED = 1003
ERR_READ_FAILED = 1004
ERR_AUTH_FAILED = 1005
ERR_TIMEOUT = 1006
ERR_SERVER_ERROR = 1007
ERR_ALREADY_STARTED = 1008
ERR_NOT_STARTED = 1009
ERR_ALREADY_STOPPED = 1010


class ASRError(Exception):
    """Error returned by the TRTC-ASR service or SDK."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"trtc-asr error [{code}]: {message}")
