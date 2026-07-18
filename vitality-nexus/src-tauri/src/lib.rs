//! Vitality Nexus — Tauri v2 데스크톱 셸.
//!
//! - 시스템 트레이: 보이기/숨기기, 배치 모드 전환, 종료
//! - 3가지 배치 모드 (스펙 2장): normal / on-top / desktop-widget
//! - 부팅 시 자동 실행 (tauri-plugin-autostart)
//! - 로컬 FastAPI 백엔드 자동 기동/정리 (backend.rs)

mod backend;

use backend::{kill_backend, spawn_backend, BackendProcess};
use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent},
    Manager, RunEvent, WebviewWindow,
};
use tauri_plugin_autostart::{MacosLauncher, ManagerExt};

/// 창 배치 모드. 스펙: "3가지 배치 모드 (desktop / on-top / normal)"
#[derive(Clone, Copy)]
enum PlacementMode {
    /// 일반 창 (테두리 있음, 보통 z-order)
    Normal,
    /// 항상 위 (다른 창 위에 떠 있음)
    OnTop,
    /// 데스크톱 위젯 (테두리 없음, 항상 맨 아래, 작업표시줄 숨김) — 배경화면에 붙은 느낌
    DesktopWidget,
}

fn apply_placement(window: &WebviewWindow, mode: PlacementMode) {
    match mode {
        PlacementMode::Normal => {
            let _ = window.set_always_on_bottom(false);
            let _ = window.set_always_on_top(false);
            let _ = window.set_decorations(true);
            let _ = window.set_skip_taskbar(false);
        }
        PlacementMode::OnTop => {
            let _ = window.set_always_on_bottom(false);
            let _ = window.set_decorations(true);
            let _ = window.set_skip_taskbar(false);
            let _ = window.set_always_on_top(true);
        }
        PlacementMode::DesktopWidget => {
            let _ = window.set_always_on_top(false);
            let _ = window.set_decorations(false);
            let _ = window.set_skip_taskbar(true);
            let _ = window.set_always_on_bottom(true);
        }
    }
    let _ = window.show();
    let _ = window.set_focus();
}

/// 프론트에서 배치 모드를 바꿀 수 있게 노출하는 커맨드 (설정 UI에서 호출 가능)
#[tauri::command]
fn set_placement(window: WebviewWindow, mode: String) {
    let m = match mode.as_str() {
        "on-top" => PlacementMode::OnTop,
        "desktop-widget" => PlacementMode::DesktopWidget,
        _ => PlacementMode::Normal,
    };
    apply_placement(&window, m);
}

/// 자동 시작(부팅 시 실행) 토글 — 설정 UI에서 호출
#[tauri::command]
fn set_autostart(app: tauri::AppHandle, enabled: bool) -> Result<(), String> {
    let manager = app.autolaunch();
    if enabled {
        manager.enable().map_err(|e| e.to_string())
    } else {
        manager.disable().map_err(|e| e.to_string())
    }
}

#[tauri::command]
fn is_autostart(app: tauri::AppHandle) -> Result<bool, String> {
    app.autolaunch().is_enabled().map_err(|e| e.to_string())
}

fn show_main(app: &tauri::AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.unminimize();
        let _ = w.set_focus();
    }
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_autostart::init(
            MacosLauncher::LaunchAgent,
            None,
        ))
        .manage(BackendProcess::default())
        .invoke_handler(tauri::generate_handler![
            set_placement,
            set_autostart,
            is_autostart
        ])
        .setup(|app| {
            // 로컬 백엔드 기동
            let state = app.state::<BackendProcess>();
            spawn_backend(&state);

            // 로컬 개발(debug) 빌드에서만 웹뷰 콘솔 자동 오픈.
            // 배포(release) 빌드에서는 열리지 않는다.
            #[cfg(debug_assertions)]
            if let Some(w) = app.get_webview_window("main") {
                w.open_devtools();
            }

            // ── 시스템 트레이 메뉴 ──
            let show_i = MenuItem::with_id(app, "show", "열기", true, None::<&str>)?;
            let hide_i = MenuItem::with_id(app, "hide", "숨기기", true, None::<&str>)?;

            let mode_normal = MenuItem::with_id(app, "mode_normal", "일반 창", true, None::<&str>)?;
            let mode_ontop = MenuItem::with_id(app, "mode_ontop", "항상 위", true, None::<&str>)?;
            let mode_widget =
                MenuItem::with_id(app, "mode_widget", "데스크톱 위젯", true, None::<&str>)?;
            let mode_menu = Submenu::with_items(
                app,
                "배치 모드",
                true,
                &[&mode_normal, &mode_ontop, &mode_widget],
            )?;

            let quit_i = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            let sep = PredefinedMenuItem::separator(app)?;

            let menu = Menu::with_items(
                app,
                &[&show_i, &hide_i, &sep, &mode_menu, &sep, &quit_i],
            )?;

            let _tray = TrayIconBuilder::with_id("main-tray")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("Vitality Nexus")
                .menu(&menu)
                .show_menu_on_left_click(false)
                .on_menu_event(|app, event| match event.id.as_ref() {
                    "show" => show_main(app),
                    "hide" => {
                        if let Some(w) = app.get_webview_window("main") {
                            let _ = w.hide();
                        }
                    }
                    "mode_normal" => {
                        if let Some(w) = app.get_webview_window("main") {
                            apply_placement(&w, PlacementMode::Normal);
                        }
                    }
                    "mode_ontop" => {
                        if let Some(w) = app.get_webview_window("main") {
                            apply_placement(&w, PlacementMode::OnTop);
                        }
                    }
                    "mode_widget" => {
                        if let Some(w) = app.get_webview_window("main") {
                            apply_placement(&w, PlacementMode::DesktopWidget);
                        }
                    }
                    "quit" => {
                        let state = app.state::<BackendProcess>();
                        kill_backend(&state);
                        app.exit(0);
                    }
                    _ => {}
                })
                // 트레이 좌클릭 → 창 토글
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        show_main(tray.app_handle());
                    }
                })
                .build(app)?;

            Ok(())
        })
        // 창 닫기(X)는 종료가 아니라 트레이로 숨김 (상시 위젯이므로)
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                let _ = window.hide();
                api.prevent_close();
            }
        })
        .build(tauri::generate_context!())
        .expect("Tauri 앱 초기화 실패")
        .run(|app, event| {
            // 앱이 정말 종료될 때 백엔드 정리
            if let RunEvent::Exit = event {
                let state = app.state::<BackendProcess>();
                kill_backend(&state);
            }
        });
}
