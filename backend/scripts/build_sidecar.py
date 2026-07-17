"""
백엔드를 단일 실행파일(사이드카)로 빌드 — Tauri 프로덕션 번들에 포함하기 위함.

개발 중에는 Tauri가 venv python으로 백엔드를 직접 띄우지만(src-tauri/src/backend.rs),
배포 앱은 사용자 PC에 Python이 없을 수 있으므로 exe로 묶어야 한다.

사용 (backend/ 에서):
  .venv/Scripts/pip install pyinstaller
  .venv/Scripts/python scripts/build_sidecar.py

결과: dist/vitality-backend.exe
이 파일을 vitality-nexus/src-tauri/ 로 복사하고 tauri.conf.json의
bundle.externalBin 또는 resources에 등록하면 앱에 번들된다.
(backend.rs는 exe 위치에서 vitality-backend.exe를 자동 탐색한다.)
"""
import subprocess
import sys
from pathlib import Path

# CI Windows 콘솔 기본 인코딩(cp1252)에서 비ASCII 출력이 죽지 않도록 UTF-8로 고정
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    # uvicorn을 코드에서 직접 기동하는 런처 (PyInstaller가 CLI보다 묶기 쉬움)
    launcher = BACKEND_DIR / "sidecar_entry.py"
    launcher.write_text(
        "import uvicorn\n"
        "from app.main import app\n"
        "if __name__ == '__main__':\n"
        "    uvicorn.run(app, host='127.0.0.1', port=8787)\n",
        encoding="utf-8",
    )

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        "--name",
        "vitality-backend",
        # keyring/uvicorn의 동적 import를 PyInstaller가 놓치지 않도록
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "keyring.backends.Windows",
        str(launcher),
    ]
    # 로그는 ASCII로 — CI Windows 콘솔 기본 인코딩(cp1252)에서 한글 print가
    # UnicodeEncodeError로 죽는 것을 방지
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=BACKEND_DIR, check=True)
    print("\nDone: backend/dist/vitality-backend.exe")
    print("-> copy to vitality-nexus/src-tauri/ and register in tauri.conf.json")


if __name__ == "__main__":
    main()
