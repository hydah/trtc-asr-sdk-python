from setuptools import setup, find_packages

setup(
    name="trtc-asr",
    version="0.1.0",
    description="Tencent TRTC Real-time ASR SDK for Python",
    python_requires=">=3.8",
    packages=find_packages(include=["trtc_asr*"]),
    install_requires=[
        "websockets>=11.0",
        "tls-sig-api-v2>=1.2",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0",
            "python-dotenv>=1.0",
        ],
    },
    license="MIT",
    keywords=["trtc", "asr", "speech-recognition", "tencent", "real-time"],
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Sound/Audio :: Speech",
    ],
)
