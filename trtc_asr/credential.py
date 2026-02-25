"""Credential management for TRTC-ASR authentication."""


class Credential:
    """Holds the authentication information for the TRTC-ASR service.

    Three values are needed:
        - app_id: Tencent Cloud account APPID, from https://console.cloud.tencent.com/cam/capi
        - sdk_app_id: TRTC application ID, from https://console.cloud.tencent.com/trtc/app
        - secret_key: TRTC SDK secret key, from TRTC console > Application Overview > SDK Key

    Example::

        credential = Credential(
            app_id=1300403317,
            sdk_app_id=1400188366,
            secret_key="your-sdk-secret-key",
        )
    """

    def __init__(self, app_id: int, sdk_app_id: int, secret_key: str) -> None:
        self.app_id = app_id
        self.sdk_app_id = sdk_app_id
        self.secret_key = secret_key
        self.user_sig: str = ""

    def set_user_sig(self, user_sig: str) -> None:
        """Set a pre-computed UserSig. If not set, the SDK will auto-generate it."""
        self.user_sig = user_sig
