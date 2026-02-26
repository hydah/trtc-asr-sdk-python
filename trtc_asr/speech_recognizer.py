"""Real-time speech recognition client for TRTC-ASR."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional

import websockets
import websockets.asyncio.client

from trtc_asr.credential import Credential
from trtc_asr.errors import (
    ASRError,
    ERR_ALREADY_STARTED,
    ERR_AUTH_FAILED,
    ERR_CONNECT_FAILED,
    ERR_NOT_STARTED,
    ERR_READ_FAILED,
    ERR_WRITE_FAILED,
)
from trtc_asr.signature import SignatureParams
from trtc_asr.usersig import gen_user_sig

logger = logging.getLogger(__name__)

ENDPOINT = "wss://asr.cloud-rtc.com"


class _State(IntEnum):
    IDLE = 0
    STARTING = 1
    RUNNING = 2
    STOPPING = 3
    STOPPED = 4


@dataclass
class WordInfo:
    """Word-level recognition details."""

    word: str = ""
    start_time: int = 0
    end_time: int = 0
    stable_flag: int = 0


@dataclass
class Result:
    """Speech recognition result details."""

    slice_type: int = 0
    index: int = 0
    start_time: int = 0
    end_time: int = 0
    voice_text_str: str = ""
    word_size: int = 0
    word_list: list[WordInfo] = field(default_factory=list)


@dataclass
class SpeechRecognitionResponse:
    """Response message from the ASR service."""

    code: int = 0
    message: str = ""
    voice_id: str = ""
    message_id: str = ""
    final: int = 0
    result: Result = field(default_factory=Result)

    @classmethod
    def from_dict(cls, data: dict) -> SpeechRecognitionResponse:
        result_data = data.get("result", {})
        word_list = [
            WordInfo(
                word=w.get("word", ""),
                start_time=w.get("start_time", 0),
                end_time=w.get("end_time", 0),
                stable_flag=w.get("stable_flag", 0),
            )
            for w in result_data.get("word_list", [])
        ]
        result = Result(
            slice_type=result_data.get("slice_type", 0),
            index=result_data.get("index", 0),
            start_time=result_data.get("start_time", 0),
            end_time=result_data.get("end_time", 0),
            voice_text_str=result_data.get("voice_text_str", ""),
            word_size=result_data.get("word_size", 0),
            word_list=word_list,
        )
        return cls(
            code=data.get("code", 0),
            message=data.get("message", ""),
            voice_id=data.get("voice_id", ""),
            message_id=data.get("message_id", ""),
            final=data.get("final", 0),
            result=result,
        )


class SpeechRecognitionListener(ABC):
    """Callback interface for speech recognition events."""

    @abstractmethod
    def on_recognition_start(self, response: SpeechRecognitionResponse) -> None:
        """Called when the recognition session starts."""

    @abstractmethod
    def on_sentence_begin(self, response: SpeechRecognitionResponse) -> None:
        """Called when a new sentence begins."""

    @abstractmethod
    def on_recognition_result_change(self, response: SpeechRecognitionResponse) -> None:
        """Called when intermediate results are available."""

    @abstractmethod
    def on_sentence_end(self, response: SpeechRecognitionResponse) -> None:
        """Called when a sentence ends with the final result."""

    @abstractmethod
    def on_recognition_complete(self, response: SpeechRecognitionResponse) -> None:
        """Called when the entire recognition session completes."""

    @abstractmethod
    def on_fail(self, response: Optional[SpeechRecognitionResponse], error: Exception) -> None:
        """Called when an error occurs during recognition."""


class SpeechRecognizer:
    """Real-time speech recognition client using WebSocket.

    Example::

        credential = Credential(app_id=130xxx, sdk_app_id=140xxx, secret_key="xxx")
        listener = MyListener()
        recognizer = SpeechRecognizer(credential, "16k_zh", listener)

        await recognizer.start()
        await recognizer.write(audio_data)
        await recognizer.stop()
    """

    def __init__(
        self,
        credential: Credential,
        engine_model_type: str,
        listener: SpeechRecognitionListener,
    ) -> None:
        self._credential = credential
        self._listener = listener
        self._engine_model_type = engine_model_type
        self._endpoint = ENDPOINT

        # Configuration (defaults match Go SDK)
        self._voice_format = 1  # PCM
        self._need_vad = 1
        self._convert_num_mode = 1
        self._hotword_id = ""
        self._customization_id = ""
        self._filter_dirty = 0
        self._filter_modal = 0
        self._filter_punc = 0
        self._word_info = 0
        self._vad_silence_time = 0
        self._max_speak_time = 0
        self._voice_id = ""
        self._write_timeout = 5.0

        self._state = _State.IDLE
        self._ws: Optional[websockets.asyncio.client.ClientConnection] = None
        self._read_task: Optional[asyncio.Task] = None

    # ---- Configuration setters ----

    def set_voice_format(self, fmt: int) -> None:
        self._voice_format = fmt

    def set_need_vad(self, need_vad: int) -> None:
        self._need_vad = need_vad

    def set_convert_num_mode(self, mode: int) -> None:
        self._convert_num_mode = mode

    def set_hotword_id(self, hotword_id: str) -> None:
        self._hotword_id = hotword_id

    def set_customization_id(self, customization_id: str) -> None:
        self._customization_id = customization_id

    def set_filter_dirty(self, mode: int) -> None:
        self._filter_dirty = mode

    def set_filter_modal(self, mode: int) -> None:
        self._filter_modal = mode

    def set_filter_punc(self, mode: int) -> None:
        self._filter_punc = mode

    def set_word_info(self, mode: int) -> None:
        self._word_info = mode

    def set_vad_silence_time(self, ms: int) -> None:
        self._vad_silence_time = ms

    def set_max_speak_time(self, ms: int) -> None:
        self._max_speak_time = ms

    def set_voice_id(self, voice_id: str) -> None:
        self._voice_id = voice_id

    def set_write_timeout(self, timeout: float) -> None:
        self._write_timeout = timeout

    # ---- Core operations ----

    async def start(self) -> None:
        """Initiate the WebSocket connection and begin the recognition session."""
        if self._state != _State.IDLE:
            raise ASRError(ERR_ALREADY_STARTED, "recognizer already started")

        self._state = _State.STARTING

        try:
            await self._connect()
        except ASRError:
            self._state = _State.IDLE
            raise
        except Exception as exc:
            self._state = _State.IDLE
            raise ASRError(ERR_CONNECT_FAILED, f"websocket connect failed: {exc}") from exc

        self._state = _State.RUNNING
        self._read_task = asyncio.create_task(self._read_loop())

    async def write(self, data: bytes) -> None:
        """Send audio data to the ASR service."""
        if self._state != _State.RUNNING:
            raise ASRError(ERR_NOT_STARTED, "recognizer not running")
        if self._ws is None:
            raise ASRError(ERR_NOT_STARTED, "connection not established")

        try:
            await asyncio.wait_for(self._ws.send(data), timeout=self._write_timeout)
        except Exception as exc:
            raise ASRError(ERR_WRITE_FAILED, f"write audio data failed: {exc}") from exc

    async def stop(self) -> None:
        """Gracefully stop the recognition session."""
        if self._state != _State.RUNNING:
            raise ASRError(ERR_NOT_STARTED, "recognizer not running")

        self._state = _State.STOPPING

        if self._ws is None:
            self._state = _State.STOPPED
            raise ASRError(ERR_NOT_STARTED, "connection not established")

        try:
            end_msg = json.dumps({"type": "end"})
            await asyncio.wait_for(self._ws.send(end_msg), timeout=self._write_timeout)
        except Exception as exc:
            await self._close()
            self._state = _State.STOPPED
            raise ASRError(ERR_WRITE_FAILED, f"send end signal failed: {exc}") from exc

        # Wait for read loop to finish
        if self._read_task is not None:
            try:
                await asyncio.wait_for(self._read_task, timeout=10.0)
            except asyncio.TimeoutError:
                await self._close()

        self._state = _State.STOPPED

    # ---- Internal methods ----

    async def _connect(self) -> None:
        voice_id = self._voice_id or str(uuid.uuid4())
        self._voice_id = voice_id

        # Generate UserSig if not already set
        if not self._credential.user_sig:
            try:
                self._credential.user_sig = gen_user_sig(
                    self._credential.sdk_app_id,
                    self._credential.secret_key,
                    voice_id,
                    86400,
                )
            except Exception as exc:
                raise ASRError(ERR_AUTH_FAILED, f"generate user sig failed: {exc}") from exc

        # Build request parameters
        sig_params = SignatureParams(
            app_id=self._credential.app_id,
            engine_model_type=self._engine_model_type,
            voice_id=voice_id,
            voice_format=self._voice_format,
            need_vad=self._need_vad,
            convert_num_mode=self._convert_num_mode,
            hotword_id=self._hotword_id,
            customization_id=self._customization_id,
            filter_dirty=self._filter_dirty,
            filter_modal=self._filter_modal,
            filter_punc=self._filter_punc,
            word_info=self._word_info,
            vad_silence_time=self._vad_silence_time,
            max_speak_time=self._max_speak_time,
        )

        query_string = sig_params.build_query_string_with_signature(
            self._credential.user_sig
        )
        ws_url = f"{self._endpoint}/asr/v2/{self._credential.app_id}?{query_string}"

        headers = {
            "X-TRTC-SdkAppId": str(self._credential.sdk_app_id),
            "X-TRTC-UserSig": self._credential.user_sig,
        }

        self._ws = await websockets.asyncio.client.connect(
            ws_url,
            additional_headers=headers,
            open_timeout=10,
        )

    async def _read_loop(self) -> None:
        try:
            async for message in self._ws:
                if isinstance(message, bytes):
                    message = message.decode("utf-8")

                try:
                    data = json.loads(message)
                except json.JSONDecodeError as exc:
                    self._listener.on_fail(
                        None, ASRError(ERR_READ_FAILED, f"unmarshal response failed: {exc}")
                    )
                    continue

                resp = SpeechRecognitionResponse.from_dict(data)

                if resp.code != 0:
                    self._listener.on_fail(resp, ASRError(resp.code, resp.message))
                    return

                self._dispatch_event(resp)

                if resp.final == 1:
                    self._listener.on_recognition_complete(resp)
                    return
        except websockets.ConnectionClosed:
            if self._state >= _State.STOPPING:
                return
            self._listener.on_fail(
                None, ASRError(ERR_READ_FAILED, "websocket connection closed unexpectedly")
            )
        except Exception as exc:
            if self._state >= _State.STOPPING:
                return
            self._listener.on_fail(
                None, ASRError(ERR_READ_FAILED, f"read message failed: {exc}")
            )
        finally:
            await self._close()

    def _dispatch_event(self, resp: SpeechRecognitionResponse) -> None:
        slice_type = resp.result.slice_type
        if slice_type == 0:
            self._listener.on_sentence_begin(resp)
        elif slice_type == 1:
            self._listener.on_recognition_result_change(resp)
        elif slice_type == 2:
            self._listener.on_sentence_end(resp)
        else:
            if resp.final == 1:
                return
            self._listener.on_recognition_start(resp)

    async def _close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
