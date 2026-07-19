"""API 키를 OS 키체인(Windows 자격증명 관리자)에 등록하는 CLI.

사용법 (backend/ 디렉터리에서):
  # 방법 A) 프롬프트에 붙여넣기 (권장 — 붙여넣기 확실히 됨, 화면엔 잠깐 보임)
  .venv/Scripts/python.exe scripts/set_api_key.py kiwoom app_key
  .venv/Scripts/python.exe scripts/set_api_key.py kiwoom app_secret
  .venv/Scripts/python.exe scripts/set_api_key.py kiwoom is_mock     # 실전=0, 모의=1

  # 방법 B) 값을 인자로 직접 (한 줄에 끝, 단 명령 히스토리에 남음)
  .venv/Scripts/python.exe scripts/set_api_key.py kiwoom app_key <붙여넣기>

값은 로컬 OS 자격증명 저장소(Windows Credential Locker)에만 저장되고 서버로 나가지
않는다. 저장 후 '길이'를 찍어주니, 키가 통째로 들어갔는지(예: 길이 40) 확인할 수 있다.

⚠️ getpass(안 보이는 입력)는 일부 Windows 터미널에서 붙여넣기가 1글자만 들어가는
문제가 있어, 붙여넣기가 확실한 visible input()으로 받는다. 로컬 전용 키라 화면에
잠깐 보이는 것은 문제되지 않는다(어차피 키체인에 안전하게 저장).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.keychain import set_api_key  # noqa: E402


def main() -> None:
    if len(sys.argv) not in (3, 4):
        print("사용법: python scripts/set_api_key.py <exchange> <key_name> [값]")
        print("  값을 생략하면 프롬프트에 붙여넣으면 됩니다.")
        sys.exit(1)

    exchange, key_name = sys.argv[1], sys.argv[2]
    if len(sys.argv) == 4:
        value = sys.argv[3].strip()
    else:
        value = input(f"{exchange}:{key_name} 값을 붙여넣고 엔터: ").strip()

    if not value:
        print("빈 값은 저장하지 않습니다.")
        sys.exit(1)

    set_api_key(exchange, key_name, value)
    print(f"저장 완료: {exchange}:{key_name}  (길이 {len(value)})")


if __name__ == "__main__":
    main()
