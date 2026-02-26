# TRTC-ASR Python SDK

基于 TRTC 鉴权体系的语音识别（ASR）Python SDK，支持实时语音识别（WebSocket）、一句话识别（HTTP）和录音文件识别（异步 HTTP）三种模式。

> 其他语言 SDK：[Go](https://github.com/hydah/trtc-asr-sdk-go) | [Node.js](https://github.com/hydah/trtc-asr-sdk-nodejs)

## 安装

**集成到你的项目中**（推荐）：

```bash
pip install git+https://github.com/hydah/trtc-asr-sdk-python.git
```

**clone 后运行示例**：

```bash
git clone https://github.com/hydah/trtc-asr-sdk-python.git
cd trtc-asr-sdk-python
pip install -r requirements.txt
```

**要求**：Python >= 3.8

## 快速开始

```python
import asyncio
from trtc_asr import Credential, SpeechRecognizer, SpeechRecognitionListener, SpeechRecognitionResponse

# 实现回调接口
class MyListener(SpeechRecognitionListener):
    def on_recognition_start(self, response: SpeechRecognitionResponse) -> None:
        print(f"Recognition started, voice_id: {response.voice_id}")

    def on_sentence_begin(self, response: SpeechRecognitionResponse) -> None:
        print(f"Sentence begin, index: {response.result.index}")

    def on_recognition_result_change(self, response: SpeechRecognitionResponse) -> None:
        print(f"Result: {response.result.voice_text_str}")

    def on_sentence_end(self, response: SpeechRecognitionResponse) -> None:
        print(f"Sentence end: {response.result.voice_text_str}")

    def on_recognition_complete(self, response: SpeechRecognitionResponse) -> None:
        print(f"Complete, voice_id: {response.voice_id}")

    def on_fail(self, response, error: Exception) -> None:
        print(f"Failed: {error}")

async def main():
    # 1. 创建凭证
    credential = Credential(
        app_id=1300403317,         # 腾讯云 APPID
        sdk_app_id=1400188366,     # TRTC SDKAppID
        secret_key="your-sdk-secret-key",  # SDK密钥
    )

    # 2. 创建识别器
    listener = MyListener()
    recognizer = SpeechRecognizer(credential, "16k_zh", listener)

    # 3. 可选配置
    # recognizer.set_hotword_id("hotword-id")     # 设置热词
    # recognizer.set_vad_silence_time(500)         # VAD 静音时间

    # 4. 启动识别
    await recognizer.start()

    # 5. 发送音频数据
    with open("audio.pcm", "rb") as f:
        while True:
            chunk = f.read(6400)  # 200ms of 16kHz 16bit mono PCM
            if not chunk:
                break
            await recognizer.write(chunk)
            await asyncio.sleep(0.2)  # 模拟实时

    # 6. 停止识别
    await recognizer.stop()

asyncio.run(main())
```

### 一句话识别

```python
from trtc_asr import Credential
from trtc_asr.sentence_recognizer import SentenceRecognizer

# 1. 创建凭证
credential = Credential(
    app_id=0,                      # 腾讯云 APPID
    sdk_app_id=0,                  # TRTC SDKAppID
    secret_key="your-sdk-secret-key",  # SDK密钥
)

# 2. 创建一句话识别器
recognizer = SentenceRecognizer(credential)

# 3. 从本地文件识别（自动 base64 编码）
with open("audio.pcm", "rb") as f:
    data = f.read()
result = recognizer.recognize_data(data, "pcm", "16k_zh_en")

print(f"识别结果: {result.result}")
print(f"音频时长: {result.audio_duration} ms")

    # 或者从 URL 识别
    # result = recognizer.recognize_url("https://example.com/audio.wav", "wav", "16k_zh_en")
```

### 录音文件识别

```python
from trtc_asr import Credential
from trtc_asr.file_recognizer import FileRecognizer

# 1. 创建凭证
credential = Credential(
    app_id=0,                      # 腾讯云 APPID
    sdk_app_id=0,                  # TRTC SDKAppID
    secret_key="your-sdk-secret-key",  # SDK密钥
)

# 2. 创建录音文件识别器
recognizer = FileRecognizer(credential)

# 3. 提交识别任务（本地文件）
with open("audio.wav", "rb") as f:
    data = f.read()
task_id = recognizer.create_task_from_data(data, "16k_zh_en")
print(f"任务已提交: {task_id}")

# 4. 轮询等待结果（默认 1 秒间隔，10 分钟超时）
status = recognizer.wait_for_result(task_id)

print(f"识别结果: {status.result}")
print(f"音频时长: {status.audio_duration:.2f} s")

# 或者从 URL 提交（支持更大文件，≤1GB / ≤12h）
# task_id = recognizer.create_task_from_url("https://example.com/audio.wav", "16k_zh_en")

# 或者自定义轮询间隔（秒）
# status = recognizer.wait_for_result_with_interval(task_id, 2.0, 1800.0)
```

## 前提条件

使用本 SDK 前，您需要：

1. **获取腾讯云 APPID** — 在 [CAM API 密钥管理](https://console.cloud.tencent.com/cam/capi) 页面查看
2. **创建 TRTC 应用** — 在 [实时音视频控制台](https://console.cloud.tencent.com/trtc/app) 创建应用，获取 `SDKAppID`
3. **获取 SDK 密钥** — 在应用概览页点击「SDK密钥」查看密钥，即用于计算 UserSig 的加密密钥

## 凭证获取

| 参数 | 来源 | 说明 |
|------|------|------|
| `app_id` | [CAM 密钥管理](https://console.cloud.tencent.com/cam/capi) | 腾讯云账号 APPID，用于 URL 路径 |
| `sdk_app_id` | [TRTC 控制台](https://console.cloud.tencent.com/trtc/app) > 应用管理 | TRTC 应用 ID |
| `secret_key` | [TRTC 控制台](https://console.cloud.tencent.com/trtc/app) > 应用概览 > SDK密钥 | 用于生成 UserSig，不会传输到网络 |

## 配置项

| 方法 | 说明 | 默认值 |
|------|------|--------|
| `set_voice_format(f)` | 音频格式 | 1 (PCM) |
| `set_need_vad(v)` | 是否开启 VAD | 1 (开启) |
| `set_convert_num_mode(m)` | 数字转换模式 | 1 (智能) |
| `set_hotword_id(id)` | 热词表 ID | - |
| `set_customization_id(id)` | 自学习模型 ID | - |
| `set_filter_dirty(m)` | 脏词过滤 | 0 (关闭) |
| `set_filter_modal(m)` | 语气词过滤 | 0 (关闭) |
| `set_filter_punc(m)` | 句号过滤 | 0 (关闭) |
| `set_word_info(m)` | 词级时间 | 0 (关闭) |
| `set_vad_silence_time(ms)` | VAD 静音阈值 | 1000ms |
| `set_max_speak_time(ms)` | 强制断句时间 | 60000ms |
| `set_voice_id(id)` | 自定义 voice_id | 自动 UUID |

## 引擎模型

| 类型 | 说明 |
|------|------|
| `8k_zh` | 中文通用，常用于电话场景 |
| `16k_zh` | 中文通用（推荐） |
| `16k_zh_en` | 中英文通用 |

## 示例

完整示例请参见：

- **实时语音识别**：[`examples/realtime_asr.py`](./examples/realtime_asr.py) — WebSocket 流式识别
- **一句话识别**：[`examples/sentence_asr.py`](./examples/sentence_asr.py) — HTTP 短音频识别（≤60s）
- **录音文件识别**：[`examples/file_asr.py`](./examples/file_asr.py) — 异步长音频识别

运行示例：

```bash
git clone https://github.com/hydah/trtc-asr-sdk-python.git
cd trtc-asr-sdk-python
pip install -r requirements.txt

# 实时语音识别
python examples/realtime_asr.py -f examples/test.pcm

# 一句话识别
python examples/sentence_asr.py -f examples/test.pcm

# 录音文件识别
python examples/file_asr.py -f examples/test.wav

# 查看所有选项
python examples/realtime_asr.py -h
python examples/sentence_asr.py -h
```

## 项目结构

```
trtc-asr-sdk-python/
├── trtc_asr/                       # 包源码
│   ├── __init__.py                 # 包入口，统一导出
│   ├── credential.py               # 凭证管理（APPID + SDKAppID + SDK密钥）
│   ├── usersig.py                  # TRTC UserSig 生成
│   ├── signature.py                # URL 请求参数构建
│   ├── speech_recognizer.py        # 实时语音识别器（WebSocket）
│   ├── sentence_recognizer.py      # 一句话识别器（HTTP）
│   ├── file_recognizer.py          # 录音文件识别器（异步 HTTP）
│   └── errors.py                   # 错误定义
├── examples/                       # 示例代码
│   ├── test.pcm                    # 测试音频文件
│   ├── realtime_asr.py             # 实时语音识别示例
│   ├── sentence_asr.py             # 一句话识别示例
│   └── file_asr.py                 # 录音文件识别示例
├── tests/                          # 测试
│   ├── test_signature.py           # 签名参数测试
│   ├── test_recognizer_lifecycle.py # 生命周期健壮性测试
│   ├── test_sentence_recognizer.py # 一句话识别测试
│   └── test_file_recognizer.py     # 录音文件识别测试
├── pyproject.toml                  # 包定义
├── setup.py                        # 兼容安装
└── .gitignore
```

## 常见问题

### APPID 和 SDKAppID 有什么区别？

- **APPID**（如 `13xxxxxxxx`）：腾讯云账号级别的 ID，从 [CAM 密钥管理](https://console.cloud.tencent.com/cam/capi) 获取，用于 WebSocket URL 路径
- **SDKAppID**（如 `14xxxxxxxx`）：TRTC 应用级别的 ID，从 [TRTC 控制台](https://console.cloud.tencent.com/trtc/app) 获取，用于 Header 鉴权

### UserSig 是什么？

UserSig 是基于 SDKAppID 和 SDK 密钥计算的签名，用于 TRTC 服务鉴权。SDK 会自动生成，无需手动计算。详见[鉴权文档](https://cloud.tencent.com/document/product/647/17275)。

### 支持哪些音频格式？

- **实时语音识别**：支持 PCM 格式（`voice_format=1`），建议 16kHz、16bit、单声道
- **一句话识别**：支持 wav、pcm、ogg-opus、mp3、m4a，音频时长 ≤ 60s，文件 ≤ 3MB
- **录音文件识别**：支持 wav、ogg-opus、mp3、m4a，本地文件 ≤ 5MB，URL ≤ 1GB / ≤ 12h

## License

MIT License
