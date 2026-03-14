//! Terminal panel — log view with auto-scroll.

use dioxus::prelude::*;

use crate::state::app_state::AppState;

/// Terminal-style log viewer.
#[component]
pub fn TerminalPanel() -> Element {
    let state = use_context::<Signal<AppState>>();

    rsx! {
        div { class: "terminal-panel",
            div { class: "terminal-output",
                {
                    let messages = state.read().log_messages.clone();
                    rsx! {
                        for (i, msg) in messages.iter().enumerate() {
                            {
                                let css_class = if msg.starts_with("[ERROR]") {
                                    "terminal-line terminal-error"
                                } else if msg.starts_with("[WARN]") {
                                    "terminal-line terminal-warn"
                                } else {
                                    "terminal-line"
                                };
                                rsx! {
                                    div {
                                        class: css_class,
                                        key: "{i}",
                                        "{msg}"
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
