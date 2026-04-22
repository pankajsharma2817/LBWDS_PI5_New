import sounddevice as sd
import numpy as np

def activate_microphone(duration=5, samplerate=44100):
    print("Recording audio...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='float64')
    sd.wait()
    np.save("animal_sound.npy", recording)
    print("Audio saved as animal_sound.npy")
