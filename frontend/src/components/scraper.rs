//! Scraper panel — new job form, real-time progress, and job history.

use dioxus::prelude::*;

use crate::api::client;
use crate::hooks::use_websocket::use_job_websocket;
use crate::state::app_state::AppState;

/// Scraper panel with URL input and job management.
#[component]
pub fn ScraperPanel() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut url_input = use_signal(|| "https://platform.minimax.io/docs".to_string());
    let mut is_loading = use_signal(|| false);
    let mut error_msg = use_signal(|| None::<String>);

    // Load jobs once on mount
    use_hook(move || {
        spawn(async move {
            match client::list_jobs().await {
                Ok(jobs) => state.write().jobs = jobs,
                Err(e) => {
                    state.write().log_messages.push(format!("[ERROR] {e}"));
                }
            }
        });
    });

    // Connect WebSocket for the active job — always called (hook rules)
    let active_job_id = state.read().active_job_id.clone();
    use_job_websocket(active_job_id);

    let on_submit = move |_| {
        let url = url_input.read().clone();
        if url.is_empty() {
            return;
        }
        is_loading.set(true);
        error_msg.set(None);

        spawn(async move {
            match client::create_job(&url, None).await {
                Ok(job) => {
                    let mut s = state.write();
                    s.log_messages
                        .push(format!("[INFO] Job created: {} ({})", job.id, job.url));
                    s.active_job_id = Some(job.id.clone());
                    s.jobs.insert(0, job);
                }
                Err(e) => {
                    error_msg.set(Some(e.clone()));
                    state.write().log_messages.push(format!("[ERROR] {e}"));
                }
            }
            is_loading.set(false);
        });
    };

    rsx! {
        div { class: "scraper-panel",
            // URL input form
            div { class: "scraper-form",
                input {
                    class: "scraper-input",
                    r#type: "text",
                    placeholder: "Enter documentation URL...",
                    value: "{url_input}",
                    oninput: move |e| url_input.set(e.value()),
                }
                button {
                    class: "scraper-btn",
                    disabled: *is_loading.read(),
                    onclick: on_submit,
                    if *is_loading.read() { "Scraping..." } else { "Scrape" }
                }
            }

            if let Some(err) = error_msg.read().as_ref() {
                div { class: "scraper-error", "{err}" }
            }

            // Job list
            div { class: "scraper-jobs",
                h3 { "Jobs" }
                {
                    let jobs = state.read().jobs.clone();
                    if jobs.is_empty() {
                        rsx! { p { class: "scraper-empty", "No jobs yet. Enter a URL above to start scraping." } }
                    } else {
                        rsx! {
                            for job in jobs.into_iter() {
                                JobCard { job: job }
                            }
                        }
                    }
                }
            }
        }
    }
}

/// Individual job card with progress and cancel button.
#[component]
fn JobCard(job: crate::api::types::JobResponse) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let status_class = format!("scraper-job-status status-{}", job.status);
    let is_active = matches!(job.status.as_str(), "pending" | "discovering" | "scraping");
    let show_progress = job.total_pages > 0;
    let progress_style = format!("width: {}%", job.progress_pct);
    let progress_label = format!(
        "{}/{} pages ({:.0}%)",
        job.scraped_pages, job.total_pages, job.progress_pct
    );
    let job_id = job.id.clone();

    let on_cancel = move |_| {
        let jid = job_id.clone();
        spawn(async move {
            match client::cancel_job(&jid).await {
                Ok(()) => {
                    let mut s = state.write();
                    if let Some(j) = s.jobs.iter_mut().find(|j| j.id == jid) {
                        j.status = "cancelled".to_string();
                    }
                    s.log_messages.push(format!("[INFO] Job {jid} cancelled"));
                }
                Err(e) => {
                    state
                        .write()
                        .log_messages
                        .push(format!("[ERROR] Cancel failed: {e}"));
                }
            }
        });
    };

    rsx! {
        div {
            class: "scraper-job",
            key: "{job.id}",
            div { class: "scraper-job-header",
                span { class: "scraper-job-url", "{job.url}" }
                div { class: "scraper-job-actions",
                    span { class: "{status_class}", "{job.status}" }
                    if is_active {
                        button {
                            class: "scraper-cancel-btn",
                            onclick: on_cancel,
                            "Cancel"
                        }
                    }
                }
            }
            if show_progress {
                div { class: "scraper-job-progress",
                    div {
                        class: "progress-bar",
                        div {
                            class: "progress-fill",
                            style: "{progress_style}",
                        }
                    }
                    span { class: "progress-text", "{progress_label}" }
                }
            }
            if let Some(err) = &job.error_message {
                div { class: "scraper-job-error", "{err}" }
            }
        }
    }
}
