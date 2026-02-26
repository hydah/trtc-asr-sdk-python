"""UserSig generation using the official tls-sig-api-v2 library."""

import TLSSigAPIv2

DEFAULT_EXPIRE = 86400 * 180  # 180 days in seconds


def gen_user_sig(
    sdk_app_id: int, key: str, user_id: str, expire: int = 0
) -> str:
    """Generate a TRTC UserSig.

    Args:
        sdk_app_id: TRTC application ID.
        key: TRTC secret key (from console).
        user_id: Unique user identifier (maps to voice_id in ASR).
        expire: Signature validity in seconds (0 uses default 180 days).

    Returns:
        The generated UserSig string.
    """
    if expire <= 0:
        expire = DEFAULT_EXPIRE

    api = TLSSigAPIv2.TLSSigAPIv2(sdk_app_id, key)
    return api.gen_sig(user_id, expire)
