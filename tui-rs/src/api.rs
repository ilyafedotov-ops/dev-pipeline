use crate::models::{BranchList, Event, Project, ProtocolRun, QueueJob, StepRun};
use anyhow::Result;
use reqwest::StatusCode;
use serde::de::DeserializeOwned;
use serde_json::Value;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ApiError {
    #[error("http error {status}: {message}")]
    Http { status: StatusCode, message: String },
    #[error("transport error: {0}")]
    Transport(#[from] reqwest::Error),
    #[error("unexpected response shape")]
    Unexpected,
}

#[derive(Clone)]
pub struct ApiClient {
    base_url: String,
    token: Option<String>,
    project_token: Option<String>,
    client: reqwest::Client,
}

impl ApiClient {
    pub fn new(
        base_url: String,
        token: Option<String>,
        project_token: Option<String>,
    ) -> Result<Self> {
        let client = reqwest::Client::builder().build()?;
        Ok(Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            token,
            project_token,
            client,
        })
    }

    fn auth_headers(&self) -> reqwest::header::HeaderMap {
        let mut headers = reqwest::header::HeaderMap::new();
        if let Some(token) = &self.token {
            if let Ok(val) = format!("Bearer {token}").parse() {
                headers.insert(reqwest::header::AUTHORIZATION, val);
            }
        }
        if let Some(token) = &self.project_token {
            if let Ok(val) = token.parse() {
                headers.insert("X-Project-Token", val);
            }
        }
        headers
    }

    async fn get<T: DeserializeOwned>(&self, path: &str) -> Result<T, ApiError> {
        let url = if path.starts_with("http") {
            path.to_string()
        } else {
            format!("{}/{}", self.base_url, path.trim_start_matches('/'))
        };
        let resp = self
            .client
            .get(url)
            .headers(self.auth_headers())
            .send()
            .await
            .map_err(ApiError::Transport)?;
        if !resp.status().is_success() {
            let status = resp.status();
            let message = resp
                .text()
                .await
                .unwrap_or_else(|_| "request failed".to_string());
            return Err(ApiError::Http { status, message });
        }
        resp.json::<T>().await.map_err(|_| ApiError::Unexpected)
    }

    async fn post_json<T: DeserializeOwned>(
        &self,
        path: &str,
        payload: Value,
    ) -> Result<T, ApiError> {
        let url = if path.starts_with("http") {
            path.to_string()
        } else {
            format!("{}/{}", self.base_url, path.trim_start_matches('/'))
        };
        let resp = self
            .client
            .post(url)
            .headers(self.auth_headers())
            .json(&payload)
            .send()
            .await
            .map_err(ApiError::Transport)?;
        if !resp.status().is_success() {
            let status = resp.status();
            let message = resp
                .text()
                .await
                .unwrap_or_else(|_| "request failed".to_string());
            return Err(ApiError::Http { status, message });
        }
        resp.json::<T>().await.map_err(|_| ApiError::Unexpected)
    }

    pub async fn projects(&self) -> Result<Vec<Project>, ApiError> {
        self.get("/projects").await
    }

    pub async fn protocols(&self, project_id: i64) -> Result<Vec<ProtocolRun>, ApiError> {
        self.get(&format!("/projects/{project_id}/protocols")).await
    }

    pub async fn steps(&self, protocol_id: i64) -> Result<Vec<StepRun>, ApiError> {
        self.get(&format!("/protocols/{protocol_id}/steps")).await
    }

    pub async fn events(&self, protocol_id: i64) -> Result<Vec<Event>, ApiError> {
        self.get(&format!("/protocols/{protocol_id}/events")).await
    }

    pub async fn recent_events(&self, limit: u32) -> Result<Vec<Event>, ApiError> {
        self.get(&format!("/events?limit={limit}")).await
    }

    pub async fn queue_stats(&self) -> Result<Value, ApiError> {
        self.get("/queues").await
    }

    pub async fn queue_jobs(&self, status: Option<&str>) -> Result<Vec<QueueJob>, ApiError> {
        let path = match status {
            Some(s) => format!("/queues/jobs?status={s}"),
            None => "/queues/jobs".to_string(),
        };
        self.get(&path).await
    }

    pub async fn branches(&self, project_id: i64) -> Result<BranchList, ApiError> {
        self.get(&format!("/projects/{project_id}/branches")).await
    }

    pub async fn delete_branch(&self, project_id: i64, branch: &str) -> Result<Value, ApiError> {
        let payload = serde_json::json!({ "confirm": true });
        self.post_json(
            &format!("/projects/{project_id}/branches/{branch}/delete"),
            payload,
        )
        .await
    }

    pub async fn create_project(
        &self,
        name: &str,
        git_url: &str,
        base_branch: &str,
    ) -> Result<Project, ApiError> {
        let payload = serde_json::json!({
            "name": name,
            "git_url": git_url,
            "base_branch": base_branch,
        });
        self.post_json("/projects", payload).await
    }

    pub async fn create_protocol(
        &self,
        project_id: i64,
        protocol_name: &str,
        base_branch: &str,
        description: Option<String>,
    ) -> Result<ProtocolRun, ApiError> {
        let payload = serde_json::json!({
            "protocol_name": protocol_name,
            "base_branch": base_branch,
            "description": description,
            "status": "pending",
        });
        self.post_json(&format!("/projects/{project_id}/protocols"), payload)
            .await
    }

    pub async fn protocol_action(&self, protocol_id: i64, action: &str) -> Result<Value, ApiError> {
        self.post_json(
            &format!("/protocols/{protocol_id}/actions/{action}"),
            Value::Null,
        )
        .await
    }

    pub async fn protocol_open_pr(&self, protocol_id: i64) -> Result<Value, ApiError> {
        self.post_json(
            &format!("/protocols/{protocol_id}/actions/open_pr"),
            Value::Null,
        )
        .await
    }

    pub async fn step_run_next(&self, protocol_id: i64) -> Result<Value, ApiError> {
        self.post_json(
            &format!("/protocols/{protocol_id}/actions/run_next_step"),
            Value::Null,
        )
        .await
    }

    pub async fn step_retry_latest(&self, protocol_id: i64) -> Result<Value, ApiError> {
        self.post_json(
            &format!("/protocols/{protocol_id}/actions/retry_latest"),
            Value::Null,
        )
        .await
    }

    pub async fn step_run_qa(&self, step_id: i64) -> Result<Value, ApiError> {
        self.post_json(&format!("/steps/{step_id}/actions/run_qa"), Value::Null)
            .await
    }

    pub async fn step_approve(&self, step_id: i64) -> Result<Value, ApiError> {
        self.post_json(&format!("/steps/{step_id}/actions/approve"), Value::Null)
            .await
    }

    pub async fn spec_audit(
        &self,
        project_id: Option<i64>,
        protocol_id: Option<i64>,
        backfill: bool,
        interval_seconds: Option<i64>,
    ) -> Result<Value, ApiError> {
        let payload = serde_json::json!({
            "project_id": project_id,
            "protocol_id": protocol_id,
            "backfill": backfill,
            "interval_seconds": interval_seconds,
        });
        self.post_json("/specs/audit", payload).await
    }

    pub async fn import_codemachine(
        &self,
        project_id: i64,
        protocol_name: &str,
        workspace_path: &str,
        base_branch: &str,
        description: Option<String>,
        enqueue: bool,
    ) -> Result<Value, ApiError> {
        let payload = serde_json::json!({
            "protocol_name": protocol_name,
            "workspace_path": workspace_path,
            "base_branch": base_branch,
            "description": description,
            "enqueue": enqueue,
        });
        self.post_json(
            &format!("/projects/{project_id}/codemachine/import"),
            payload,
        )
        .await
    }

    pub fn base_url(&self) -> &str {
        &self.base_url
    }

    pub fn has_token(&self) -> bool {
        self.token.is_some()
    }

    pub fn has_project_token(&self) -> bool {
        self.project_token.is_some()
    }
}
