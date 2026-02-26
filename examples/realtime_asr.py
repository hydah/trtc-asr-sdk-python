"""Basic example: Real-time speech recognition with hardcoded credentials.

Usage:
    python realtime_asr.py -f test.pcm
    python realtime_asr.py -f test.pcm -e 16k_zh -c 2

Prerequisites:
    1. Get Tencent Cloud APPID: https://console.cloud.tencent.com/cam/capi
    2. Create a TRTC application: https://console.cloud.tencent.com/trtc/app
    3. Get SDKAppID and SDK secret key from the application overview page
    4. Prepare a PCM audio file (16kHz, 16bit, mono)
"""

import argparse
import asyncio
import logging
import sys
from typing import Optional

from trtc_asr import (
    Credential,
    SpeechRecognizer,
    SpeechRecognitionListener,
    SpeechRecognitionResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

# ===== Configuration =====
# Fill in your credentials before running.
APP_ID = 0  # Tencent Cloud APPID
SDK_APP_ID = 0  # TRTC application ID (e.g., 1400188366)
SECRET_KEY = ""  # TRTC SDK secret key

SLICE_SIZE = 6400  # bytes per audio chunk (200ms for 16kHz 16bit mono PCM)


class MyListener(SpeechRecognitionListener):
    def __init__(self, worker_id: int) -> None:
        self.id = worker_id

    def on_recognition_start(self, response: SpeechRecognitionResponse) -> None:
        log.info("[%d] Recognition started, voice_id: %s", self.id, response.voice_id)

    def on_sentence_begin(self, response: SpeechRecognitionResponse) -> None:
        log.info("[%d] Sentence begin, index: %d", self.id, response.result.index)

    def on_recognition_result_change(self, response: SpeechRecognitionResponse) -> None:
        log.info(
            "[%d] Result change, index: %d, text: %s",
            self.id,
            response.result.index,
            response.result.voice_text_str,
        )

    def on_sentence_end(self, response: SpeechRecognitionResponse) -> None:
        log.info(
            "[%d] Sentence end, index: %d, text: %s",
            self.id,
            response.result.index,
            response.result.voice_text_str,
        )

    def on_recognition_complete(self, response: SpeechRecognitionResponse) -> None:
        log.info("[%d] Recognition complete, voice_id: %s", self.id, response.voice_id)

    def on_fail(self, response: Optional[SpeechRecognitionResponse], error: Exception) -> None:
        if response is not None:
            log.error("[%d] Failed, voice_id: %s, error: %s", self.id, response.voice_id, error)
        else:
            log.error("[%d] Failed, error: %s", self.id, error)


async def process_audio(worker_id: int, file_path: str, engine: str) -> None:
    credential = Credential(APP_ID, SDK_APP_ID, SECRET_KEY)
    listener = MyListener(worker_id)
    recognizer = SpeechRecognizer(credential, engine, listener)

    try:
        await recognizer.start()
    except Exception as exc:
        log.error("[%d] Start failed: %s", worker_id, exc)
        return

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(SLICE_SIZE)
                if not chunk:
                    break
                await recognizer.write(chunk)
                await asyncio.sleep(0.2)
    except Exception as exc:
        log.error("[%d] Write error: %s", worker_id, exc)

    try:
        await recognizer.stop()
    except Exception as exc:
        log.error("[%d] Stop error: %s", worker_id, exc)

    log.info("[%d] Processing complete.", worker_id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="TRTC Real-time ASR Example")
    parser.add_argument("-f", "--file", default="test.pcm", help="PCM audio file path")
    parser.add_argument("-e", "--engine", default="16k_zh_en", help="Engine model type")
    parser.add_argument("-c", "--concurrency", type=int, default=1, help="Concurrent sessions")
    parser.add_argument("-l", "--loop", action="store_true", help="Loop mode")
    args = parser.parse_args()

    if APP_ID == 0 or SDK_APP_ID == 0 or not SECRET_KEY:
        print(
            "Error: Please set APP_ID, SDK_APP_ID and SECRET_KEY in the code.\n\n"
            "Steps:\n"
            "  1. Get APPID from CAM Console: https://console.cloud.tencent.com/cam/capi\n"
            "  2. Open TRTC Console: https://console.cloud.tencent.com/trtc/app\n"
            "  3. Create or select an application\n"
            "  4. Copy SDKAppID and SDK secret key from the application overview\n"
            "  5. Fill in the credentials at the top of this file.",
            file=sys.stderr,
        )
        sys.exit(1)

    while True:
        tasks = [
            process_audio(i, args.file, args.engine) for i in range(args.concurrency)
        ]
        await asyncio.gather(*tasks)
        if not args.loop:
            break
        await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
