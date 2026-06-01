import os
import io
from urllib import response
import wave
import struct
import webbrowser
import tempfile
import pyautogui
from dotenv import load_dotenv
from groq import Groq
import soundfile as sf
from cartesia import Cartesia
import pyaudio
import pvporcupine
import pygame
import numpy as np

# ===================== Load Keys from .env =====================
load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
PORCUPINE_ACCESS_KEY = os.getenv("ACCESS_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")

if not GROQ_API_KEY:
    print("Error: GROQ_API_KEY not found in .env file!")
    exit()
if not PORCUPINE_ACCESS_KEY:
    print("Error: ACCESS_KEY not found in .env file!")
    exit()
if not CARTESIA_API_KEY:
    print("Error: CARTESIA_API_KEY not found in .env file!")
    exit()


# ===================== Clients =====================
groq_client = Groq(api_key=GROQ_API_KEY)
cartesia_client = Cartesia(api_key=CARTESIA_API_KEY)

# ===================== Voice =====================
VOICE_ID = "ed44578d-ffca-4d4e-9d91-4808c8f82990"  # 👈 your cloned voice ID

# Initialize pygame for audio playback
pygame.mixer.init()

def nexus_speak(text):
    print(f"🗣️ NEXUS: {text}\n")

    try:
        response = cartesia_client.tts.generate(
            model_id="sonic-2",
            transcript=text,
            voice={"mode": "id", "id": VOICE_ID},
            output_format={
                "container": "mp3",
                "sample_rate": 44100,
                "bit_rate": 128000
            }
        )

        response.write_to_file("nexus_tts.mp3")

        # 🔴 IMPORTANT: pause wake loop safely
        pygame.mixer.music.load("nexus_tts.mp3")
        pygame.mixer.music.play()

        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(20)

        pygame.mixer.music.unload()

        pygame.time.wait(50)  # small buffer reset

        os.remove("nexus_tts.mp3")

    except Exception as e:
        print(f"Speech error: {e}")

# ===================== Groq Setup =====================
LLM_MODEL = "llama-3.3-70b-versatile"
STT_MODEL = "whisper-large-v3-turbo"

chat_history = [
    {"role": "system", "content": "You are NEXUS, a wise, rustic cowboy-voiced AI assistant. Speak in a calm, folksy, slightly drawling tone with cowboy wisdom. Be helpful, witty, and concise."}
]

# ===================== Microphone Auto-Selection =====================
BLACKLIST_KEYWORDS = [
    "virtual", "vad wave", "voicemod", "hitpaw", "cable", "vb-audio",
    "voice meter", "dubbing", "monitor", "mix", "stereo mix", "what u hear"
]

# ===================== Microphone Selection =====================
def list_input_devices():
    p = pyaudio.PyAudio()
    devices = []
    print("\nAvailable microphones:")
    print("-" * 60)
    
    default_idx = p.get_default_input_device_info()['index']
    
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            name = info['name'].strip()
            is_default = " (default)" if i == default_idx else ""
            print(f" {len(devices):2d} │ {i:2d} │ {name}{is_default}")
            devices.append((i, name))
    
    p.terminate()
    return devices


def choose_microphone():
    devices = list_input_devices()
    
    if not devices:
        print("No input devices found. Exiting.")
        exit()
    
    print("\nEnter the number (left column) of the microphone you want to use")
    print("Just press Enter to use the system default.")
    print()
    
    while True:
        choice = input("Your choice → ").strip()
        
        if choice == "":
            # Use system default
            p_temp = pyaudio.PyAudio()
            default_idx = p_temp.get_default_input_device_info()['index']
            p_temp.terminate()
            print(f"Using system default device (index {default_idx})")
            return default_idx
        
        try:
            num = int(choice)
            if 0 <= num < len(devices):
                chosen_idx, chosen_name = devices[num]
                print(f"Selected: {chosen_name} (index {chosen_idx})")
                return chosen_idx
            else:
                print(f"Number must be between 0 and {len(devices)-1}")
        except ValueError:
            print("Please enter a number or press Enter for default")


# ────────────────────────────────────────────────
# Get chosen microphone index once at startup
chosen_device_index = choose_microphone()

# ===================== Porcupine Wake Word =====================
PPN_FILE = r"C:\NEXUS\porcupine\NEXUS.ppn"
# PV_FILE = None

