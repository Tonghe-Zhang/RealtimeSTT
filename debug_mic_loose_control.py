import time
from RealtimeSTT import AudioToTextRecorder

def on_recording_start():
    print("🔴  VAD DETECTED SPEECH - RECORDING...")

def on_recording_stop():
    print("✅  VAD SILENCE - PROCESSING...")

def process_text(text):
    print(f"📝  TRANSCRIPTION: {text}")

if __name__ == '__main__':
    print("Initializing (Switching to WebRTC Engine)...")
    
    recorder = AudioToTextRecorder(
        model="tiny.en",              # Fast model for testing
        webrtc_sensitivity=3,         # Maximum sensitivity
        spinner=True,
        on_recording_start=on_recording_start,
        on_recording_stop=on_recording_stop,
        post_speech_silence_duration=0.5, # Stop recording fast after you stop talking
    )

    print("\n🎤 LISTENING (WebRTC Mode)")
    print("Say 'Hello testing one two three'")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            recorder.text(process_text)
    except KeyboardInterrupt:
        print("Exiting...")
        recorder.shutdown()