"""Async audio file recognition client for TRTC-ASR.

Unlike SentenceRecognizer (one-shot, ≤60s), FileRecognizer handles longer audio
files via an async workflow: submit a task (CreateRecTask), then poll for results
(DescribeTaskStatus).

Usage::

    credential = Credential(app_id, sdk_app_id, secret_key)
    recognizer = FileRecognizer(credential)

    # Submit from local file
    task_id = recognizer.create_task_from_data(data, "16k_zh_en")

    # Poll for result
    result = recognizer.wait_for_result(task_id)
"""

from __future__ import annotations

import base64
import json
import logging
import time
import urllib.request
import urllib.error
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from trtc_asr.credential import Credential
from trtc_asr.errors import (
    ASRError,
    ERR_AUTH_FAILED,
    ERR_CONNECT_FAILED,
    ERR_INVALID_PARAM,
    ERR_READ_FAILED,
    ERR_SERVER_ERROR,
    ERR_TIMEOUT,
)
from trtc_asr.usersig import gen_user_sig

logger = logging.getLogger(__name__)

FILE_ENDPOINT = "https://asr.cloud-rtc.com"

# SourceType constants
SOURCE_TYPE_URL = 0
SOURCE_TYPE_DATA = 1

# TaskStatus constants
TASK_STATUS_WAITING = 0
TASK_STATUS_RUNNING = 1
TASK_STATUS_SUCCESS = 2
TASK_STATUS_FAILED = 3


@dataclass
class CreateRecTaskRequest:
    """JSON request body for creating a file recognition task."""

    engine_model_type: str = ""
    channel_num: int = 1
    res_text_format: int = 1
    source_type: int = SOURCE_TYPE_DATA

    # Conditional fields
    url: str = ""
    data: str = ""
    data_len: int = 0

    # Optional fields
    callback_url: str = ""
    filter_dirty: int = 0
    filter_modal: int = 0
    filter_punc: int = 0
    convert_num_mode: int = 0
    hotword_id: str = ""
    hotword_list: str = ""

    def to_dict(self) -> dict:
        """Convert to JSON body dict matching API field names."""
        d: dict = {
            "EngineModelType": self.engine_model_type,
            "ChannelNum": self.channel_num,
            "ResTextFormat": self.res_text_format,
            "SourceType": self.source_type,
        }

        if self.source_type == SOURCE_TYPE_URL:
            d["Url"] = self.url
        else:
            d["Data"] = self.data
            d["DataLen"] = self.data_len

        if self.callback_url:
            d["CallbackUrl"] = self.callback_url
        if self.filter_dirty:
            d["FilterDirty"] = self.filter_dirty
        if self.filter_modal:
            d["FilterModal"] = self.filter_modal
        if self.filter_punc:
            d["FilterPunc"] = self.filter_punc
        if self.convert_num_mode:
            d["ConvertNumMode"] = self.convert_num_mode
        if self.hotword_id:
            d["HotwordId"] = self.hotword_id
        if self.hotword_list:
            d["HotwordList"] = self.hotword_list

        return d


@dataclass
class SentenceWords:
    """Word-level timing information within a sentence."""

    word: str = ""
    offset_start_ms: int = 0
    offset_end_ms: int = 0


@dataclass
class SentenceDetail:
    """Sentence-level recognition result with word timing."""

    final_sentence: str = ""
    slice_sentence: str = ""
    written_text: str = ""
    start_ms: int = 0
    end_ms: int = 0
    words_num: int = 0
    words: List[SentenceWords] = field(default_factory=list)
    speech_speed: float = 0.0
    silence_time: int = 0


@dataclass
class TaskStatus:
    """Task status and result."""

    rec_task_id: str = ""
    status: int = 0
    status_str: str = ""
    result: str = ""
    error_msg: str = ""
    result_detail: List[SentenceDetail] = field(default_factory=list)
    audio_duration: float = 0.0

    @classmethod
    def from_dict(cls, data: dict) -> "TaskStatus":
        result_detail = []
        for sd in data.get("ResultDetail", []) or []:
            words = [
                SentenceWords(
                    word=w.get("Word", ""),
                    offset_start_ms=w.get("OffsetStartMs", 0),
                    offset_end_ms=w.get("OffsetEndMs", 0),
                )
                for w in sd.get("Words", []) or []
            ]
            result_detail.append(
                SentenceDetail(
                    final_sentence=sd.get("FinalSentence", ""),
                    slice_sentence=sd.get("SliceSentence", ""),
                    written_text=sd.get("WrittenText", ""),
                    start_ms=sd.get("StartMs", 0),
                    end_ms=sd.get("EndMs", 0),
                    words_num=sd.get("WordsNum", 0),
                    words=words,
                    speech_speed=sd.get("SpeechSpeed", 0.0),
                    silence_time=sd.get("SilenceTime", 0),
                )
            )
        return cls(
            rec_task_id=data.get("RecTaskId", ""),
            status=data.get("Status", 0),
            status_str=data.get("StatusStr", ""),
            result=data.get("Result", ""),
            error_msg=data.get("ErrorMsg", ""),
            result_detail=result_detail,
            audio_duration=data.get("AudioDuration", 0.0),
        )