create_args = {
    "access_key": PORCUPINE_ACCESS_KEY,
    "keyword_paths": [PPN_FILE]
}

print("Model loaded OK")
# if os.path.exists(PV_FILE):
#     create_args["model_path"] = PV_FILE

porcupine = pvporcupine.create(**create_args)

# ===================== Open Audio Stream =====================
p = pyaudio.PyAudio()
stream = None

try:
    print(f"Opening microphone (index {chosen_device_index})...")
    stream = p.open(
    rate=16000,  # 🔥 FORCE standard wake word rate
    channels=1,
    format=pyaudio.paInt16,
    input=True,
    input_device_index=chosen_device_index,
    frames_per_buffer=512  # 🔥 DO NOT use porcupine.frame_length here
)
    print("✅ Microphone opened successfully")
except Exception as e:
    print(f"Failed to open microphone: {e}")
    print("Please check your selection and try again.")
    p.terminate()
    exit()

print("NEXUS is always listening for your wake word...\n")

# ===================== Record Command =====================
def record_full_command():
    print("🎙️ Recording...")

    frames = []
    silent_count = 0
    triggered = False

    for _ in range(500):
        try:
            pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)
        except OSError:
            continue

        frames.append(pcm)

        audio_int = struct.unpack_from("h" * porcupine.frame_length, pcm)

        if max(abs(x) for x in audio_int) > 800:
            silent_count = 0
            triggered = True
        else:
            if triggered:
                silent_count += 1
                if silent_count > 40:
                    break

    print("⏹️ Recording stopped.")

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")

    with wave.open(temp_file.name, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(porcupine.sample_rate)
        wf.writeframes(b''.join(frames))

    return temp_file.name

# ===================== Transcribe =====================
def transcribe_audio(audio_path):
    print("📝 Transcribing...")

    with open(audio_path, "rb") as f:
        transcription = groq_client.audio.transcriptions.create(
            model=STT_MODEL,
            file=("audio.wav", f, "audio/wav"),
            language="en",
            response_format="text"
        )

    return transcription.strip() if isinstance(transcription, str) else transcription.text.strip()

# ===================== Generate Response =====================
def generate_response(user_text):
    chat_history.append({"role": "user", "content": user_text})
    response = groq_client.chat.completions.create(
        model=LLM_MODEL,
        messages=chat_history,
        temperature=0.8,
        max_tokens=1024
    )
    reply = response.choices[0].message.content
    chat_history.append({"role": "assistant", "content": reply})
    return reply

# ===================== Custom Commands =====================
def run_custom_command(text):
    text = text.lower()

    # Open apps
    if "open youtube" in text:
        webbrowser.open("https://www.youtube.com/")
        nexus_speak("Opening YouTube")
        return True
    elif "open music" in text:
        webbrowser.open("https://music.youtube.com/")
        nexus_speak("Opening YouTube Music")
        return True
    elif "open roblox" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Roblox Player.lnk")
        nexus_speak("Opening Roblox")
        return True
    elif "open roblox studio" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Roblox Studio.lnk")
        nexus_speak("Opening Roblox Studio")
        return True
    elif "open steam" in text:
        os.startfile(r"C:\Users\Public\Desktop\Steam.lnk")
        nexus_speak("Opening Steam")
        return True
    elif "open red dead" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Red Dead Redemption 2.url")
        nexus_speak("Opening Red Dead Redemption 2")
        return True
    elif "open discord" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Discord.lnk")
        nexus_speak("Opening Discord")
        return True
    elif "open minecraft" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Minecraft Launcher.lnk")
        nexus_speak("Opening Minecraft")
        return True
    elif "open rocket league" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Rocket League®.url")
        nexus_speak("Opening Rocket League")
        return True
    elif "open jurassic world the game" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Jurassic World™ The Game.lnk")
        nexus_speak("Opening Jurassic World The Mobile Game")
        return True
    elif "open lego star wars" in text:
        os.startfile(r"C:\Users\lifef\Desktop\LEGO® Star Wars™ The Skywalker Saga.url")
        nexus_speak("Opening Lego Star Wars The Skywalker Saga")
        return True
    elif "open netflix" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Netflix.lnk")
        nexus_speak("Opening Netflix")
        return True
    elif "open epic games" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Epic Games Launcher.lnk")
        nexus_speak("Opening Epic Games Launcher")
        return True
    elif "open rockstar games" in text:
        os.startfile(r"C:\Users\Public\Desktop\Epic Games Launcher.lnk")
        nexus_speak("Opening Rockstar Games Launcher")
        return True
    elif "open curseforge" in text:
        os.startfile(r"C:\Users\lifef\Desktop\CurseForge.lnk")
        nexus_speak("Opening Curseforge")
        return True
    elif "open obs" in text:
        os.startfile(r"C:\Users\lifef\Desktop\OBS Studio.lnk")
        nexus_speak("Opening OBS Studio")
        return True
    elif "open grok" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Grok.lnk")
        nexus_speak("Opening Groq AI")
        return True
    elif "open borderlands 2" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Borderlands 2.url")
        nexus_speak("Opening Borderlands 2")
        return True
    elif "open throne and liberty" in text:
        os.startfile(r"C:\Users\lifef\Desktop\THRONE AND LIBERTY.url")
        nexus_speak("Opening Throne and Liberty")
        return True
    elif "open ready or not" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Ready or Not.url")
        nexus_speak("Opening Ready or Not")
        return True
    elif "open blockbench" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Blockbench.lnk")
        nexus_speak("Opening Blockbench")
        return True
    elif "open voicemod" in text:
        os.startfile(r"C:\Users\Public\Desktop\Voicemod V3.lnk")
        nexus_speak("Opening Voicemod")
        return True
    elif "open creality" in text:
        os.startfile(r"C:\Users\Public\Desktop\Creality Print 6.3.lnk")
        nexus_speak("Opening Creality Slicer")
        return True
    elif "open arduino" in text:
        os.startfile(r"C:\Users\lifef\Desktop\Arduino IDE.lnk")
        nexus_speak("Opening Arduino IDE")
        return True
    elif "open gog galaxy" in text:
        os.startfile(r"C:\Users\Public\Desktop\GOG Galaxy.lnk")
        nexus_speak("Opening GOG Galaxy")
        return True
    elif "open google play games" in text:
        os.startfile(r"C:\Users\Public\Desktop\Google Play Games.lnk")
        nexus_speak("Opening Google Play Games")
        return True
    elif "open davinci resolve" in text:
        os.startfile(r"C:\Users\Public\Desktop\DaVinci Resolve.lnk")
        nexus_speak("Opening Davinci Resolve")
        return True

    # Media controls
    if any(p in text for p in ["next", "skip", "next song", "skip song", "next track"]):
        pyautogui.press('nexttrack')
        nexus_speak("Skippin' ahead")
        return True

    if any(p in text for p in ["previous", "back", "previous song"]):
        pyautogui.press('prevtrack')
        nexus_speak("Goin' back one")
        return True

    if any(p in text for p in ["play", "pause", "toggle"]):
        pyautogui.press('playpause')
        nexus_speak("Togglin' playback")
        return True

    return False

# ===================== Main Loop =====================
def flush_audio_stream(n=5):
    """Clear leftover audio so wake word engine doesn't get stuck"""
    for _ in range(n):
        try:
            stream.read(porcupine.frame_length, exception_on_overflow=False)
        except:
            pass


try:
    while True:
        pcm = stream.read(porcupine.frame_length, exception_on_overflow=False)

        audio = np.frombuffer(pcm, dtype=np.int16)

        if len(audio) != porcupine.frame_length:
            continue

        result = porcupine.process(audio)

        if result >= 0:
            print("🟡 WAKE WORD DETECTED")

            # 🔥 STOP dirty audio buildup
            flush_audio_stream()

            # Speak BEFORE recording
            nexus_speak("Yeah? I'm listening.")

            # Record user command
            audio_file = record_full_command()
            user_text = transcribe_audio(audio_file)

            if not user_text:
                nexus_speak("Didn't catch that.")
                flush_audio_stream()
                continue

            print(f"You: {user_text}")

            if run_custom_command(user_text):
                flush_audio_stream()
                continue

            reply = generate_response(user_text)
            nexus_speak(reply)

            # 🔥 CRITICAL: reset audio again AFTER TTS
            flush_audio_stream()

except KeyboardInterrupt:
    nexus_speak("Adios, amigo.")

finally:
    stream.close()
    p.terminate()
    porcupine.delete()
    pygame.mixer.quit()
    print("\nNEXUS shutdown complete.")