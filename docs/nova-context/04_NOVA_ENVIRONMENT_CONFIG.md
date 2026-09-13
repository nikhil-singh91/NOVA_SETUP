# 04 — NOVA Environment Configuration & Settings

## Central Configuration System
NOVA manages all configuration through a centralized, validated Pydantic Settings v2 model defined in `config/settings.py`.

---

## 📋 Environment Variable Catalog

| Variable Name | Type | Required | Default Value | Description |
| :--- | :--- | :--- | :--- | :--- |
| `GEMINI_API_KEY` | `SecretStr` | **Yes** | — | Google Gemini API key for primary reasoning |
| `GROQ_API_KEY` | `SecretStr` | **Yes** | — | Groq API key for fast inference |
| `OPENROUTER_API_KEY`| `SecretStr` | **Yes** | — | OpenRouter API key for backup model access |
| `CEREBRAS_API_KEY` | `SecretStr` | **Yes** | — | Cerebras Cloud API key for cheap/fast inference |
| `TAVILY_API_KEY` | `SecretStr` | **Yes** | — | Tavily Search API key for deep web research |
| `ELEVENLABS_API_KEY`| `SecretStr` | **Yes** | — | ElevenLabs API key for optional neural speech |
| `OPENWEATHER_API_KEY`| `SecretStr`| **Yes** | — | OpenWeatherMap API key |
| `NEWS_API_KEY` | `SecretStr` | **Yes** | — | NewsAPI key for news digests |
| `GOOGLE_MAPS_API_KEY`| `SecretStr`| No | `None` | Optional Google Maps API key |
| `APP_ENV` | `str` | No | `"development"` | Environment (`development`, `production`, `test`) |
| `DEBUG` | `bool` | No | `False` | Debug mode toggle |
| `LOG_LEVEL` | `str` | No | `"INFO"` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `STT_ENGINE` | `str` | No | `"whisper"` | Speech-to-text engine (`whisper`, `faster_whisper`) |
| `TTS_ENGINE` | `str` | No | `"edge_tts"` | Text-to-speech engine (`edge_tts`, `pyttsx3`, `kokoro`) |
| `TTS_VOICE` | `str` | No | `"hi-IN-SwaraNeural"`| Voice model identifier for TTS |
| `WHISPER_MODEL_NAME`| `str` | No | `"small"` | Whisper model size (`tiny`, `base`, `small`, `medium`) |
| `STT_LANGUAGE` | `str` | No | `"auto"` | ASR language code (`auto`, `en`, `hi`) |
| `DEFAULT_BROWSER` | `str` | No | `"chrome"` | Default web browser (`chrome`, `safari`) |
| `DESKTOP_WORKSPACE_DIR`| `str` | No | `"~/Desktop/NOVA_WORKSPACE"`| Default sandboxed file workspace |
| `DESKTOP_CAMERA_OUTPUT_DIR`| `str` | No | `"~/Pictures/NOVA"` | Destination folder for camera snapshots |
| `NOVA_BROWSER_DEBUG`| `bool`| No | `False` | Enable browser action debug logging |
| `NOVA_INTENT_DEBUG` | `bool`| No | `False` | Enable intent parsing telemetry |
| `NOVA_MEDIA_DEBUG` | `bool`| No | `False` | Enable media matching debug output |
| `NOVA_ENVIRONMENT_DEBUG`| `bool`| No| `False` | Enable environment observer debug output |
| `NOVA_COMPUTER_AGENT_DEBUG`| `bool`| No| `False` | Enable computer agent perception logs |
| `NOVA_TASK_AGENT_DEBUG`| `bool`| No | `False` | Enable task agent step execution logs |

---

## 🔒 Security Best Practices
- **No Plaintext Secrets in Logs:** All keys use Pydantic's `SecretStr` to prevent accidental serialization.
- **Git Ignore Protection:** `.env` and `credentials.json` are excluded in `.gitignore`.
- **Doctor Verification:** `ui/doctor.py` checks for the presence and non-emptiness of required keys without ever printing the key strings.
