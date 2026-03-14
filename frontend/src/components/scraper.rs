//! Scraper panel — new job form and job list.

use dioxus::prelude::*;

use crate::api::client;
use crate::state::app_state::AppState;

/// Scraper panel with URL input and job management.
#[component]
pub fn ScraperPanel() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let mut url_input = use_signal(|| "https://platform.minimax.io/docs".to_string());
    let mut is_loading = use_signal(|| false);
    let mut error_msg = use_signal(|| None::<String>);

    // Load jobs once on mount — use_hook runs exactly once per component instance
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
                                {
                                    let status_class = format!("scraper-job-status status-{}", job.status);
                                    let progress_style = format!("width: {}%", job.progress_pct);
                                    let progress_label = format!(
                                        "{}/{} pages ({}%)",
                                        job.scraped_pages, job.total_pages, job.progress_pct
                                    );
                                    let show_progress = job.total_pages > 0;
                                    rsx! {
                                        div {
                                            class: "scraper-job",
                                            key: "{job.id}",
                                            div { class: "scraper-job-header",
                                                span { class: "scraper-job-url", "{job.url}" }
                                                span { class: "{status_class}", "{job.status}" }
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
}
