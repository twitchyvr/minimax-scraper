//! AI Chat panel — chat-style Q&A over scraped documentation.

use dioxus::prelude::*;

use crate::api::client;
use crate::state::app_state::AppState;

/// A single message in the chat.
#[derive(Clone, Debug, PartialEq)]
pub struct ChatMessage {
    pub role: String, // "user" or "assistant"
    pub content: String,
    pub sources: Vec<String>,
}

/// AI Chat panel with message history and input.
#[component]
pub fn AiChatPanel() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut input_text = use_signal(String::new);
    let mut messages = use_signal(Vec::<ChatMessage>::new);
    let mut loading = use_signal(|| false);
    let mut error_msg = use_signal(|| None::<String>);

    let send_message = move |_| {
        let question = input_text.read().trim().to_string();
        if question.is_empty() || *loading.read() {
            return;
        }

        let job_id = state.read().active_job_id.clone();
        let Some(job_id) = job_id else {
            error_msg.set(Some(
                "No active job selected. Start a scrape first.".to_string(),
            ));
            return;
        };

        // Add user message
        messages.write().push(ChatMessage {
            role: "user".to_string(),
            content: question.clone(),
            sources: Vec::new(),
        });
        input_text.set(String::new());
        error_msg.set(None);
        loading.set(true);

        spawn(async move {
            match client::chat(&job_id, &question).await {
                Ok(response) => {
                    messages.write().push(ChatMessage {
                        role: "assistant".to_string(),
                        content: response.answer,
                        sources: response.sources,
                    });
                }
                Err(e) => {
                    error_msg.set(Some(e));
                }
            }
            loading.set(false);
        });
    };

    // Handle Enter key in input
    let on_keydown = move |evt: KeyboardEvent| {
        if evt.key() == Key::Enter && !evt.modifiers().contains(Modifiers::SHIFT) {
            let question = input_text.read().trim().to_string();
            if question.is_empty() || *loading.read() {
                return;
            }

            let job_id = state.read().active_job_id.clone();
            let Some(job_id) = job_id else {
                error_msg.set(Some("No active job selected.".to_string()));
                return;
            };

            messages.write().push(ChatMessage {
                role: "user".to_string(),
                content: question.clone(),
                sources: Vec::new(),
            });
            input_text.set(String::new());
            error_msg.set(None);
            loading.set(true);

            spawn(async move {
                match client::chat(&job_id, &question).await {
                    Ok(response) => {
                        messages.write().push(ChatMessage {
                            role: "assistant".to_string(),
                            content: response.answer,
                            sources: response.sources,
                        });
                    }
                    Err(e) => {
                        error_msg.set(Some(e));
                    }
                }
                loading.set(false);
            });
        }
    };

    rsx! {
        div { class: "chat-panel",
            // Message area
            div { class: "chat-messages",
                if messages.read().is_empty() && error_msg.read().is_none() {
                    div { class: "chat-empty",
                        "Ask a question about the scraped documentation."
                    }
                }
                {
                    let msgs = messages.read().clone();
                    rsx! {
                        for (i, msg) in msgs.iter().enumerate() {
                            div {
                                class: if msg.role == "user" { "chat-bubble chat-user" } else { "chat-bubble chat-assistant" },
                                key: "{i}",
                                div { class: "chat-role",
                                    if msg.role == "user" { "You" } else { "AI" }
                                }
                                div { class: "chat-content", "{msg.content}" }
                                if !msg.sources.is_empty() {
                                    div { class: "chat-sources",
                                        span { class: "chat-sources-label", "Sources: " }
                                        {
                                            let sources = msg.sources.clone();
                                            rsx! {
                                                for source in sources.iter() {
                                                    span {
                                                        class: "chat-source-link",
                                                        onclick: {
                                                            let source = source.clone();
                                                            move |_| {
                                                                let mut s = state.write();
                                                                s.selected_file = Some(source.clone());
                                                                s.panels.preview = true;
                                                                s.panels.explorer = true;
                                                            }
                                                        },
                                                        "{source}"
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
                if *loading.read() {
                    div { class: "chat-bubble chat-assistant chat-typing",
                        div { class: "chat-role", "AI" }
                        div { class: "chat-content chat-loading", "Thinking..." }
                    }
                }
                if let Some(err) = error_msg.read().as_ref() {
                    div { class: "chat-error", "{err}" }
                }
            }

            // Input area
            div { class: "chat-input-area",
                input {
                    class: "chat-input",
                    r#type: "text",
                    placeholder: "Ask about the documentation...",
                    value: "{input_text}",
                    disabled: *loading.read(),
                    oninput: move |evt| input_text.set(evt.value()),
                    onkeydown: on_keydown,
                }
                button {
                    class: "chat-send-btn",
                    disabled: *loading.read() || input_text.read().trim().is_empty(),
                    onclick: send_message,
                    "Send"
                }
            }
        }
    }
}
