"""URL query parameter building for the ASR WebSocket request."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from urllib.parse import quote


@dataclass
class SignatureParams:
    """Holds URL query parameters for the ASR WebSocket request.

    The ``secretid`` URL parameter is required by the protocol but internally
    populated with AppID — users do not need to provide a separate SecretID.
    The ``signature`` parameter is set to the UserSig value per protocol spec.
    """

    app_id: int
    engine_model_type: str
    voice_id: str
    timestamp: int = field(default_factory=lambda: int(time.time()))
    expired: int = 0
    nonce: int = field(default_factory=lambda: random.randint(1, 9999999))
    voice_format: int = 1  # PCM
    need_vad: int = 1
    convert_num_mode: int = 1

    # Optional parameters
    hotword_id: str = ""
    customization_id: str = ""
    filter_dirty: int = 0
    filter_modal: int = 0
    filter_punc: int = 0
    word_info: int = 0
    vad_silence_time: int = 0
    max_speak_time: int = 0

    def __post_init__(self) -> None:
        if self.expired == 0:
            self.expired = self.timestamp + 86400

    def build_query_string(self) -> str:
        """Build URL query string without signature."""
        params = self._to_map()
        return _encode_params(params)

    def build_query_string_with_signature(self, user_sig: str) -> str:
        """Build URL query string with signature set to the given UserSig.

        Per protocol: ``signature`` value equals ``X-TRTC-UserSig``.
        """
        params = self._to_map()
        params["signature"] = user_sig
        return _encode_params(params)

    def _to_map(self) -> dict[str, str]:
        m: dict[str, str] = {
            "secretid": str(self.app_id),
            "timestamp": str(self.timestamp),
            "expired": str(self.expired),
            "nonce": str(self.nonce),
            "engine_model_type": self.engine_model_type,
            "voice_id": self.voice_id,
            "voice_format": str(self.voice_format),
            "needvad": str(self.need_vad),
        }

        if self.hotword_id:
            m["hotword_id"] = self.hotword_id
        if self.customization_id:
            m["customization_id"] = self.customization_id
        if self.filter_dirty:
            m["filter_dirty"] = str(self.filter_dirty)
        if self.filter_modal:
            m["filter_modal"] = str(self.filter_modal)
        if self.filter_punc:
            m["filter_punc"] = str(self.filter_punc)
        if self.convert_num_mode:
            m["convert_num_mode"] = str(self.convert_num_mode)
        if self.word_info:
            m["word_info"] = str(self.word_info)
        if self.vad_silence_time:
            m["vad_silence_time"] = str(self.vad_silence_time)
        if self.max_speak_time:
            m["max_speak_time"] = str(self.max_speak_time)

        return m


def _encode_params(params: dict[str, str]) -> str:
    """Encode parameters into a sorted URL query string."""
    return "&".join(
        f"{k}={quote(v, safe='')}" for k, v in sorted(params.items())
    )
