import pyaudio

# The index you found earlier
DEVICE_INDEX = 7

p = pyaudio.PyAudio()
print(f"Testing rates for Device {DEVICE_INDEX}...")

# Common rates to test
rates = [16000, 32000, 44100, 48000]

for rate in rates:
    try:
        is_supported = p.is_format_supported(
            rate=rate, 
            input_device=DEVICE_INDEX, 
            input_channels=1, 
            input_format=pyaudio.paInt16
        )
        if is_supported:
            print(f"✅ SUPPORTED: {rate} Hz")
    except ValueError:
        print(f"❌ Rejected:  {rate} Hz")

p.terminate()