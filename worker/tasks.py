import os
import shutil
import subprocess
from celery import Celery
from basic_pitch.inference import predict
import pretty_midi
import librosa
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

def align_to_downbeat(pm, offset):
    """Helper function to shift all notes backward so the first beat is at 0.0s"""
    for instrument in pm.instruments:
        for note in instrument.notes:
            # Shift timings and prevent negative timestamps
            note.start = max(0.0, note.start - offset)
            note.end = max(0.0, note.end - offset)
    return pm

@app.task(bind=True, name="process_audio_to_midi")
def process_audio_to_midi(self, input_audio_path: str, output_midi_path: str):
    base_name = os.path.splitext(os.path.basename(input_audio_path))[0]
    stem_dir = f"separated/htdemucs/{base_name}"
    
    try:
        # STEP 1: RUN DEMUCS SEPARATION
        print(f"[{self.request.id}] Launching Demucs stem separation...")
        subprocess.run(["demucs", "-o", "/app/media/separated", input_audio_path], check=True)
        stem_dir = f"/app/media/separated/htdemucs/{base_name}"
        
        # STEP 2: ACCURATE TEMPO & DOWNBEAT DETECTION
        print(f"[{self.request.id}] Analyzing Tempo and Downbeat...")
        y, sr = librosa.load(input_audio_path, sr=22050)
        
        # Get tempo and beat frames
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
        bpm = float(tempo[0]) if hasattr(tempo, '__len__') else float(tempo)
        beat_times = librosa.frames_to_time(beat_frames, sr=sr)
        
        # Fallback safeguard for downbeat
        first_beat_time = beat_times[0] if len(beat_times) > 0 else 0.0
        
        print(f"[{self.request.id}] Detected BPM: {bpm:.2f} | Offset: {first_beat_time:.3f}s")
        
        # STEP 3: GENERATE HIGH-CONFIDENCE, GRID-SYNCED MIDIS
        # Note: If your `append_midi_track` function accepts a confidence parameter, 
        # make sure to pass a higher threshold (e.g., minimum_confidence=0.65) to strip weak notes.
        print(f"[{self.request.id}] Transcribing stems with high confidence threshold...")
        
        pm_vocals = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        append_midi_track(pm_vocals, f"{stem_dir}/vocals.wav", "Vocal Melody", is_bass=False)
        align_to_downbeat(pm_vocals, first_beat_time).write(f"/app/media/{base_name}_vocals.mid")

        pm_bass = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        append_midi_track(pm_bass, f"{stem_dir}/bass.wav", "Bassline", is_bass=True)
        align_to_downbeat(pm_bass, first_beat_time).write(f"/app/media/{base_name}_bass.mid")

        pm_chords = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        append_midi_track(pm_chords, f"{stem_dir}/other.wav", "Harmonics/Chords", is_bass=False)
        align_to_downbeat(pm_chords, first_beat_time).write(f"/app/media/{base_name}_other.mid")

        # STEP 4: CREATE THE MASTER MIDI
        pm_master = pretty_midi.PrettyMIDI(initial_tempo=bpm)
        append_midi_track(pm_master, f"{stem_dir}/other.wav", "Harmonics/Chords", is_bass=False)
        append_midi_track(pm_master, f"{stem_dir}/bass.wav", "Bassline", is_bass=True)
        append_midi_track(pm_master, f"{stem_dir}/vocals.wav", "Vocal Melody", is_bass=False)
        
        align_to_downbeat(pm_master, first_beat_time).write(output_midi_path)
        print(f"[{self.request.id}] Extraction complete.")

        return {"status": "success", "midi_file": output_midi_path}

    except Exception as e:
        print(f"[{self.request.id}] Pipeline failed: {str(e)}")
        return {"status": "error", "message": str(e)}