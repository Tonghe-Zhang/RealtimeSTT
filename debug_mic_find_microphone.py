from RealtimeSTT import AudioToTextRecorder

def process_text(text):
    print(f"\rRecognized: {text}", end="", flush=True)

if __name__ == '__main__':
    print("Initializing (High Sensitivity Mode)...")
    
    recorder = AudioToTextRecorder(
        spinner=True,
        model="tiny.en",
        # 1. More sensitive voice detection (0.4 is standard, 0.05 is extremely sensitive)
        silero_sensitivity=0.05,
        # 2. Wait less time before deciding you are done talking
        post_speech_silence_duration=0.6,
    )
    
    print("\n🎤 Listening! (Sensitivity Maxed)")
    print("Speak a FULL SENTENCE now.\n")
    
    try:
        while True:
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("\nStopping...")
        recorder.shutdown()