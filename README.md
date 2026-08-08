# 🎹 aNOTATE

> **Automated Audio-to-Sheetmusic, Audio-to-MIDI & Stem Separation Pipeline**

`aNOTATE` is a containerized music production workspace designed to create sheetmusic midi and stems from a song.

---

## Features

* **AI Stem Isolation:** Separates audio files into isolated stems (Vocals, Bass, Drums, and Other) using Demucs.
* **Smart MIDI Extraction:** Converts audio stems into MIDI using Spotify's `basic-pitch` machine learning model with tuned confidence thresholds to eliminate artifact clutter.
* **Grid-Aware Syncing:** Automatically detects track BPM and downbeat offsets so your stems and MIDI lock straight into your DAW's timeline.
* **Modular Pipeline Interface:**download individual or packaged outputs.


##  Quick Start

 ```bash 
git clone https://github.com/Albertokeroro/anotate.git
cd anotate
docker compose up -d --build
```
3. Open your browser and navigate to:
   http://localhost:3838

4. Upload your track and wait for it to be processed
