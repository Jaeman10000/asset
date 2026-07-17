//! 로컬 FastAPI 백엔드(localhost:8787) 프로세스 관리.
//!
//! 앱 시작 시 백엔드를 자식 프로세스로 띄우고, 앱 종료 시 정리한다.
//! - 개발: backend/.venv 의 python 으로 `uvicorn app.main:app` 실행
//! - 배포: PyInstaller로 만든 사이드카 exe(리소스에 번들)를 실행
//!
//! 백엔드를 못 찾으면 조용히 넘어간다 — 프론트가 "백엔드 오프라인"을 표시하고,
//! 사용자가 수동으로 띄우면 자동으로 다시 붙는다 (graceful).

use std::path::PathBuf;
use std::process::{Child, Command};
use std::sync::Mutex;

/// 실행 중인 백엔드 자식 프로세스 핸들 (앱 종료 시 kill 하려고 보관)
#[derive(Default)]
pub struct BackendProcess(pub Mutex<Option<Child>>);

const BACKEND_PORT: &str = "8787";

/// 개발 환경에서 backend 디렉터리를 찾는다. exe 위치와 현재 작업 디렉터리에서
/// 위로 올라가며 `backend/.venv/Scripts/python.exe`(Windows) 또는
/// `backend/.venv/bin/python`(Unix)를 탐색한다.
fn find_dev_backend() -> Option<(PathBuf, PathBuf)> {
    let python_rel = if cfg!(windows) {
        ".venv/Scripts/python.exe"
    } else {
        ".venv/bin/python"
    };

    let mut roots: Vec<PathBuf> = Vec::new();
    if let Ok(cwd) = std::env::current_dir() {
        roots.push(cwd);
    }
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            roots.push(dir.to_path_buf());
        }
    }

    for start in roots {
        let mut dir = Some(start.as_path());
        // 최대 6단계 상위까지 탐색
        for _ in 0..6 {
            let Some(d) = dir else { break };
            let backend = d.join("backend");
            let python = backend.join(python_rel);
            if python.exists() {
                return Some((backend, python));
            }
            dir = d.parent();
        }
    }
    None
}

/// 백엔드를 기동한다. 성공하면 Child를 state에 저장.
pub fn spawn_backend(state: &BackendProcess) {
    // 1) 환경변수 override (사용자가 직접 지정)
    if let Ok(python) = std::env::var("VITALITY_BACKEND_PYTHON") {
        let backend = std::env::var("VITALITY_BACKEND_DIR").unwrap_or_else(|_| "backend".into());
        if let Some(child) = try_spawn_python(PathBuf::from(&backend), PathBuf::from(&python)) {
            *state.0.lock().unwrap() = Some(child);
            return;
        }
    }

    // 2) 개발용 venv python 탐색
    if let Some((backend, python)) = find_dev_backend() {
        if let Some(child) = try_spawn_python(backend, python) {
            eprintln!("[vitality] 개발 백엔드 기동됨");
            *state.0.lock().unwrap() = Some(child);
            return;
        }
    }

    // 3) 배포 사이드카 exe (리소스에 번들된 경우)
    if let Ok(exe) = std::env::current_exe() {
        if let Some(dir) = exe.parent() {
            let sidecar = dir.join(if cfg!(windows) {
                "vitality-backend.exe"
            } else {
                "vitality-backend"
            });
            if sidecar.exists() {
                if let Ok(child) = Command::new(&sidecar).spawn() {
                    eprintln!("[vitality] 사이드카 백엔드 기동됨");
                    *state.0.lock().unwrap() = Some(child);
                    return;
                }
            }
        }
    }

    eprintln!(
        "[vitality] 백엔드를 찾지 못함 — 프론트가 오프라인으로 뜹니다. \
         backend/를 수동 실행하거나 VITALITY_BACKEND_PYTHON을 설정하세요."
    );
}

fn try_spawn_python(backend_dir: PathBuf, python: PathBuf) -> Option<Child> {
    Command::new(&python)
        .args([
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            BACKEND_PORT,
        ])
        .current_dir(&backend_dir)
        .spawn()
        .ok()
}

/// 앱 종료 시 백엔드 자식 프로세스를 정리한다.
pub fn kill_backend(state: &BackendProcess) {
    if let Some(mut child) = state.0.lock().unwrap().take() {
        let _ = child.kill();
        let _ = child.wait();
    }
}
