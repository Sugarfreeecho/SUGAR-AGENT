"""Bounded PCM format shared by voice providers and the HTTP controller."""
import struct

MAX_AUDIO_BYTES = 4 * 1024 * 1024
MAX_DURATION_SECONDS = 120
LANGUAGES = ("auto", "zh", "en", "yue", "ja", "ko")


def validate_wave(audio: bytes) -> float:
    """Accept canonical 16 kHz mono PCM16 WAV; return its duration."""
    if not 46 <= len(audio) <= MAX_AUDIO_BYTES:
        raise ValueError("Invalid audio size")
    if (audio[:4] != b"RIFF" or audio[8:16] != b"WAVEfmt "
            or audio[36:40] != b"data"):
        raise ValueError("Expected PCM16 WAV")
    riff_size, = struct.unpack_from("<I", audio, 4)
    fmt_size, codec, channels, rate, byte_rate, align, bits = struct.unpack_from("<IHHIIHH", audio, 16)
    size, = struct.unpack_from("<I", audio, 40)
    if ((fmt_size, codec, channels, rate, byte_rate, align, bits) != (16, 1, 1, 16000, 32000, 2, 16)
            or riff_size != len(audio) - 8 or size != len(audio) - 44 or size % 2
            or size > MAX_DURATION_SECONDS * 32000):
        raise ValueError("Expected at most 120 seconds of 16 kHz mono PCM16 WAV")
    return size / 32000
