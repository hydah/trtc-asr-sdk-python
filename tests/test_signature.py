"""Tests for signature parameter building."""

import re

from trtc_asr.signature import SignatureParams


def test_new_signature_params_defaults():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    assert params.app_id == 1300403317
    assert params.engine_model_type == "16k_zh"
    assert params.voice_id == "test-voice-001"
    assert params.voice_format == 1
    assert params.need_vad == 1
    assert params.convert_num_mode == 1
    assert params.timestamp > 0
    assert params.expired == params.timestamp + 86400
    assert 1 <= params.nonce <= 9999999


def test_build_query_string_contains_required_params():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    qs = params.build_query_string()
    assert "secretid=1300403317" in qs
    assert "engine_model_type=16k_zh" in qs
    assert "voice_id=test-voice-001" in qs
    assert "voice_format=1" in qs
    assert "needvad=1" in qs
    assert "signature" not in qs


def test_build_query_string_with_signature():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    user_sig = "eJyrVgrxCdYrLkksyczPs1KyUkqpTM4sSgUAR94HgQ--"
    qs = params.build_query_string_with_signature(user_sig)
    assert "signature=" in qs
    # signature value should be URL-encoded
    assert "secretid=1300403317" in qs


def test_query_string_is_sorted():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    qs = params.build_query_string()
    keys = [part.split("=")[0] for part in qs.split("&")]
    assert keys == sorted(keys)


def test_optional_params_omitted_when_zero():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    qs = params.build_query_string()
    assert "hotword_id" not in qs
    assert "customization_id" not in qs
    assert "filter_dirty" not in qs
    assert "word_info" not in qs
    assert "vad_silence_time" not in qs
    assert "max_speak_time" not in qs


def test_optional_params_included_when_set():
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
        hotword_id="hw-001",
        filter_dirty=1,
        word_info=1,
        vad_silence_time=500,
    )
    qs = params.build_query_string()
    assert "hotword_id=hw-001" in qs
    assert "filter_dirty=1" in qs
    assert "word_info=1" in qs
    assert "vad_silence_time=500" in qs


def test_secret_key_never_in_query():
    """SecretKey should never appear in query parameters."""
    params = SignatureParams(
        app_id=1300403317,
        engine_model_type="16k_zh",
        voice_id="test-voice-001",
    )
    user_sig = "fake-user-sig"
    qs = params.build_query_string_with_signature(user_sig)
    assert "secret_key" not in qs.lower()
    assert "secretkey" not in qs.lower()
