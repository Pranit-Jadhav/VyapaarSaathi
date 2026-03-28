import whisper
import os
import wave
import tempfile
import numpy as np
from typing import Any, Dict, List, Optional

_model = None
WHISPER_MODEL_NAME = os.getenv("WHISPER_MODEL", "large-v3")
HINDI_HINT_PROMPT = (
    "Yeh street vendor ka daily hisaab hai. Hindi ya Hinglish ko usi bhaasha mein likho. "
    "Translation mat karo."
)

def get_whisper_model():
    global _model
    if _model is None:
        # Better default accuracy for Hindi/Hinglish while allowing override via WHISPER_MODEL.
        print(f"Loading Whisper model: {WHISPER_MODEL_NAME}...")
        _model = whisper.load_model(WHISPER_MODEL_NAME)
    return _model


def _deva_ratio(text: str) -> float:
    if not text:
        return 0.0
    deva_count = sum(1 for ch in text if "\u0900" <= ch <= "\u097F")
    return deva_count / max(len(text), 1)


def _ascii_ratio(text: str) -> float:
    if not text:
        return 0.0
    ascii_count = sum(1 for ch in text if ord(ch) < 128 and ch.isalpha())
    alpha_count = sum(1 for ch in text if ch.isalpha())
    return ascii_count / max(alpha_count, 1)


def _avg_segment_logprob(segments: List[Dict[str, Any]]) -> float:
    if not segments:
        return -10.0
    values = []
    for seg in segments:
        value = seg.get("avg_logprob")
        if isinstance(value, (int, float)):
            values.append(float(value))
    if not values:
        return -10.0
    return sum(values) / len(values)


def _transcribe_pass(model: Any, file_path: str, language: Optional[str]) -> Dict[str, Any]:
    return model.transcribe(
        file_path,
        task="transcribe",
        language=language,
        initial_prompt=HINDI_HINT_PROMPT,
        temperature=0,
        beam_size=5,
        best_of=5,
        condition_on_previous_text=False,
        word_timestamps=True,
    )


def _preprocess_audio(file_path: str) -> Optional[str]:
    """
    Preprocesses audio for better ASR quality:
    - force mono 16k (via whisper.load_audio)
    - trim leading/trailing low-energy silence
    - normalize loudness to a safe target peak
    Returns temporary wav file path or None if preprocessing should be skipped.
    """
    audio = whisper.load_audio(file_path)
    if audio.size == 0:
        return None

    # Trim edge silence using a conservative energy threshold.
    threshold = 0.01
    active_idx = np.where(np.abs(audio) > threshold)[0]
    if active_idx.size > 0:
        start = max(int(active_idx[0]) - 1600, 0)  # keep 100ms context
        end = min(int(active_idx[-1]) + 1600, audio.shape[0])
        trimmed = audio[start:end]
        if trimmed.size > 1600:  # keep if at least ~0.1 sec remains
            audio = trimmed

    peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
    if peak > 0:
        # Normalize but avoid clipping and over-amplifying noise.
        target_peak = 0.85
        gain = min(target_peak / peak, 8.0)
        audio = np.clip(audio * gain, -1.0, 1.0)

    # Convert float [-1, 1] to PCM16 wav.
    pcm = (audio * 32767.0).astype(np.int16)
    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(out_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm.tobytes())
    return out_path


def _pick_best_result(forced_hi: Dict[str, Any], auto_lang: Dict[str, Any]) -> Dict[str, Any]:
    forced_text = (forced_hi.get("text") or "").strip()
    auto_text = (auto_lang.get("text") or "").strip()
    auto_detected_language = (auto_lang.get("language") or "").strip().lower()

    forced_segments = forced_hi.get("segments") or []
    auto_segments = auto_lang.get("segments") or []

    forced_score = _avg_segment_logprob(forced_segments)
    auto_score = _avg_segment_logprob(auto_segments)

    forced_deva = _deva_ratio(forced_text)
    auto_deva = _deva_ratio(auto_text)
    forced_ascii = _ascii_ratio(forced_text)
    auto_ascii = _ascii_ratio(auto_text)

    # If auto pass drifts to English but forced Hindi produced usable text,
    # prefer forced Hindi unless confidence gap is very large.
    if (
        auto_detected_language in {"en", "english"}
        and len(forced_text) >= 8
        and (forced_deva > auto_deva or forced_ascii < auto_ascii)
        and forced_score >= auto_score - 0.6
    ):
        return forced_hi

    # If forced Hindi captured Hindi script substantially better,
    # keep it even with a small confidence disadvantage.
    if (
        len(forced_text) >= 8
        and forced_deva >= auto_deva + 0.08
        and forced_score >= auto_score - 0.4
    ):
        return forced_hi

    # If quality is similar, prefer transcript that preserves Hindi script better.
    if abs(forced_score - auto_score) <= 0.25 and forced_deva > auto_deva + 0.1:
        return forced_hi

    # Otherwise choose the more confident decode.
    return forced_hi if forced_score >= auto_score else auto_lang

def transcribe_audio(file_path: str) -> dict:
    """
    Transcribes the audio file at file_path.
    Expects Hindi/Hinglish speech.
    """
    model = get_whisper_model()

    preprocessed_path: Optional[str] = None
    audio_for_decode = file_path
    try:
        preprocessed_path = _preprocess_audio(file_path)
        if preprocessed_path:
            audio_for_decode = preprocessed_path
    except Exception as e:
        print(f"Warning: audio preprocessing failed, using raw audio. Error: {e}")

    try:
        # Two-pass decode: forced Hindi + auto language detect, then pick best candidate.
        forced_hi = _transcribe_pass(model, audio_for_decode, language="hi")
        auto_lang = _transcribe_pass(model, audio_for_decode, language=None)
        result = _pick_best_result(forced_hi, auto_lang)
    finally:
        if preprocessed_path and os.path.exists(preprocessed_path):
            os.remove(preprocessed_path)
    
    # result contains 'text', 'segments', 'language'
    return {
        "text": result.get("text", "").strip(),
        "language": result.get("language", "hi"),
        "segments": result.get("segments", [])
    }
