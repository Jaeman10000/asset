"""
OS 키체인 래퍼 — API 키를 Tauri 번들이나 .env가 아니라 OS가 관리하는
자격증명 저장소(Windows Credential Locker / macOS Keychain)에 둔다.

`keyring` 라이브러리가 플랫폼을 자동 감지한다 — Windows에서는
WinVaultKeyring이 기본으로 잡혀 별도 설정이 필요 없다.

키를 등록하려면 scripts/set_api_key.py 참고.
"""
import keyring

SERVICE_NAME = "vitality-nexus"


def _account(exchange: str, key_name: str) -> str:
    return f"{exchange}:{key_name}"


def get_api_key(exchange: str, key_name: str) -> str | None:
    return keyring.get_password(SERVICE_NAME, _account(exchange, key_name))


def set_api_key(exchange: str, key_name: str, value: str) -> None:
    keyring.set_password(SERVICE_NAME, _account(exchange, key_name), value)


def delete_api_key(exchange: str, key_name: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, _account(exchange, key_name))
    except keyring.errors.PasswordDeleteError:
        pass  # 애초에 없었으면 조용히 무시


def has_api_key(exchange: str, key_name: str) -> bool:
    return get_api_key(exchange, key_name) is not None
