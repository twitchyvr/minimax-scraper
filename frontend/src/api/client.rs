//! HTTP API client for communicating with the backend.
#![allow(dead_code)]

use gloo_net::http::Request;

use super::types::{CreateJobRequest, FileContentResponse, FileTreeNode, JobResponse};

const BASE_URL: &str = "/api";

/// Fetch all jobs.
pub async fn list_jobs() -> Result<Vec<JobResponse>, String> {
    let resp = Request::get(&format!("{BASE_URL}/jobs"))
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        resp.json().await.map_err(|e| format!("Parse error: {e}"))
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}

/// Create a new scrape job.
pub async fn create_job(url: &str, rate_limit: Option<f64>) -> Result<JobResponse, String> {
    let body = CreateJobRequest {
        url: url.to_string(),
        rate_limit,
    };

    let resp = Request::post(&format!("{BASE_URL}/jobs"))
        .json(&body)
        .map_err(|e| format!("Serialize error: {e}"))?
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        resp.json().await.map_err(|e| format!("Parse error: {e}"))
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}

/// Get a specific job.
pub async fn get_job(job_id: &str) -> Result<JobResponse, String> {
    let resp = Request::get(&format!("{BASE_URL}/jobs/{job_id}"))
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        resp.json().await.map_err(|e| format!("Parse error: {e}"))
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}

/// Cancel a running job.
pub async fn cancel_job(job_id: &str) -> Result<(), String> {
    let resp = Request::delete(&format!("{BASE_URL}/jobs/{job_id}"))
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        Ok(())
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}

/// Get the file tree for a job.
pub async fn get_file_tree(job_id: &str) -> Result<Vec<FileTreeNode>, String> {
    let resp = Request::get(&format!("{BASE_URL}/browse/{job_id}/tree"))
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        resp.json().await.map_err(|e| format!("Parse error: {e}"))
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}

/// Get the content of a specific file.
pub async fn get_file_content(job_id: &str, path: &str) -> Result<FileContentResponse, String> {
    let resp = Request::get(&format!("{BASE_URL}/browse/{job_id}/file?path={path}"))
        .send()
        .await
        .map_err(|e| format!("Network error: {e}"))?;

    if resp.ok() {
        resp.json().await.map_err(|e| format!("Parse error: {e}"))
    } else {
        Err(format!("HTTP {}", resp.status()))
    }
}
