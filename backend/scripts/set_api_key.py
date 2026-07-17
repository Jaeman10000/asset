"""
API 키를 OS 키체인에 등록하는 CLI.

사용법 (backend/ 디렉터리에서):
  .venv/Scripts/python.exe scripts/set_api_key.py kiwoom app_key
  .venv/Scripts/python.exe scripts/set_api_key.py kis app_key
  .venv/Scripts/python.exe scripts/set_api_key.py upbit access_key
  .venv/Scripts/python.exe scripts/set_api_key.py upbit secret_key
  .venv/Scripts/python.exe scripts/set_api_key.py bithumb api_key
  .venv/Scripts/python.exe scripts/set_api_key.py bithumb api_secret

값은 getpass로 입력받아 화면/히스토리에 남지 않는다. 저장 위치는
Windows Credential Locker (keyring 라이브러리가 자동 선택).
"""
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.keychain import set_api_key  # noqa: E402


def main() -> None:
    if len(sys.argv) != 3:
        print("사용법: python scripts/set_api_key.py <exchange> <key_name>")
        sys.exit(1)

    exchange, key_name = sys.argv[1], sys.argv[2]
    value = getpass.getpass(f"{exchange}:{key_name} 값 입력 (화면에 안 보임): ")
    if not value:
        print("빈 값은 저장하지 않습니다.")
        sys.exit(1)

    set_api_key(exchange, key_name, value)
    print(f"저장 완료: {exchange}:{key_name}")


if __name__ == "__main__":
    main()
