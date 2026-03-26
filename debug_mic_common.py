#!/usr/bin/env python3
from __future__ import annotations

import array
import math
import os
import re
import shlex
import subprocess
import sys
import threading
import time
from typing import Dict, List, Optional

PREFERRED_SAMPLE_RATES = [16000, 48000, 44100, 32000]
CHUNK = 1024


def ensure_audio_env() -> Dict[str, str]:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    os.environ["XDG_RUNTIME_DIR"] = runtime_dir
    os.environ.setdefault("DBUS_SESSION_BUS_ADDRESS", f"unix:path={runtime_dir}/bus")
    return {
        "XDG_RUNTIME_DIR": os.environ["XDG_RUNTIME_DIR"],
        "DBUS_SESSION_BUS_ADDRESS": os.environ["DBUS_SESSION_BUS_ADDRESS"],
    }


ensure_audio_env()

import pyaudio


BLUE = "\033[94m"
RESET = "\033[0m"
CLEAR_LINE = "\r\033[2K"


class RealtimeMicUI:
    def __init__(self, refresh_seconds: float = 0.05):
        self.refresh_seconds = refresh_seconds
        self.state = "listening"
        self.preview_text = ""
        self.last_final_text = ""
        self.level_rms = 0.0
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._render_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
        with self._lock:
            sys.stdout.write(CLEAR_LINE)
            sys.stdout.flush()

    def on_listening(self, *_args, **_kwargs) -> None:
        with self._lock:
            self.state = "listening"

    def on_recording_start(self, *_args, **_kwargs) -> None:
        with self._lock:
            self.state = "recording"

    def on_recording_stop(self, *_args, **_kwargs) -> None:
        with self._lock:
            self.state = "transcribing"

    def on_transcription_start(self, *_args, **_kwargs) -> None:
        with self._lock:
            self.state = "transcribing"

    def on_audio_chunk(self, data: bytes) -> None:
        rms = self._rms_16bit_pcm(data)
        with self._lock:
            self.level_rms = (0.75 * self.level_rms) + (0.25 * rms)

    def on_preview(self, text: str) -> None:
        text = self._normalize(text)
        with self._lock:
            self.preview_text = text

    def on_final(self, text: str) -> None:
        text = self._normalize(text)
        if not text:
            with self._lock:
                self.preview_text = ""
                self.state = "listening"
            return

        with self._lock:
            if text == self.last_final_text:
                self.preview_text = ""
                self.state = "listening"
                return
            self.last_final_text = text
            self.preview_text = ""
            self.state = "listening"
            sys.stdout.write(f"{CLEAR_LINE}{BLUE}{text}{RESET}\n")
            sys.stdout.flush()

    def _render_loop(self) -> None:
        while self._running:
            with self._lock:
                sys.stdout.write(self._render_line())
                sys.stdout.flush()
            time.sleep(self.refresh_seconds)

    def _render_line(self) -> str:
        icon = "🔴🎤" if self.state == "recording" else "🟢🎤"
        label = "rec" if self.state == "recording" else "listen"
        rms = int(self.level_rms)
        bar_units = max(0, min(18, rms // 250))
        bar = ("█" * bar_units).ljust(18, "·")
        preview = f" {BLUE}{self.preview_text}{RESET}" if self.preview_text else ""
        return f"{CLEAR_LINE}{icon} {label} vol:{rms:4d} |{bar}|{preview}"

    @staticmethod
    def _normalize(text: str) -> str:
        return (text or "").strip()

    @staticmethod
    def _rms_16bit_pcm(data: bytes) -> int:
        samples = array.array("h")
        samples.frombytes(data)
        if sys.byteorder != "little":
            samples.byteswap()
        if not samples:
            return 0
        mean_square = sum(sample * sample for sample in samples) / len(samples)
        return int(math.sqrt(mean_square))


def _run(cmd: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        text=True,
        capture_output=True,
        env=os.environ.copy(),
    )


def _shell(cmd: List[str]) -> str:
    return " ".join(shlex.quote(part) for part in cmd)


def get_default_source_name() -> Optional[str]:
    proc = _run(["pactl", "get-default-source"])
    if proc.returncode != 0:
        return None
    name = proc.stdout.strip()
    return name or None


def _get_short_sources() -> List[Dict[str, str]]:
    proc = _run(["pactl", "list", "short", "sources"])
    if proc.returncode != 0:
        return []

    rows: List[Dict[str, str]] = []
    for line in proc.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append(
                {
                    "id": parts[0].strip(),
                    "name": parts[1].strip(),
                    "driver": parts[2].strip() if len(parts) > 2 else "",
                    "spec": parts[3].strip() if len(parts) > 3 else "",
                    "state": parts[4].strip() if len(parts) > 4 else "",
                }
            )
    return rows


def get_source_details(source_name: Optional[str]) -> Dict[str, Optional[str]]:
    details: Dict[str, Optional[str]] = {
        "name": source_name,
        "id": None,
        "description": None,
        "mute": None,
        "volume": None,
        "alsa_card": None,
        "alsa_device": None,
    }
    if not source_name:
        return details

    for row in _get_short_sources():
        if row["name"] == source_name:
            details["id"] = row["id"]
            break

    proc = _run(["pactl", "list", "sources"])
    if proc.returncode != 0:
        return details

    blocks = re.split(r"\n(?=Source #)", proc.stdout)
    for block in blocks:
        if f"Name: {source_name}" not in block:
            continue

        def grab(pattern: str) -> Optional[str]:
            match = re.search(pattern, block, re.MULTILINE)
            return match.group(1).strip() if match else None

        details["description"] = grab(r"^\s*Description:\s*(.+)$")
        details["mute"] = grab(r"^\s*Mute:\s*(.+)$")
        details["volume"] = grab(r"^\s*Volume:\s*(.+)$")
        details["alsa_card"] = grab(r'^\s*alsa\.card = "([^"]+)"$')
        details["alsa_device"] = grab(r'^\s*alsa\.device = "([^"]+)"$')
        break

    return details


def print_shell_commands(source: Dict[str, Optional[str]]) -> None:
    env = ensure_audio_env()
    print("\nUse these shell commands:")
    print(f"export XDG_RUNTIME_DIR={env['XDG_RUNTIME_DIR']}")
    print(f"export DBUS_SESSION_BUS_ADDRESS={env['DBUS_SESSION_BUS_ADDRESS']}")
    print("wpctl set-mute @DEFAULT_AUDIO_SOURCE@ 0")
    print("wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 1.0")
    if source.get("alsa_card") is not None:
        print(f"amixer -c {source['alsa_card']} sset Mic 100% cap")
        print(f"amixer -c {source['alsa_card']} sget Mic")


def configure_default_source(source: Dict[str, Optional[str]], verbose: bool = True) -> None:
    commands: List[List[str]] = [
        ["wpctl", "set-mute", "@DEFAULT_AUDIO_SOURCE@", "0"],
        ["wpctl", "set-volume", "@DEFAULT_AUDIO_SOURCE@", "1.0"],
    ]

    card = source.get("alsa_card")
    for cmd in commands:
        proc = _run(cmd)
        if verbose:
            print(f"$ {_shell(cmd)}")
            if proc.stdout.strip():
                print(proc.stdout.strip())
            if proc.returncode != 0 and proc.stderr.strip():
                print(proc.stderr.strip())

    if card is None:
        return

    amixer_commands = [
        ["amixer", "-c", str(card), "sset", "Mic", "100%", "cap"],
        ["amixer", "-c", str(card), "sset", "Capture", "100%", "cap"],
    ]
    for cmd in amixer_commands:
        proc = _run(cmd)
        if verbose:
            print(f"$ {_shell(cmd)}")
            if proc.stdout.strip():
                print(proc.stdout.strip())
            if proc.returncode != 0 and proc.stderr.strip():
                print(proc.stderr.strip())
        if proc.returncode == 0:
            break


def _input_devices(pa: pyaudio.PyAudio) -> List[dict]:
    devices = []
    for index in range(pa.get_device_count()):
        info = pa.get_device_info_by_index(index)
        if info.get("maxInputChannels", 0) > 0:
            devices.append(info)
    return devices


def _default_input(pa: pyaudio.PyAudio) -> Optional[dict]:
    try:
        return pa.get_default_input_device_info()
    except Exception:
        return None


def _candidate_devices(default_input: Optional[dict], devices: List[dict], source: Dict[str, Optional[str]]) -> List[dict]:
    candidates: List[dict] = []
    seen = set()
    default_index = default_input["index"] if default_input else None
    source_tokens = " ".join(
        value.lower()
        for value in [source.get("name"), source.get("description")]
        if value
    )

    def add(info: dict) -> None:
        if info["index"] not in seen:
            candidates.append(info)
            seen.add(info["index"])

    for info in devices:
        if info["index"] == default_index:
            add(info)

    for preferred_name in ("default", "pipewire", "pulse"):
        for info in devices:
            if info["name"].lower() == preferred_name:
                add(info)

    for info in devices:
        name = info["name"].lower()
        if source_tokens and any(token in name for token in source_tokens.split()):
            add(info)

    for info in devices:
        name = info["name"].lower()
        if any(token in name for token in ("amazon", "usb", "mic")):
            add(info)

    for info in devices:
        add(info)

    return candidates


def choose_working_input(verbose: bool = True) -> Dict[str, object]:
    ensure_audio_env()
    source_name = get_default_source_name()
    source = get_source_details(source_name)
    configure_default_source(source, verbose=verbose)

    pa = pyaudio.PyAudio()
    try:
        default_input = _default_input(pa)
        devices = _input_devices(pa)
        candidates = _candidate_devices(default_input, devices, source)

        if verbose:
            print("\nDetected default source:")
            print(f"- source: {source.get('name')}")
            print(f"- description: {source.get('description')}")
            print(f"- source id: {source.get('id')}")
            print(f"- ALSA card/device: {source.get('alsa_card')} / {source.get('alsa_device')}")
            if default_input:
                print(f"- PyAudio default input: [{default_input['index']}] {default_input['name']}")

            print("\nPyAudio input devices:")
            for info in devices:
                print(
                    f"  [{info['index']}] {info['name']} "
                    f"(in={info['maxInputChannels']}, default_rate={info['defaultSampleRate']})"
                )

        errors: List[str] = []
        for info in candidates:
            for rate in PREFERRED_SAMPLE_RATES:
                try:
                    stream = pa.open(
                        format=pyaudio.paInt16,
                        channels=1,
                        rate=rate,
                        input=True,
                        frames_per_buffer=CHUNK,
                        input_device_index=info["index"],
                    )
                    stream.close()
                    recorder_input_index = info["index"]
                    if info["name"].lower() in ("default", "pipewire", "pulse"):
                        recorder_input_index = None
                    result = {
                        "source": source,
                        "default_input": default_input,
                        "selected_device_index": info["index"],
                        "selected_device_name": info["name"],
                        "selected_sample_rate": rate,
                        "recorder_input_device_index": recorder_input_index,
                        "devices": devices,
                    }
                    if verbose:
                        print("\nSelected working input:")
                        print(f"- PyAudio device: [{info['index']}] {info['name']}")
                        print(f"- sample rate: {rate}")
                        if recorder_input_index is None:
                            print("- RealtimeSTT will use input_device_index=None (recommended)")
                        else:
                            print(f"- RealtimeSTT will use input_device_index={recorder_input_index}")
                        print_shell_commands(source)
                    return result
                except Exception as exc:
                    errors.append(f"[{info['index']}] {info['name']} @ {rate} Hz -> {exc}")

        raise RuntimeError("No working microphone input found.\n" + "\n".join(errors[:20]))
    finally:
        pa.terminate()
