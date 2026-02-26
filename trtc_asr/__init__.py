"""Tencent TRTC ASR SDK for Python."""

from trtc_asr.credential import Credential
from trtc_asr.speech_recognizer import (
    SpeechRecognizer,
    SpeechRecognitionListener,
    SpeechRecognitionResponse,
)
from trtc_asr.sentence_recognizer import (
    SentenceRecognizer,
    SentenceRecognitionRequest,
    SentenceRecognitionResult,
)
from trtc_asr.errors import ASRError

__all__ = [
    "Credential",
    "SpeechRecognizer",
    "SpeechRecognitionListener",
    "SpeechRecognitionResponse",
    "SentenceRecognizer",
    "SentenceRecognitionRequest",
    "SentenceRecognitionResult",
    "ASRError",
]

__version__ = "0.1.0"
