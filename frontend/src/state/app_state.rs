//! Global application state.

use crate::api::types::{FileTreeNode, JobResponse};

/// Which panel windows are currently open.
#[derive(Clone, Debug, PartialEq)]
pub struct OpenPanels {
    pub scraper: bool,
    pub explorer: bool,
    pub preview: bool,
    pub terminal: bool,
    pub ai_chat: bool,
}

impl Default for OpenPanels {
    fn default() -> Self {
        Self {
            scraper: true,
            explorer: false,
            preview: false,
            terminal: true,
            ai_chat: false,
        }
    }
}

/// Global application state shared via context.
#[derive(Clone, Debug)]
#[allow(dead_code)]
pub struct AppState {
    /// Currently open panels
    pub panels: OpenPanels,
    /// Active job ID (if any)
    pub active_job_id: Option<String>,
    /// List of all jobs
    pub jobs: Vec<JobResponse>,
    /// File tree for active job
    pub file_tree: Vec<FileTreeNode>,
    /// Currently selected file path
    pub selected_file: Option<String>,
    /// Preview content (markdown)
    pub preview_content: Option<String>,
    /// Terminal log messages
    pub log_messages: Vec<String>,
}

impl Default for AppState {
    fn default() -> Self {
        Self {
            panels: OpenPanels::default(),
            active_job_id: None,
            jobs: Vec::new(),
            file_tree: Vec::new(),
            selected_file: None,
            preview_content: None,
            log_messages: vec!["MiniMax Scraper v0.2.1 ready.".to_string()],
        }
    }
}
