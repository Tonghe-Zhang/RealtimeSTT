import audioop
import pyaudio

from debug_mic_common import choose_working_input

stream = None
p = None

try:
    print("Initializing microphone volume meter...")
    mic = choose_working_input(verbose=True)
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=mic["selected_sample_rate"],
        input=True,
        frames_per_buffer=1024,
        input_device_index=mic["selected_device_index"],
    )

    print("\n🎤 MICROPHONE TEST")
    print("---------------------------------")
    print(f"Using [{mic['selected_device_index']}] {mic['selected_device_name']}")
    print(f"Sample rate: {mic['selected_sample_rate']}")
    print("Talk into the mic. You should see bars move.")
    print("Press Ctrl+C to stop.\n")

    while True:
        data = stream.read(1024, exception_on_overflow=False)
        rms = audioop.rms(data, 2)
        scale = min(60, int(rms / 150))
        bar = "█" * scale
        print(f"\rVolume: {rms:05d} |{bar:<60}|", end="", flush=True)

except KeyboardInterrupt:
    print("\n\nDone.")
except Exception as e:
    print(f"\n\n❌ Error: {e}")
    print("The script auto-detects the current default mic, unmutes it, and tests a working rate.")
finally:
    try:
        if stream is not None:
            stream.close()
    finally:
        if p is not None:
            p.terminate()
