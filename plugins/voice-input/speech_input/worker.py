"""Optional private CPU worker owned by the voice plugin."""
import base64
import json
import os
from pathlib import Path
import sys
import time

# Embedded CPython's ._pth does not add a launched script's directory to sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech_input.protocol import LANGUAGES, MAX_AUDIO_BYTES, validate_wave


def main():
    # The protocol owns stdout; native diagnostics continue to use stderr.
    protocol_out = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
    import numpy as np
    import sherpa_onnx

    root = Path(sys.argv[1])
    recognizer = None
    selected = None

    def load(language):
        return sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(root / "model.int8.onnx"), tokens=str(root / "tokens.txt"),
            num_threads=2, language=language, use_itn=True, provider="cpu", debug=False,
        )

    recognizer = load("auto")
    selected = "auto"
    config = sherpa_onnx.VadModelConfig()
    config.silero_vad.model = str(root / "silero_vad.onnx")
    config.silero_vad.threshold = 0.5
    config.silero_vad.min_silence_duration = 0.5
    config.silero_vad.min_speech_duration = 0.25
    config.silero_vad.max_speech_duration = 30
    config.sample_rate = 16000
    config.num_threads = 2
    config.provider = "cpu"
    detector = sherpa_onnx.VoiceActivityDetector(config, buffer_size_in_seconds=32)
    print(json.dumps({"ready": True}), file=protocol_out)
    limit = ((MAX_AUDIO_BYTES + 2) // 3) * 4 + 1024
    while True:
        line = sys.stdin.buffer.readline(limit + 1)
        if not line:
            return
        if len(line) > limit or not line.endswith(b"\n"):
            raise ValueError("Worker input exceeds limit")
        request = json.loads(line)
        language = request["language"]
        if language not in LANGUAGES:
            raise ValueError("Invalid language")
        audio = base64.b64decode(request["audio"], validate=True)
        seconds = validate_wave(audio)
        if selected != language:
            recognizer = load(language)
            selected = language
        samples = np.frombuffer(audio, dtype="<i2", offset=44).astype(np.float32) / 32768
        detector.reset()
        texts = []
        started = time.monotonic()

        def drain():
            while not detector.empty():
                stream = recognizer.create_stream()
                stream.accept_waveform(16000, detector.front.samples)
                detector.pop()
                recognizer.decode_stream(stream)
                texts.append(stream.result.text.strip())

        window = config.silero_vad.window_size
        for offset in range(0, len(samples), window):
            block = samples[offset:offset + window]
            if len(block) < window:
                block = np.pad(block, (0, window - len(block)))
            detector.accept_waveform(block)
            drain()
        detector.flush()
        drain()
        result = {"text": " ".join(filter(None, texts)), "audioSeconds": seconds,
                  "inferenceSeconds": time.monotonic() - started}
        print(json.dumps(result, ensure_ascii=True), file=protocol_out)


if __name__ == "__main__":
    main()
