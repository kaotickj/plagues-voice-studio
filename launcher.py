"""Entry point shared by source runs and packaged Windows builds."""
from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

if __name__ == "__main__":
    # Run before importing Qt, and return a process exit code that the Windows
    # build script can check before creating an installer.
    if len(sys.argv) >= 2 and sys.argv[1] == "--self-test":
        from chatterbox_studio.frozen_check import run
        sys.exit(run(Path(sys.argv[2]) if len(sys.argv) > 2 else None))
    if len(sys.argv) >= 2 and sys.argv[1] == "--ui-self-test":
        from chatterbox_studio.ui_smoke_test import run
        sys.exit(run(Path(sys.argv[2]) if len(sys.argv) > 2 else None))
    if len(sys.argv) >= 2 and sys.argv[1] == "--ui-self-test-no-audio":
        from chatterbox_studio.ui_smoke_test import run
        sys.exit(run(Path(sys.argv[2]) if len(sys.argv) > 2 else None, no_audio=True))
    if len(sys.argv) == 3 and sys.argv[1] == '--kokoro-self-test':
        from chatterbox_studio.kokoro_check import run
        sys.exit(run(Path(sys.argv[2])))
    if len(sys.argv) == 4 and sys.argv[1] == '--speech-self-test':
        from chatterbox_studio.speech_check import run
        sys.exit(run(Path(sys.argv[2]), Path(sys.argv[3])))
    from chatterbox_studio.app import run
    sys.exit(run())
