import math
import struct
import wave

SAMPLE_RATE = 44100
DURATION = 28.0  # seconds
NUM_SAMPLES = int(SAMPLE_RATE * DURATION)

# Chord frequencies (Hz) for a chill upbeat lo-fi progression (Fmaj7 -> Em7 -> Dm7 -> Cmaj7)
CHORDS = [
    [174.61, 220.00, 261.63, 329.63], # Fmaj7
    [164.81, 196.00, 246.94, 293.66], # Em7
    [146.83, 174.61, 220.00, 261.63], # Dm7
    [130.81, 164.81, 196.00, 246.94], # Cmaj7
]

BPM = 84
BEAT_DUR = 60.0 / BPM  # ~0.714s
BAR_DUR = BEAT_DUR * 4 # ~2.857s

def generate_lofi():
    out_samples = []
    
    for i in range(NUM_SAMPLES):
        t = i / SAMPLE_RATE
        
        # Determine bar and chord
        bar_index = int(t / BAR_DUR) % len(CHORDS)
        chord_freqs = CHORDS[bar_index]
        
        # 1. Warm chord pad (triangle wave with smooth envelope)
        t_in_bar = t % BAR_DUR
        pad_env = math.exp(-0.8 * (t_in_bar / BAR_DUR))
        pad_val = 0.0
        for f in chord_freqs:
            # Triangle wave sum
            val = 0.0
            for k in range(1, 4, 2):
                val += (1.0 / (k * k)) * math.sin(2 * math.pi * k * f * t)
            pad_val += val * 0.15 * pad_env

        # 2. Upbeat Lo-fi Drum Beat (Kick on 1 & 3, Snare on 2 & 4, Hi-hats on 8ths)
        beat_in_bar = (t % BAR_DUR) / BEAT_DUR
        beat_num = beat_in_bar % 4.0
        
        drum_val = 0.0
        
        # Kick (low sine drop)
        kick_t = (t % (BEAT_DUR * 2))
        if kick_t < 0.15:
            kick_freq = 110.0 * math.exp(-25.0 * kick_t)
            kick_env = math.exp(-15.0 * kick_t)
            drum_val += 0.4 * math.sin(2 * math.pi * kick_freq * kick_t) * kick_env
            
        # Snare (noise + sine pop on beats 2 & 4)
        snare_t = ((t + BEAT_DUR) % (BEAT_DUR * 2))
        if snare_t < 0.18:
            snare_env = math.exp(-18.0 * snare_t)
            # Pseudo random noise
            noise = (math.sin(t * 123456.789) * 43758.5453123) % 1.0 - 0.5
            snare_pop = math.sin(2 * math.pi * 180.0 * snare_t)
            drum_val += 0.25 * (noise * 0.7 + snare_pop * 0.3) * snare_env

        # Hi-hat (soft noise tick on 8th notes)
        hat_t = t % (BEAT_DUR / 2)
        if hat_t < 0.05:
            hat_env = math.exp(-60.0 * hat_t)
            hat_noise = (math.sin(t * 987654.321) * 65432.12345) % 1.0 - 0.5
            drum_val += 0.08 * hat_noise * hat_env

        # Subtle Vinyl Crackle / Warm Noise
        crackle = ((math.sin(t * 777777.7) * 99999.9) % 1.0 - 0.5) * 0.012

        # Combine
        sample = pad_val + drum_val + crackle
        # Soft clipping
        sample = max(-0.95, min(0.95, sample))
        
        out_samples.append(int(sample * 32767))

    with wave.open("scratch/lofi_beat.wav", "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        for s in out_samples:
            wf.writeframes(struct.pack("<h", s))

    print("Lo-fi beat generated successfully at scratch/lofi_beat.wav")

if __name__ == "__main__":
    generate_lofi()
