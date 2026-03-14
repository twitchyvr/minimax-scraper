//! Markdown preview panel — renders scraped markdown as sanitized HTML.

use dioxus::prelude::*;
use pulldown_cmark::{Options, Parser};

use crate::state::app_state::AppState;

/// Maximum markdown size to render synchronously (512 KB).
/// Larger files would freeze the single-threaded WASM UI.
const MAX_PREVIEW_BYTES: usize = 512 * 1024;

/// Preview panel that renders the currently selected file's markdown content.
#[component]
pub fn PreviewPanel() -> Element {
    let state = use_context::<Signal<AppState>>();
    let selected = state.read().selected_file.clone();
    let content = state.read().preview_content.clone();

    rsx! {
        div { class: "preview-panel",
            match (&selected, &content) {
                (Some(path), Some(md)) => {
                    let (html, truncated) = markdown_to_html(md);
                    rsx! {
                        div { class: "preview-header",
                            span { class: "preview-path", "{path}" }
                        }
                        div {
                            class: "preview-content",
                            dangerous_inner_html: "{html}",
                        }
                        if truncated {
                            p { class: "preview-truncated",
                                "Content truncated (file too large for live preview)."
                            }
                        }
                    }
                }
                (Some(path), None) => rsx! {
                    div { class: "preview-header",
                        span { class: "preview-path", "{path}" }
                    }
                    p { class: "preview-loading", "Loading..." }
                },
                _ => rsx! {
                    p { class: "preview-empty", "Select a file in the Explorer to preview it." }
                },
            }
        }
    }
}

/// Convert markdown to sanitized HTML. Returns (html, was_truncated).
fn markdown_to_html(markdown: &str) -> (String, bool) {
    let truncated = markdown.len() > MAX_PREVIEW_BYTES;
    let source = if truncated {
        &markdown[..MAX_PREVIEW_BYTES]
    } else {
        markdown
    };

    let mut opts = Options::empty();
    opts.insert(Options::ENABLE_TABLES);
    opts.insert(Options::ENABLE_STRIKETHROUGH);
    opts.insert(Options::ENABLE_TASKLISTS);

    let parser = Parser::new_ext(source, opts);
    let mut raw_html = String::new();
    pulldown_cmark::html::push_html(&mut raw_html, parser);

    // Sanitize HTML to prevent XSS from scraped content.
    // ammonia strips <script>, event handlers, etc. while preserving safe formatting.
    let safe_html = ammonia::clean(&raw_html);

    (safe_html, truncated)
}
