"""Tests for SentenceRecognizer."""

import base64
import json

import pytest

from trtc_asr.credential import Credential
from trtc_asr.errors import ASRError, ERR_INVALID_PARAM, ERR_SERVER_ERROR
from trtc_asr.sentence_recognizer import (
    SOURCE_TYPE_DATA,
    SOURCE_TYPE_URL,
    SentenceRecognitionRequest,
    SentenceRecognitionResult,
    SentenceRecognizer,
)


def make_credential():
    return Credential(app_id=1300000000, sdk_app_id=1400000000, secret_key="test-secret")


def make_recognizer():
    return SentenceRecognizer(make_credential())


# ---- Validation tests ----


class TestValidation:
    def test_recognize_data_empty_raises(self):
        r = make_recognizer()
        with pytest.raises(ASRError) as exc_info:
            r.recognize_data(b"", "pcm", "16k_zh")
        assert exc_info.value.code == ERR_INVALID_PARAM

    def test_recognize_data_too_large_raises(self):
        r = make_recognizer()
        with pytest.raises(ASRError) as exc_info:
            r.recognize_data(b"x" * (3 * 1024 * 1024 + 1), "pcm", "16k_zh")
        assert exc_info.value.code == ERR_INVALID_PARAM
        assert "3MB" in exc_info.value.message

    def test_recognize_url_empty_raises(self):
        r = make_recognizer()
        with pytest.raises(ASRError) as exc_info:
            r.recognize_url("", "wav", "16k_zh")
        assert exc_info.value.code == ERR_INVALID_PARAM

    def test_missing_engine_raises(self):
        r = make_recognizer()
        req = SentenceRecognitionRequest(
            eng_service_type="",
            source_type=SOURCE_TYPE_DATA,
            voice_format="pcm",
            data="abc",
            data_len=3,
        )
        with pytest.raises(ASRError) as exc_info:
            r.recognize(req)
        assert exc_info.value.code == ERR_INVALID_PARAM
        assert "eng_service_type" in exc_info.value.message

    def test_missing_voice_format_raises(self):
        r = make_recognizer()
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_DATA,
            voice_format="",
            data="abc",
            data_len=3,
        )
        with pytest.raises(ASRError) as exc_info:
            r.recognize(req)
        assert exc_info.value.code == ERR_INVALID_PARAM
        assert "voice_format" in exc_info.value.message

    def test_url_source_missing_url_raises(self):
        r = make_recognizer()
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_URL,
            voice_format="wav",
            url="",
        )
        with pytest.raises(ASRError) as exc_info:
            r.recognize(req)
        assert exc_info.value.code == ERR_INVALID_PARAM
        assert "url" in exc_info.value.message

    def test_data_source_missing_data_raises(self):
        r = make_recognizer()
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_DATA,
            voice_format="pcm",
            data="",
        )
        with pytest.raises(ASRError) as exc_info:
            r.recognize(req)
        assert exc_info.value.code == ERR_INVALID_PARAM
        assert "data" in exc_info.value.message


# ---- Request building tests ----


class TestRequestBuilding:
    def test_to_dict_data_source(self):
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh_en",
            source_type=SOURCE_TYPE_DATA,
            voice_format="pcm",
            data="base64data",
            data_len=100,
        )
        d = req.to_dict()
        assert d["EngSerViceType"] == "16k_zh_en"
        assert d["SourceType"] == 1
        assert d["Data"] == "base64data"
        assert d["DataLen"] == 100
        assert "Url" not in d

    def test_to_dict_url_source(self):
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_URL,
            voice_format="wav",
            url="https://example.com/test.wav",
        )
        d = req.to_dict()
        assert d["Url"] == "https://example.com/test.wav"
        assert "Data" not in d
        assert "DataLen" not in d

    def test_to_dict_optional_fields(self):
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_DATA,
            voice_format="pcm",
            data="abc",
            data_len=3,
            word_info=2,
            filter_dirty=1,
            hotword_id="hw-001",
        )
        d = req.to_dict()
        assert d["WordInfo"] == 2
        assert d["FilterDirty"] == 1
        assert d["HotwordId"] == "hw-001"

    def test_to_dict_omits_defaults(self):
        req = SentenceRecognitionRequest(
            eng_service_type="16k_zh",
            source_type=SOURCE_TYPE_DATA,
            voice_format="pcm",
            data="abc",
            data_len=3,
        )
        d = req.to_dict()
        assert "WordInfo" not in d
        assert "FilterDirty" not in d
        assert "HotwordId" not in d


# ---- Result parsing tests ----


class TestResultParsing:
    def test_from_dict_basic(self):
        data = {
            "Result": "hello world",
            "AudioDuration": 2500,
            "WordSize": 0,
            "WordList": None,
            "RequestId": "req-123",
        }
        result = SentenceRecognitionResult.from_dict(data)
        assert result.result == "hello world"
        assert result.audio_duration == 2500
        assert result.request_id == "req-123"
        assert result.word_list == []

    def test_from_dict_with_words(self):
        data = {
            "Result": "hello",
            "AudioDuration": 1000,
            "WordSize": 1,
            "WordList": [{"Word": "hello", "StartTime": 0, "EndTime": 500}],
            "RequestId": "req-456",
        }
        result = SentenceRecognitionResult.from_dict(data)
        assert len(result.word_list) == 1
        assert result.word_list[0].word == "hello"
        assert result.word_list[0].start_time == 0
        assert result.word_list[0].end_time == 500
