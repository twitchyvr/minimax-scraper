//! WebSocket hook for real-time scrape progress updates.

use dioxus::prelude::*;
use futures_util::StreamExt;
use gloo_net::websocket::{Message, futures::WebSocket};
use gloo_timers::future::TimeoutFuture;

use crate::api::{client, types::WsMessage};
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

                            // WS closed — poll REST API for current job status
                            // before deciding whether to reconnect. This handles
                            // the case where the job completed while WS was down.
                            if let Ok(job) = client::get_job(&job_id).await {
                                let is_terminal = matches!(
                                    job.status.as_str(),
                                    "complete" | "failed" | "cancelled"
                                );
                                // Update the job in state from the REST response
                                let mut s = state.write();
                                if let Some(j) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                                    j.status = job.status.clone();
                                    j.total_pages = job.total_pages;
                                    j.scraped_pages = job.scraped_pages;
                                    j.progress_pct = job.progress_pct;
                                    j.output_dir = job.output_dir.clone();
                                    j.error_message = job.error_message.clone();
                                    j.discovery_method = job.discovery_method.clone();
                                }
                                if is_terminal {
                                    s.log_messages.push(format!(
                                        "[INFO] Job {job_id} status: {} (via REST poll)",
                                        job.status
                                    ));
                                    drop(s);
                                    break;
                                }
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
///
/// Uses exhaustive pattern matching on the `WsMessage` enum — the compiler
/// ensures every variant is handled and every field is present (no more
/// `unwrap_or` on Optional fields).
fn handle_ws_message(msg: WsMessage, job_id: &str, state: &mut Signal<AppState>) {
    match msg {
        WsMessage::Progress {
            scraped,
            total,
            current_url,
            ..
        } => {
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
        WsMessage::Complete {
            total_pages,
            output_dir,
            ..
        } => {
            let mut s = state.write();
            if let Some(job) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                job.status = "complete".to_string();
                job.total_pages = total_pages;
                job.scraped_pages = total_pages;
                job.progress_pct = 100.0;
                job.output_dir = Some(output_dir.clone());
            }
            s.log_messages.push(format!(
                "[INFO] Job {job_id} complete — {total_pages} pages scraped"
            ));
        }
        WsMessage::Error { message, .. } => {
            let mut s = state.write();
            if let Some(job) = s.jobs.iter_mut().find(|j| j.id == job_id) {
                job.status = "failed".to_string();
                job.error_message = Some(message.clone());
            }
            s.log_messages
                .push(format!("[ERROR] Job {job_id}: {message}"));
        }
    }
}
