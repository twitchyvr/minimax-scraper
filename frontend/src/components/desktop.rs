//! Desktop component — the root OS-like layout with taskbar and window area.

use dioxus::prelude::*;

use crate::components::scraper::ScraperPanel;
use crate::components::terminal::TerminalPanel;
use crate::components::window::Window;
use crate::state::app_state::AppState;

/// The main desktop surface with taskbar and open windows.
#[component]
pub fn Desktop() -> Element {
    let state = use_context::<Signal<AppState>>();

    rsx! {
        div { class: "desktop",
            // Window area
            div { class: "desktop-workspace",
                if state.read().panels.scraper {
                    Window {
                        title: "Scraper",
                        panel_key: "scraper",
                        ScraperPanel {}
                    }
                }
                if state.read().panels.terminal {
                    Window {
                        title: "Terminal",
                        panel_key: "terminal",
                        TerminalPanel {}
                    }
                }
            }

            // Taskbar
            Taskbar {}
        }
    }
}

/// Bottom taskbar with panel toggle buttons.
#[component]
fn Taskbar() -> Element {
    let mut state = use_context::<Signal<AppState>>();

    rsx! {
        div { class: "taskbar",
            div { class: "taskbar-brand",
                "MiniMax Scraper"
            }
            div { class: "taskbar-panels",
                button {
                    class: if state.read().panels.scraper { "taskbar-btn active" } else { "taskbar-btn" },
                    onclick: move |_| {
                        let current = state.read().panels.scraper;
                        state.write().panels.scraper = !current;
                    },
                    "Scraper"
                }
                button {
                    class: if state.read().panels.terminal { "taskbar-btn active" } else { "taskbar-btn" },
                    onclick: move |_| {
                        let current = state.read().panels.terminal;
                        state.write().panels.terminal = !current;
                    },
                    "Terminal"
                }
                button {
                    class: if state.read().panels.explorer { "taskbar-btn active" } else { "taskbar-btn" },
                    onclick: move |_| {
                        let current = state.read().panels.explorer;
                        state.write().panels.explorer = !current;
                    },
                    "Explorer"
                }
                button {
                    class: if state.read().panels.preview { "taskbar-btn active" } else { "taskbar-btn" },
                    onclick: move |_| {
                        let current = state.read().panels.preview;
                        state.write().panels.preview = !current;
                    },
                    "Preview"
                }
            }
            div { class: "taskbar-status",
                "v0.1.0"
            }
        }
    }
}
