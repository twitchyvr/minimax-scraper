//! Shared API types matching the backend Pydantic schemas.
#![allow(dead_code)]

use serde::{Deserialize, Serialize};

/// Request to create a new scrape job.
#[derive(Serialize, Clone, Debug)]
pub struct CreateJobRequest {
    pub url: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub rate_limit: Option<f64>,
}

/// Response for a scrape job.
#[derive(Deserialize, Clone, Debug, PartialEq)]
pub struct JobResponse {
    pub id: String,
    pub url: String,
    pub status: String,
    pub discovery_method: Option<String>,
    pub total_pages: u32,
    pub scraped_pages: u32,
    pub output_dir: Option<String>,
    pub error_message: Option<String>,
    pub progress_pct: f64,
}

/// Recursive file tree node.
#[derive(Deserialize, Clone, Debug, PartialEq)]
pub struct FileTreeNode {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    #[serde(default)]
    pub children: Vec<FileTreeNode>,
    #[serde(default)]
    pub word_count: u32,
}

/// File content response.
#[derive(Deserialize, Clone, Debug)]
pub struct FileContentResponse {
    pub path: String,
    pub content: String,
}

/// Request to send a chat message to AI.
#[derive(Serialize, Clone, Debug)]
pub struct ChatRequest {
    pub question: String,
    pub job_id: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub top_k: Option<u32>,
}

/// Response from the AI chat endpoint.
#[derive(Deserialize, Clone, Debug)]
pub struct ChatResponse {
    pub answer: String,
    pub sources: Vec<String>,
    #[serde(default)]
    pub model: String,
    #[serde(default)]
    pub prompt_tokens: u32,
    #[serde(default)]
    pub completion_tokens: u32,
}

/// Typed WebSocket message from the backend.
///
/// Uses serde's internally-tagged enum representation so that
/// `{"type": "progress", ...}` deserializes into `WsMessage::Progress { .. }`.
#[derive(Deserialize, Clone, Debug)]
#[serde(tag = "type")]
pub enum WsMessage {
    /// Real-time scrape progress update.
    #[serde(rename = "progress")]
    Progress {
        job_id: String,
        scraped: u32,
        total: u32,
        current_url: String,
    },
    /// Job completed successfully.
    #[serde(rename = "complete")]
    Complete {
        job_id: String,
        total_pages: u32,
        output_dir: String,
    },
    /// Job encountered an error.
    #[serde(rename = "error")]
    Error { job_id: String, message: String },
}
