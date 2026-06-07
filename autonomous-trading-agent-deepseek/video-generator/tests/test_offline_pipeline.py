import os
import sys
from pathlib import Path

VIDEO_ROOT = Path(__file__).resolve().parents[1]
if str(VIDEO_ROOT) not in sys.path:
    sys.path.insert(0, str(VIDEO_ROOT))


def test_script_generator_offline_mode(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    from core.script_generator import ScriptGenerator

    gen = ScriptGenerator()
    script = gen.generate_script(topic="prueba", duration_seconds=30, niche="general", include_visual_cues=True)
    assert "hook" in script
    assert "sections" in script
    assert "cta" in script
    assert script["metadata"]["duration"] == 30


def test_voice_synthesizer_mock_generates_mp3(tmp_path, monkeypatch):
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    from core.voice_synthesizer import VoiceSynthesizer

    out = tmp_path / "audio.mp3"
    vs = VoiceSynthesizer()
    res = vs.generate_speech("hola mundo", str(out))
    assert res["success"] is True
    audio_path = Path(res["audio_path"])
    assert audio_path.exists()
    assert audio_path.stat().st_size > 0


def test_image_generator_offline_placeholder(tmp_path, monkeypatch):
    # Ensure no replicate token
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)
    from core.image_generator import ImageGenerator

    out = tmp_path / "img.jpg"
    ig = ImageGenerator()
    res = ig.generate_image("test prompt", output_path=str(out), width=640, height=360)
    assert res["success"] is True
    assert out.exists()
    assert out.stat().st_size > 0


def test_cli_dry_run_offline(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "offline")
    monkeypatch.setenv("TTS_PROVIDER", "mock")
    monkeypatch.delenv("REPLICATE_API_TOKEN", raising=False)

    # Run from scripts path; ensure it can import regardless of cwd.
    import subprocess
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "generate_video.py"
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    proc = subprocess.run(
        ["python", str(script_path), "--text", "hola", "--duration", "10", "--no-trends", "--no-subtitles", "--no-music", "--dry-run"],
        cwd=str(tmp_path),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
