# Background Music Asset

Place an optional royalty-free background music file named `music.mp3` in this folder:

```
assets/
  music.mp3
  README.md
```

### Audio Requirements & Guidelines
- **Format**: MP3 (or WAV / OGG)
- **Filename**: `music.mp3`
- **Style**: Calm, ambient, corporate, or acoustic background music
- **Volume mixing**: The video engine automatically loops or trims this audio and attenuates its volume to ~12% (-18 dB) under the voice narration so the spoken tour details remain crystal clear.
- **Missing File Handling**: If `music.mp3` is not present, the app skips background music silently or with a polite note without crashing.
