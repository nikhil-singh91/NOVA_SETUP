"""Vectorized audio signal preprocessing and enhancement utilities for speech recognition."""

from __future__ import annotations

import numpy as np

def highpass_filter(data: np.ndarray, sample_rate: int = 16000) -> np.ndarray:
    """Apply a vectorized moving-average highpass filter to strip AC hum/fan rumble."""
    # A moving average of length 120 (7.5ms at 16kHz) represents low frequencies.
    # Subtracting the lowpass moving average yields a clean highpass signal.
    window_size = 120
    if len(data) <= window_size:
        return data
        
    cumsum = np.cumsum(np.insert(data, 0, 0))
    lowpass = (cumsum[window_size:] - cumsum[:-window_size]) / window_size
    
    # Pad edge boundaries to align shapes
    pad_len = len(data) - len(lowpass)
    lowpass = np.pad(lowpass, (pad_len // 2, pad_len - pad_len // 2), mode='edge')
    return data - lowpass

def noise_gate(data: np.ndarray, threshold: float = 0.02, attenuation: float = 0.15) -> np.ndarray:
    """Attenuate segments of the signal falling below the noise floor."""
    mask = np.abs(data) < threshold
    gated_data = np.copy(data)
    gated_data[mask] *= attenuation
    return gated_data

def normalize_volume(data: np.ndarray, target_peak: float = 0.95) -> np.ndarray:
    """Scale audio peaks to a target maximum amplitude (Automatic Gain Control)."""
    peak = np.max(np.abs(data))
    if peak > 0.001:
        return data * (target_peak / peak)
    return data

def trim_silence(data: np.ndarray, threshold: float = 0.005) -> np.ndarray:
    """Trim leading and trailing silence/noise from the audio array with safety padding."""
    if len(data) == 0:
        return data
    frame_size = 480
    num_frames = len(data) // frame_size
    if num_frames == 0:
        return data
        
    start_frame = 0
    for i in range(num_frames):
        rms = np.sqrt(np.mean(data[i*frame_size:(i+1)*frame_size] ** 2))
        if rms > threshold:
            start_frame = max(0, i - 1)
            break
            
    end_frame = num_frames
    for i in range(num_frames - 1, start_frame - 1, -1):
        rms = np.sqrt(np.mean(data[i*frame_size:(i+1)*frame_size] ** 2))
        if rms > threshold:
            end_frame = min(num_frames, i + 2)
            break
            
    return data[start_frame*frame_size:end_frame*frame_size]

def preprocess_audio(raw_pcm_bytes: bytes, sample_rate: int = 16000) -> np.ndarray:
    """Converts 16-bit raw PCM bytes to float32, applies DSP enhancements, and returns float32 array."""
    # Convert raw PCM int16 to float32 normalized between [-1.0, 1.0]
    audio_int16 = np.frombuffer(raw_pcm_bytes, dtype=np.int16)
    audio_float = audio_int16.astype(np.float32) / 32768.0
    
    if len(audio_float) == 0:
        return audio_float

    # 1. Strip fan hum and DC offsets
    audio_filt = highpass_filter(audio_float, sample_rate=sample_rate)
        
    # 2. AGC Peak normalization
    audio_norm = normalize_volume(audio_filt, target_peak=0.95)
    
    # 3. Trim leading/trailing silence safely
    audio_trimmed = trim_silence(audio_norm, threshold=0.005)
    
    return audio_trimmed if len(audio_trimmed) > 0 else audio_norm
