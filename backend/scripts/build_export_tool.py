"""포트폴리오 내보내기 도구를 단일 exe로 빌드.

사용 (backend/ 에서):
  .venv/Scripts/python scripts/build_export_tool.py

결과: dist/포트폴리오-내보내기.exe
바탕화면에 두고 더블클릭하면 보유 현황이 문서\\VitalityNexus 에 저장되고
메모장이 열린다. 앱이 켜져 있으면 앱 백엔드에서, 꺼져 있으면 키움/거래소를
직접 호출하므로 앱과 별개로 단독 동작한다.
"""
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
except Exception:
    pass

BACKEND_DIR = Path(__file__).resolve().parent.parent


def main() -> None:
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--onefile",
        # 콘솔 창을 남긴다 — 진행 상황과 저장 경로가 보여야 하고, 앱이 꺼진 채로
        # 실행하면 조회에 30초쯤 걸려서 창이 없으면 멈춘 것처럼 보인다.
        "--console",
        "--name",
        "portfolio-export",
        # keyring(자격증명 관리자에서 API 키를 읽음)의 동적 import
        "--hidden-import",
        "keyring.backends.Windows",
        str(BACKEND_DIR / "tools" / "export_portfolio.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.run(cmd, cwd=BACKEND_DIR, check=True)

    built = BACKEND_DIR / "dist" / "portfolio-export.exe"
    final = BACKEND_DIR / "dist" / "포트폴리오-내보내기.exe"
    if built.exists():
        # 두 이름을 다 남긴다:
        #   portfolio-export.exe    깃허브 릴리스 첨부용 (에셋 이름은 ASCII가 안전)
        #   포트폴리오-내보내기.exe   바탕화면에 두고 쓸 때 알아보기 쉬운 이름
        # PyInstaller --name 에 한글을 주면 빌드가 깨지는 환경이 있어 영문으로 만든 뒤 복사한다.
        final.unlink(missing_ok=True)
        shutil.copy2(built, final)
    print(f"\nDone: {built}")
    print(f"      {final}")
    print("-> 바탕화면에 복사해 두고 더블클릭하면 됩니다.")


if __name__ == "__main__":
    main()
