import os
import shutil
import subprocess
from celery import Celery
from basic_pitch.inference import predict
import pretty_midi

app = Celery(
    'anotate_worker',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://redis:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://redis:6379/0')
)

def append_midi_track(pm_container, audio_path, instrument_name, is_bass=False):
    """Runs transcription on a specific stem and appends it as an instrument track."""
    if not os.path.exists(audio_path):
        return
    
    print(f"Transcribing {instrument_name} stem...")
    
    # Adjust thresholds based on stem type
    frame_thresh = 0.4 if is_bass else 0.3
    
    # Run Spotify Basic Pitch
    _, midi_data, _ = predict(
        audio_path,
        frame_threshold=frame_thresh,
        minimum_note_length=120 if is_bass else 100
    )
    
    # Create a distinct instrument track
    program = 32 if is_bass else 0 # 32 is Acoustic Bass, 0 is Acoustic Grand Piano
    instrument = pretty_midi.Instrument(program=program, name=instrument_name)
    
    # Extract note data and copy it into our master container
    for track in midi_data.instruments:
        for note in track.notes:
            instrument.notes.append(note)
            
    pm_container.instruments.append(instrument)

@app.task(bind=True, name="process_audio_to_midi")
def process_audio_to_midi(self, input_audio_path: str, output_midi_path: str):
    base_name = os.path.splitext(os.path.basename(input_audio_path))[0]
    stem_dir = f"separated/htdemucs/{base_name}"
    
    try:
        # STEP 1: RUN DEMUCS SEPARATION
        print(f"[{self.request.id}] Launching Demucs stem separation...")
        subprocess.run(["demucs", "-o", "/app/media/separated", input_audio_path], check=True)

        stem_dir = f"/app/media/separated/htdemucs/{base_name}"
        
        # STEP 2: GENERATE INDIVIDUAL MIDIS
        print(f"[{self.request.id}] Transcribing individual stems to MIDI...")
        
        pm_vocals = pretty_midi.PrettyMIDI()
        append_midi_track(pm_vocals, f"{stem_dir}/vocals.wav", "Vocal Melody", is_bass=False)
        pm_vocals.write(f"/app/media/{base_name}_vocals.mid")

        pm_bass = pretty_midi.PrettyMIDI()
        append_midi_track(pm_bass, f"{stem_dir}/bass.wav", "Bassline", is_bass=True)
        pm_bass.write(f"/app/media/{base_name}_bass.mid")

        pm_chords = pretty_midi.PrettyMIDI()
        append_midi_track(pm_chords, f"{stem_dir}/other.wav", "Harmonics/Chords", is_bass=False)
        pm_chords.write(f"/app/media/{base_name}_other.mid")

        # STEP 3: CREATE THE MULTI-TRACK MASTER MIDI
        pm_master = pretty_midi.PrettyMIDI()
        append_midi_track(pm_master, f"{stem_dir}/other.wav", "Harmonics/Chords", is_bass=False)
        append_midi_track(pm_master, f"{stem_dir}/bass.wav", "Bassline", is_bass=True)
        append_midi_track(pm_master, f"{stem_dir}/vocals.wav", "Vocal Melody", is_bass=False)
        
        pm_master.write(output_midi_path)
        print(f"[{self.request.id}] Extraction complete.")

        return {"status": "success", "midi_file": output_midi_path}

    except Exception as e:
        print(f"[{self.request.id}] Pipeline failed: {str(e)}")
        return {"status": "error", "message": str(e)}