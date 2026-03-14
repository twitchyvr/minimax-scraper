//! Window chrome component — title bar with close/minimize.

use dioxus::prelude::*;

use crate::state::app_state::AppState;

/// A window panel with title bar and close button.
#[component]
pub fn Window(title: String, panel_key: String, children: Element) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let key = panel_key.clone();

    rsx! {
        div { class: "window",
            div { class: "window-titlebar",
                span { class: "window-title", "{title}" }
                div { class: "window-controls",
                    button {
                        class: "window-btn window-btn-close",
                        onclick: move |_| {
                            let k = key.clone();
                            match k.as_str() {
                                "scraper" => state.write().panels.scraper = false,
                                "explorer" => state.write().panels.explorer = false,
                                "preview" => state.write().panels.preview = false,
                                "terminal" => state.write().panels.terminal = false,
                                _ => {}
                            }
                        },
                        "x"
                    }
                }
            }
            div { class: "window-body",
                {children}
            }
        }
    }
}
