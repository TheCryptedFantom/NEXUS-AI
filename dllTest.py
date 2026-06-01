import torch
from TTS.api import TTS
import os
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.config.shared_configs import BaseDatasetConfig

# Allow the required custom class for safe loading
torch.serialization.add_safe_globals([XttsConfig])

# Device (GPU faster, but CPU works)
device = "cuda" if torch.cuda.is_available() else "cpu"

# Load XTTS-v2
print("Loading XTTS-v2 model...")
tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

# Your 6 reference WAV files (make sure they're clean, 16-24kHz, mono preferred)
REFERENCE_WAVS = [
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_01.wav",
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_02.wav",
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_03.wav",
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_04.wav",
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_05.wav",
    r"C:\NEXUS\voice_wavs\cowboy\cowboy_06.wav",
]

print("Computing portable speaker latents from your 6 references...")

# This averages across all refs for the best possible clone
gpt_cond_latent, speaker_embedding = tts.synthesizer.get_conditioning_latents(
    audio_path=REFERENCE_WAVS
)

# Save as portable .pth file (upload this to GitHub!)
embedding_dict = {
    "gpt_cond_latent": gpt_cond_latent.cpu(),
    "speaker_embedding": speaker_embedding.cpu()
}

save_path = r"C:\NEXUS\tts\cowboy.pth"  # Change to .pt if you prefer
torch.save(embedding_dict, save_path)

print(f"Success! Your portable cowboy voice embedding saved to:\n{save_path}")
print("File size: ~few MB — safe to upload to GitHub.")
print("Others can now clone your NEXUS voice without any WAV files!")