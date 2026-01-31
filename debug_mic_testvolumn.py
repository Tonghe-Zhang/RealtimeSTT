import pyaudio
import audioop

try:
    p = pyaudio.PyAudio()
    
    # We ask for the system default input
    # If this crashes, your system default doesn't support 16k, which is a big clue
    stream = p.open(format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    input=True,
                    frames_per_buffer=1024)

    print("\n🎤 MICROPHONE TEST")
    print("---------------------------------")
    print("Yell into the mic. You should see bars move.")
    print("Press Ctrl+C to stop.\n")

    while True:
        data = stream.read(1024, exception_on_overflow=False)
        rms = audioop.rms(data, 2)  # Calculate volume
        
        # Scale the volume to a visual bar
        scale = int(rms / 20)
        bar = "█" * scale
        print(f"\rVolume: {rms:05d} |{bar}", end="")

except KeyboardInterrupt:
    print("\n\nDone.")
except Exception as e:
    print(f"\n\n❌ Error: {e}")
    print("This error means the Default Device doesn't support 16000Hz.")