class FileRecognizer:
    """Async audio file recognition client using HTTP POST.

    This client supports two workflows:
      1. Submit local audio data (base64, ≤5MB)
      2. Submit audio URL (≤1GB, ≤12h)

    After submission, poll for results using :meth:`wait_for_result`.
    """

    def __init__(self, credential: Credential) -> None:
        self._credential = credential
        self._endpoint = FILE_ENDPOINT
        self._timeout = 60.0  # seconds

    def set_endpoint(self, endpoint: str) -> None:
        """Override the default API endpoint (for testing)."""
        self._endpoint = endpoint

    def set_timeout(self, timeout: float) -> None:
        """Set HTTP request timeout in seconds."""
        self._timeout = timeout

    def create_task(self, req: CreateRecTaskRequest) -> str:
        """Submit a file recognition task and return the task ID."""
        self._validate_create_request(req)
        resp_data = self._do_request("/v1/CreateRecTask", req.to_dict())

        response = resp_data.get("Response")
        if response is None:
            raise ASRError(ERR_SERVER_ERROR, "empty response from server")

        error = response.get("Error")
        if error:
            raise ASRError(
                ERR_SERVER_ERROR,
                "server error [{}]: {} (RequestId: {})".format(
                    error.get("Code", ""),
                    error.get("Message", ""),
                    response.get("RequestId", ""),
                ),
            )

        data = response.get("Data")
        if not data or not data.get("RecTaskId"):
            raise ASRError(ERR_SERVER_ERROR, "empty RecTaskId in response")

        return data["RecTaskId"]

    def create_task_from_data(
        self, data: bytes, engine_model_type: str
    ) -> str:
        """Submit local audio data for recognition (auto base64 encoding). Max 5MB."""
        if not data:
            raise ASRError(ERR_INVALID_PARAM, "audio data is empty")
        if len(data) > 5 * 1024 * 1024:
            raise ASRError(ERR_INVALID_PARAM, "audio data exceeds 5MB limit")

        req = CreateRecTaskRequest(
            engine_model_type=engine_model_type,
            channel_num=1,
            res_text_format=1,
            source_type=SOURCE_TYPE_DATA,
            data=base64.b64encode(data).decode("ascii"),
            data_len=len(data),
        )
        return self.create_task(req)

    def create_task_from_url(
        self, audio_url: str, engine_model_type: str
    ) -> str:
        """Submit an audio URL for recognition. Audio ≤12h, ≤1GB."""
        if not audio_url:
            raise ASRError(ERR_INVALID_PARAM, "audio URL is empty")

        req = CreateRecTaskRequest(
            engine_model_type=engine_model_type,
            channel_num=1,
            res_text_format=1,
            source_type=SOURCE_TYPE_URL,
            url=audio_url,
        )
        return self.create_task(req)

    def create_task_from_data_with_options(
        self, raw_data: bytes, req: CreateRecTaskRequest
    ) -> str:
        """Submit local audio data with a pre-configured request.

        Data, data_len and source_type are set automatically from raw_data.
        """
        if not raw_data:
            raise ASRError(ERR_INVALID_PARAM, "audio data is empty")
        if len(raw_data) > 5 * 1024 * 1024:
            raise ASRError(ERR_INVALID_PARAM, "audio data exceeds 5MB limit")

        req.source_type = SOURCE_TYPE_DATA
        req.data = base64.b64encode(raw_data).decode("ascii")
        req.data_len = len(raw_data)
        return self.create_task(req)

    def describe_task_status(self, rec_task_id: str) -> TaskStatus:
        """Query the status of a file recognition task."""
        if not rec_task_id:
            raise ASRError(ERR_INVALID_PARAM, "rec_task_id is empty")

        body = {"RecTaskId": rec_task_id}
        resp_data = self._do_request("/v1/DescribeTaskStatus", body)

        response = resp_data.get("Response")
        if response is None:
            raise ASRError(ERR_SERVER_ERROR, "empty response from server")

        error = response.get("Error")
        if error:
            raise ASRError(
                ERR_SERVER_ERROR,
                "server error [{}]: {} (RequestId: {})".format(
                    error.get("Code", ""),
                    error.get("Message", ""),
                    response.get("RequestId", ""),
                ),
            )

        data = response.get("Data")
        if not data:
            raise ASRError(ERR_SERVER_ERROR, "empty response from server")

        return TaskStatus.from_dict(data)

    def wait_for_result(self, rec_task_id: str) -> TaskStatus:
        """Poll for results with default interval (1s) and timeout (10min)."""
        return self.wait_for_result_with_interval(rec_task_id, 1.0, 600.0)

    def wait_for_result_with_interval(
        self, rec_task_id: str, interval: float, timeout: float
    ) -> TaskStatus:
        """Poll for results with custom interval and timeout (in seconds)."""
        deadline = time.monotonic() + timeout

        while True:
            status = self.describe_task_status(rec_task_id)

            if status.status == TASK_STATUS_SUCCESS:
                return status
            if status.status == TASK_STATUS_FAILED:
                raise ASRError(
                    ERR_SERVER_ERROR,
                    "task failed: {} (RecTaskId: {})".format(
                        status.error_msg, status.rec_task_id
                    ),
                )

            if time.monotonic() > deadline:
                raise ASRError(
                    ERR_TIMEOUT,
                    "task not completed within {}s (RecTaskId: {}, Status: {})".format(
                        timeout, rec_task_id, status.status_str
                    ),
                )

            time.sleep(interval)

    def _do_request(self, path: str, body: dict) -> dict:
        """Send an HTTP POST to the given API path with JSON body."""
        request_id = str(uuid.uuid4())

        user_sig = self._credential.user_sig
        if not user_sig:
            try:
                user_sig = gen_user_sig(
                    self._credential.sdk_app_id,
                    self._credential.secret_key,
                    request_id,
                    86400,
                )
            except Exception as e:
                raise ASRError(
                    ERR_AUTH_FAILED, "generate user sig failed: {}".format(e)
                )

        req_url = (
            "{}{}"
            "?AppId={}"
            "&Secretid={}"
            "&RequestId={}"
            "&Timestamp={}".format(
                self._endpoint,
                path,
                self._credential.app_id,
                self._credential.app_id,
                request_id,
                int(time.time()),
            )
        )

        json_body = json.dumps(body).encode("utf-8")

        http_req = urllib.request.Request(
            req_url,
            data=json_body,
            method="POST",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "X-TRTC-SdkAppId": str(self._credential.sdk_app_id),
                "X-TRTC-UserSig": user_sig,
            },
        )

        try:
            with urllib.request.urlopen(http_req, timeout=self._timeout) as resp:
                resp_body = resp.read().decode("utf-8")
                status_code = resp.status
        except urllib.error.HTTPError as e:
            resp_body = e.read().decode("utf-8") if e.fp else ""
            raise ASRError(
                ERR_SERVER_ERROR,
                "http status {}: {}".format(e.code, resp_body),
            )
        except Exception as e:
            raise ASRError(ERR_CONNECT_FAILED, "http request failed: {}".format(e))

        try:
            return json.loads(resp_body)
        except (json.JSONDecodeError, ValueError) as e:
            raise ASRError(ERR_READ_FAILED, "unmarshal response failed: {}".format(e))

    @staticmethod
    def _validate_create_request(req: CreateRecTaskRequest) -> None:
        if req is None:
            raise ASRError(ERR_INVALID_PARAM, "request is None")
        if not req.engine_model_type:
            raise ASRError(ERR_INVALID_PARAM, "engine_model_type is required")
        if req.channel_num <= 0:
            raise ASRError(ERR_INVALID_PARAM, "channel_num must be positive")
        if req.source_type == SOURCE_TYPE_URL and not req.url:
            raise ASRError(ERR_INVALID_PARAM, "url is required when source_type=0")
        if req.source_type == SOURCE_TYPE_DATA and not req.data:
            raise ASRError(ERR_INVALID_PARAM, "data is required when source_type=1")
