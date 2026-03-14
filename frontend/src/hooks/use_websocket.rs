//! WebSocket hook for real-time scrape progress updates.

use dioxus::prelude::*;
use futures_util::StreamExt;
use gloo_net::websocket::{Message, futures::WebSocket};
use gloo_timers::future::TimeoutFuture;

use crate::api::types::WsMessage;
use crate::state::app_state::AppState;

/// Maximum number of log messages to keep in state.
const MAX_LOG_MESSAGES: usize = 500;

/// Connect a WebSocket to the active job (if any) and dispatch messages to app state.
/// Always called unconditionally — handles None internally.
/// Automatically reconnects on disconnect with exponential backoff.
pub fn use_job_websocket(job_id: Option<String>) {
    let mut state = use_context::<Signal<AppState>>();
    let mut current_task = use_signal(|| None::<Task>);
    let mut connected_job = use_signal(|| None::<String>);

    // When job_id changes, cancel old task and start new one
    let job_changed = job_id != *connected_job.read();

    if job_changed {
        // Cancel previous WebSocket task
        if let Some(task) = current_task.write().take() {
            task.cancel();
        }
        connected_job.set(job_id.clone());

        if let Some(job_id) = job_id {
            let task = spawn(async move {
                let mut retry_delay_ms = 1000u32;
                let max_delay_ms = 16000u32;

                loop {
                    let ws_url = build_ws_url(&job_id);
                    push_log(
                        &mut state,
                        format!("[INFO] Connecting to WebSocket for job {job_id}..."),
                    );

                    match WebSocket::open(&ws_url) {
                        Ok(ws) => {
                            retry_delay_ms = 1000;
                            push_log(
                                &mut state,
                                format!("[INFO] WebSocket connected for job {job_id}"),
                            );

                            if let Err(closed) = listen_ws(ws, &job_id, &mut state).await {
                                push_log(
                                    &mut state,
                                    format!("[WARN] WebSocket closed for job {job_id}: {closed}"),
                                );
                            }

                            // Check if the job is done — no need to reconnect
                            let should_reconnect = {
                                let s = state.read();
                                s.jobs.iter().any(|j| {
                                    j.id == job_id
                                        && !matches!(
                                            j.status.as_str(),
                                            "complete" | "failed" | "cancelled"
                                        )
                                })
                            };

                            if !should_reconnect {
                                break;
                            }
                        }
                        Err(e) => {
                            push_log(
                                &mut state,
                                format!("[WARN] WebSocket connection failed: {e}"),
                            );
                        }
                    }

                    push_log(
                        &mut state,
                        format!("[INFO] Reconnecting in {retry_delay_ms}ms..."),
                    );
                    TimeoutFuture::new(retry_delay_ms).await;
                    retry_delay_ms = (retry_delay_ms * 2).min(max_delay_ms);
                }
            });
            current_task.set(Some(task));
        }
    }
}

/// Push a log message to state, enforcing the max size cap.
fn push_log(state: &mut Signal<AppState>, msg: String) {
    let mut s = state.write();
    s.log_messages.push(msg);
    if s.log_messages.len() > MAX_LOG_MESSAGES {
        let excess = s.log_messages.len() - MAX_LOG_MESSAGES;
        s.log_messages.drain(0..excess);
    }
}

/// Build the WebSocket URL from the current page location.
fn build_ws_url(job_id: &str) -> String {
    let window = web_sys::window().expect("no window");
    let location = window.location();
    let protocol = location.protocol().unwrap_or_default();
    let host = location.host().unwrap_or_default();
    let ws_protocol = if protocol == "https:" { "wss:" } else { "ws:" };
    format!("{ws_protocol}//{host}/api/ws/{job_id}")
}

/// Listen for messages on the WebSocket until it closes.
async fn listen_ws(
    mut ws: WebSocket,
    job_id: &str,
    state: &mut Signal<AppState>,
) -> Result<(), String> {
    while let Some(msg_result) = ws.next().await {
        match msg_result {
            Ok(Message::Text(text)) => match serde_json::from_str::<WsMessage>(&text) {
                Ok(ws_msg) => handle_ws_message(ws_msg, job_id, state),
                Err(e) => {
                    push_log(state, format!("[WARN] Failed to parse WS message: {e}"));
                }
            },
            Ok(Message::Bytes(_)) => {}
            Err(e) => {
                return Err(format!("{e}"));
            }
        }
    }

    Err("connection closed".to_string())
}

/// Dispatch a parsed WebSocket message to update application state.
fn handle_ws_message(msg: WsMessage, job_id: &str, state: &mut Signal<AppState>) {
    match msg.msg_type.as_str() {
        "progress" => {
            let scraped = msg.scraped.unwrap_or(0);
            let total = msg.total.unwrap_or(0);
            let current_url = msg.current_url.clone().unwrap_or_default();

            let mut s = state.write();
            if let Some(job) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                job.scraped_pages = scraped;
                job.total_pages = total;
                job.status = "scraping".to_string();
                if total > 0 {
                    job.progress_pct = ((scraped as f64 / total as f64) * 100.0).clamp(0.0, 100.0);
                }
            }
            if !current_url.is_empty() {
                s.log_messages
                    .push(format!("[INFO] Scraped ({scraped}/{total}): {current_url}"));
                // Enforce log cap inline for high-frequency progress messages
                if s.log_messages.len() > MAX_LOG_MESSAGES {
                    let excess = s.log_messages.len() - MAX_LOG_MESSAGES;
                    s.log_messages.drain(0..excess);
                }
            }
        }
        "complete" => {
            let total = msg.total_pages.unwrap_or(0);

            let mut s = state.write();
            if let Some(job) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                job.status = "complete".to_string();
                job.total_pages = total;
                job.scraped_pages = total;
                job.progress_pct = 100.0;
                job.output_dir = msg.output_dir.clone();
            }
            s.log_messages.push(format!(
                "[INFO] Job {job_id} complete — {total} pages scraped"
            ));
        }
        "error" => {
            let error_msg = msg
                .message
                .clone()
                .unwrap_or_else(|| "Unknown error".to_string());

            let mut s = state.write();
            if let Some(job) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                job.status = "failed".to_string();
                job.error_message = Some(error_msg.clone());
            }
            s.log_messages
                .push(format!("[ERROR] Job {job_id}: {error_msg}"));
        }
        other => {
            push_log(state, format!("[WARN] Unknown WS message type: {other}"));
        }
    }
}
