"""Run the shipped speech worker against a local WAV without using a microphone."""
import argparse
import asyncio
import json
from pathlib import Path
import struct
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))
sys.path.insert(0, str(ROOT / 'plugins' / 'voice-input'))
from speech_input.service import SpeechService


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=ROOT / "workspace")
    parser.add_argument("--prepare", action="store_true", help="Download missing pinned models and load the native worker")
    parser.add_argument("--source", choices=("auto", "huggingface", "mirror"), default="auto")
    parser.add_argument("--audio", type=Path, help="16 kHz mono PCM16 WAV; omission tests silence")
    args = parser.parse_args()
    service = SpeechService(args.work_dir)
    # The smoke owns only this in-memory selection, never the user's saved switch.
    service.settings["enabled"] = True
    service.settings["asr"]["provider"] = "local"
    try:
        state = await service.snapshot()
        if args.prepare:
            await service.prepare(args.source)
            last = None
            while not service._preparation.done():
                state = await service.snapshot()
                progress = (state["phase"], state.get("file"), state.get("completedBytes", 0) // (1024 * 1024))
                if progress != last:
                    print(progress, flush=True)
                    last = progress
                await asyncio.sleep(1)
            state = await service.snapshot()
        if state["phase"] != "ready":
            raise RuntimeError("Speech model is not ready: " + str(state))
        if args.audio:
            with wave.open(str(args.audio), "rb") as source:
                if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
                    raise ValueError("Test audio must be 16 kHz mono PCM16")
                pcm = source.readframes(source.getnframes())
        else:
            pcm = b"\0\0" * 16000
        audio = (b"RIFF" + struct.pack("<I", len(pcm) + 36) + b"WAVEfmt "
                 + struct.pack("<IHHIIHH", 16, 1, 1, 16000, 32000, 2, 16)
                 + b"data" + struct.pack("<I", len(pcm)) + pcm)
        result = await service.transcribe(audio, "speech-smoke", "native-smoke")
        print(json.dumps(result, ensure_ascii=True), flush=True)
        if args.audio and not result["text"].strip():
            raise RuntimeError("No speech recognized in the test recording")
        if not args.audio and result["text"].strip():
            raise RuntimeError("Silence unexpectedly produced a transcript")
        print("Native speech smoke passed", flush=True)
    finally:
        await service.close()


if __name__ == "__main__":
    asyncio.run(main())
