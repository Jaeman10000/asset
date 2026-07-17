# Vitality Nexus — Tauri 데스크톱 셸

Vite 프론트엔드를 네이티브 데스크톱 앱으로 감싸는 Tauri v2 프로젝트.
스펙 2장의 데스크톱 요구사항(자동시작 / 3가지 배치모드 / 시스템 트레이 / MSI·NSIS 배포)을 구현.

## 구현된 것

| 기능 | 위치 | 비고 |
|---|---|---|
| 시스템 트레이 | `src/lib.rs` | 열기/숨기기, 배치모드 전환, 종료. 좌클릭=창 토글 |
| 3가지 배치모드 | `src/lib.rs` `apply_placement` | 일반 / 항상위 / 데스크톱위젯(맨아래+테두리없음+작업표시줄숨김) |
| 부팅 자동시작 | `tauri-plugin-autostart` | 트레이 아님, 설정 패널(앱 내)에서 토글 |
| 백엔드 자동 기동/정리 | `src/backend.rs` | 앱 시작 시 FastAPI 띄우고 종료 시 kill |
| 창 X 버튼 | `src/lib.rs` `on_window_event` | 종료 아니라 트레이로 숨김 (상시 위젯) |
| 앱 내 설정 | `src/components/dashboard/SettingsPanel.tsx` | 배치모드·자동시작 (Tauri일 때만 노출) |

## ⚠️ 빌드 전 필수: Rust + MSVC 툴체인

Tauri는 Windows에서 **Rust와 Microsoft C++ 빌드 도구(MSVC)**가 필요하다.
현재 이 PC엔 둘 다 없다 (`npx tauri info`로 확인 가능). 설치:

1. **Rust** — https://rustup.rs 의 `rustup-init.exe` 실행 (또는 `winget install Rustlang.Rustup`)
   - 설치 후 새 터미널에서 `rustc --version` 확인
2. **MSVC C++ 빌드 도구** — https://aka.ms/vs/17/release/vs_BuildTools.exe
   - 설치 시 **"C++를 사용한 데스크톱 개발"** 워크로드 선택 (수 GB)
   - 또는 `winget install Microsoft.VisualStudio.2022.BuildTools --override "--quiet --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"`

WebView2는 Windows 11에 기본 탑재라 이미 있음 (`tauri info`에서 ✔ 확인됨).

## 실행

```bash
# 개발 (핫리로드) — 프론트+백엔드+네이티브 창을 한 번에 띄움
npm run tauri:dev

# 배포 빌드 (MSI + NSIS 인스톨러 생성)
npm run tauri:build
# 산출물: src-tauri/target/release/bundle/{msi,nsis}/
```

`tauri:dev`는 백엔드를 `backend/.venv`의 python으로 자동 기동한다
(`src/backend.rs`가 상위 폴더에서 `backend/.venv`를 탐색).

## 배포 시 백엔드 번들 (Python 없는 PC 대응)

개발은 venv python으로 백엔드를 띄우지만, 배포 앱 사용자는 Python이 없을 수 있다.
백엔드를 단일 exe로 묶어 앱에 포함한다:

```bash
cd ../backend
.venv/Scripts/pip install pyinstaller
.venv/Scripts/python scripts/build_sidecar.py   # → dist/vitality-backend.exe
cp dist/vitality-backend.exe ../vitality-nexus/src-tauri/
```

그 다음 `tauri.conf.json`의 `bundle.resources`(또는 `externalBin`)에 등록하면
번들에 포함된다. `backend.rs`가 exe 옆의 `vitality-backend.exe`를 자동 탐색하므로
Rust 코드 수정은 불필요하다.

## API 주소 처리

- **브라우저 dev**: Vite 프록시 `/api` → `localhost:8787`
- **Tauri 앱**(dev·prod): `window.__TAURI_INTERNALS__` 감지 → 백엔드에 직접 연결
  (`http://127.0.0.1:8787`). `src/api/client.ts` 참고.
- CSP(`tauri.conf.json`)에서 `localhost:8787`, Yahoo/업비트/빗썸 도메인을 허용해둠.
