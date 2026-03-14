//! File explorer panel — recursive tree view with expand/collapse and file selection.

use std::collections::HashSet;

use dioxus::prelude::*;

use crate::api::client;
use crate::api::types::FileTreeNode;
use crate::state::app_state::AppState;

/// File explorer panel that loads a tree for the active job's completed scrape.
#[component]
pub fn ExplorerPanel() -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let expanded = use_signal(HashSet::<String>::new);
    let mut loading = use_signal(|| false);
    let mut loaded_job = use_signal(|| None::<String>);

    // Determine which completed job to browse (only complete jobs).
    let browse_job_id = {
        let s = state.read();
        s.jobs
            .iter()
            .find(|j| Some(j.id.as_str()) == s.active_job_id.as_deref() && j.status == "complete")
            .or_else(|| s.jobs.iter().find(|j| j.status == "complete"))
            .map(|j| j.id.clone())
    };

    // Load tree when we have a new completed job to browse.
    let should_load = browse_job_id.is_some() && browse_job_id != *loaded_job.read();
    if should_load && let Some(job_id) = browse_job_id.clone() {
        loaded_job.set(Some(job_id.clone()));
        loading.set(true);
        spawn(async move {
            match client::get_file_tree(&job_id).await {
                Ok(tree) => {
                    let mut s = state.write();
                    s.file_tree = tree;
                    s.selected_file = None;
                    s.preview_content = None;
                    s.log_messages
                        .push(format!("[INFO] File tree loaded for job {job_id}"));
                }
                Err(e) => {
                    state
                        .write()
                        .log_messages
                        .push(format!("[ERROR] Failed to load file tree: {e}"));
                }
            }
            loading.set(false);
        });
    }

    let tree = state.read().file_tree.clone();
    let has_job = browse_job_id.is_some();

    rsx! {
        div { class: "explorer-panel",
            if !has_job {
                p { class: "explorer-empty", "No completed job to browse. Run a scrape first." }
            } else if *loading.read() {
                p { class: "explorer-loading", "Loading file tree..." }
            } else if tree.is_empty() {
                p { class: "explorer-empty", "No files found. The scrape may still be running." }
            } else {
                div { class: "explorer-tree",
                    for node in tree.into_iter() {
                        TreeNode {
                            node: node,
                            depth: 0,
                            expanded: expanded,
                        }
                    }
                }
            }
        }
    }
}

/// A single node in the file tree (recursive for directories).
#[component]
fn TreeNode(node: FileTreeNode, depth: u32, expanded: Signal<HashSet<String>>) -> Element {
    let mut state = use_context::<Signal<AppState>>();
    let is_dir = node.is_dir;
    let path = node.path.clone();
    let name = node.name.clone();
    let children = node.children.clone();
    let word_count = node.word_count;
    let is_expanded = expanded.read().contains(&path);
    let is_selected = state.read().selected_file.as_deref() == Some(path.as_str());

    let indent_px = depth * 16;
    let indent_style = format!("padding-left: {indent_px}px");

    let icon = if is_dir {
        if is_expanded { "▾ 📂" } else { "▸ 📁" }
    } else {
        "  📄"
    };

    let node_class = if is_selected && !is_dir {
        "explorer-node explorer-node-selected"
    } else {
        "explorer-node"
    };

    let path_click = path.clone();

    let on_click = move |_| {
        let p = path_click.clone();
        if is_dir {
            let mut exp = expanded.write();
            if exp.contains(&p) {
                exp.remove(&p);
            } else {
                exp.insert(p);
            }
        } else {
            // Select file and load content
            let selected = state.read().selected_file.clone();
            if selected.as_deref() == Some(p.as_str()) {
                return; // Already selected
            }
            {
                let mut s = state.write();
                s.selected_file = Some(p.clone());
                s.preview_content = None; // Show "Loading..." while fetching
            }

            // Find the completed job ID for fetching
            let job_id = {
                let s = state.read();
                s.jobs
                    .iter()
                    .find(|j| {
                        Some(j.id.as_str()) == s.active_job_id.as_deref() && j.status == "complete"
                    })
                    .or_else(|| s.jobs.iter().find(|j| j.status == "complete"))
                    .map(|j| j.id.clone())
            };

            if let Some(job_id) = job_id {
                spawn(async move {
                    match client::get_file_content(&job_id, &p).await {
                        Ok(resp) => {
                            state.write().preview_content = Some(resp.content);
                        }
                        Err(e) => {
                            state
                                .write()
                                .log_messages
                                .push(format!("[ERROR] Failed to load file: {e}"));
                        }
                    }
                });
            }
        }
    };

    rsx! {
        div {
            class: "{node_class}",
            style: "{indent_style}",
            onclick: on_click,
            span { class: "explorer-icon", "{icon}" }
            span { class: "explorer-name", "{name}" }
            if !is_dir && word_count > 0 {
                span { class: "explorer-meta", "~{word_count}w" }
            }
        }
        if is_dir && is_expanded {
            for child in children.into_iter() {
                TreeNode {
                    node: child,
                    depth: depth + 1,
                    expanded: expanded,
                }
            }
        }
    }
}
