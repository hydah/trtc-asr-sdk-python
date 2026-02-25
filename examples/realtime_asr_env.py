"""Example: Real-time speech recognition with environment variable configuration.

Set the following environment variables:

    export TRTC_APP_ID="1300403317"
    export TRTC_SDK_APP_ID="1400188366"
    export TRTC_SECRET_KEY="your-sdk-secret-key"

Then run:

    python realtime_asr_env.py -f audio.pcm
"""

import argparse
import asyncio
import logging
import os
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

ENV_APP_ID = "TRTC_APP_ID"
ENV_SDK_APP_ID = "TRTC_SDK_APP_ID"
ENV_SECRET_KEY = "TRTC_SECRET_KEY"

SLICE_SIZE = 6400


class ASRListener(SpeechRecognitionListener):
    def __init__(self, worker_id: int) -> None:
        self.id = worker_id

    def on_recognition_start(self, response: SpeechRecognitionResponse) -> None:
        log.info("[Worker-%d] Recognition started | voice_id=%s", self.id, response.voice_id)

    def on_sentence_begin(self, response: SpeechRecognitionResponse) -> None:
        log.info("[Worker-%d] Sentence begin | index=%d", self.id, response.result.index)

    def on_recognition_result_change(self, response: SpeechRecognitionResponse) -> None:
        log.info(
            '[Worker-%d] Intermediate result | index=%d text="%s"',
            self.id,
            response.result.index,
            response.result.voice_text_str,
        )

    def on_sentence_end(self, response: SpeechRecognitionResponse) -> None:
        log.info(
            '[Worker-%d] Sentence end | index=%d text="%s"',
            self.id,
            response.result.index,
            response.result.voice_text_str,
        )

    def on_recognition_complete(self, response: SpeechRecognitionResponse) -> None:
        log.info("[Worker-%d] Recognition complete | voice_id=%s", self.id, response.voice_id)

    def on_fail(self, response: Optional[SpeechRecognitionResponse], error: Exception) -> None:
        if response is not None:
            log.error(
                "[Worker-%d] ERROR | voice_id=%s code=%d msg=%s err=%s",
                self.id,
                response.voice_id,
                response.code,
                response.message,
                error,
            )
        else:
            log.error("[Worker-%d] ERROR | err=%s", self.id, error)


async def process(
    worker_id: int, file_path: str, app_id: int, sdk_app_id: int, secret_key: str, engine: str
) -> None:
    cred = Credential(app_id, sdk_app_id, secret_key)
    listener = ASRListener(worker_id)
    recognizer = SpeechRecognizer(cred, engine, listener)

    log.info("[Worker-%d] Starting recognition...", worker_id)
    try:
        await recognizer.start()
    except Exception as exc:
        log.error("[Worker-%d] Start failed: %s", worker_id, exc)
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
        log.error("[Worker-%d] Write error: %s", worker_id, exc)

    try:
        await recognizer.stop()
    except Exception as exc:
        log.error("[Worker-%d] Stop error: %s", worker_id, exc)

    log.info("[Worker-%d] Done.", worker_id)


async def main() -> None:
    parser = argparse.ArgumentParser(description="TRTC Real-time ASR (env config)")
    parser.add_argument("-f", "--file", default="test.pcm", help="PCM audio file path")
    parser.add_argument("-e", "--engine", default="16k_zh", help="Engine model type")
    parser.add_argument("-c", "--concurrency", type=int, default=1, help="Concurrent sessions")
    parser.add_argument("-l", "--loop", action="store_true", help="Loop mode")
    args = parser.parse_args()

    app_id_str = os.environ.get(ENV_APP_ID, "")
    sdk_app_id_str = os.environ.get(ENV_SDK_APP_ID, "")
    secret_key = os.environ.get(ENV_SECRET_KEY, "")

    if not app_id_str or not sdk_app_id_str or not secret_key:
        print(
            f"Error: Missing required environment variables.\n\n"
            f"Please set the following environment variables:\n\n"
            f'  export {ENV_APP_ID}="your-tencent-cloud-appid"\n'
            f'  export {ENV_SDK_APP_ID}="your-trtc-sdk-app-id"\n'
            f'  export {ENV_SECRET_KEY}="your-sdk-secret-key"\n\n'
            f"How to obtain:\n"
            f"  1. Get APPID from CAM Console: https://console.cloud.tencent.com/cam/capi\n"
            f"  2. Open TRTC Console:  https://console.cloud.tencent.com/trtc/app\n"
            f"  3. Create or select an application\n"
            f"  4. Copy SDKAppID and SDK secret key from the application overview page\n",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        app_id = int(app_id_str)
    except ValueError:
        print(f"Invalid {ENV_APP_ID}: {app_id_str} (must be integer)", file=sys.stderr)
        sys.exit(1)

    try:
        sdk_app_id = int(sdk_app_id_str)
    except ValueError:
        print(f"Invalid {ENV_SDK_APP_ID}: {sdk_app_id_str} (must be integer)", file=sys.stderr)
        sys.exit(1)

    while True:
        tasks = [
            process(i, args.file, app_id, sdk_app_id, secret_key, args.engine)
            for i in range(args.concurrency)
        ]
        await asyncio.gather(*tasks)
        if not args.loop:
            break
        await asyncio.sleep(1.0)


if __name__ == "__main__":
    asyncio.run(main())
