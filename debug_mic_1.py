#!/usr/bin/env python3
import logging
import sys

from debug_mic_common import RealtimeMicUI, choose_working_input
from RealtimeSTT import AudioToTextRecorder

if __name__ == '__main__':
    mic = choose_working_input(verbose=False)
    recorder_input_device_index = mic["recorder_input_device_index"]
    ui = RealtimeMicUI()

    recorder = AudioToTextRecorder(
        model="tiny.en",
        language="en",
        input_device_index=recorder_input_device_index,
        spinner=False,
        level=logging.ERROR,
        no_log_file=True,
        use_extended_logging=False,
        enable_realtime_transcription=True,
        use_main_model_for_realtime=True,
        realtime_model_type="tiny.en",
        realtime_processing_pause=0.05,
        init_realtime_after_seconds=0.0,
        on_realtime_transcription_update=ui.on_preview,
        on_realtime_transcription_stabilized=ui.on_preview,
        on_recorded_chunk=ui.on_audio_chunk,
        on_recording_start=ui.on_recording_start,
        on_recording_stop=ui.on_recording_stop,
        on_transcription_start=ui.on_transcription_start,
        silero_sensitivity=0.05,
        silero_use_onnx=True,
        webrtc_sensitivity=3,
        faster_whisper_vad_filter=False,
        post_speech_silence_duration=0.25,
        min_length_of_recording=0.15,
        min_gap_between_recordings=0.0,
        beam_size=1,
        beam_size_realtime=1,
        batch_size=0,
        realtime_batch_size=0,
        ensure_sentence_starting_uppercase=False,
        ensure_sentence_ends_with_period=False,
    )

    try:
        ui.start()
        while True:
            recorder.text(ui.on_final)
            ui.on_listening()
    except KeyboardInterrupt:
        sys.stdout.write("\n")
        sys.stdout.flush()
        recorder.shutdown()
    finally:
        ui.stop()
