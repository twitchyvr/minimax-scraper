//! Root application component — OS-like desktop with panels.

use dioxus::prelude::*;

use crate::components::desktop::Desktop;
use crate::state::app_state::AppState;

/// Root application component.
#[component]
pub fn App() -> Element {
    // Initialize global application state wrapped in a Signal for reactivity
    use_context_provider(|| Signal::new(AppState::default()));

    rsx! {
        Desktop {}
    }
}
