use chrono::{DateTime, Utc};
use serde::Deserialize;
use serde_json::Value;

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Project {
    pub id: i64,
    pub name: String,
    #[serde(default)]
    pub git_url: Option<String>,
    #[serde(default)]
    pub base_branch: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct ProtocolRun {
    pub id: i64,
    pub project_id: i64,
    pub protocol_name: String,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub base_branch: Option<String>,
    #[serde(default)]
    pub description: Option<String>,
    #[serde(default)]
    pub updated_at: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct StepRun {
    pub id: i64,
    pub protocol_run_id: i64,
    pub step_index: i32,
    pub step_name: String,
    #[serde(default)]
    pub step_type: Option<String>,
    pub status: String,
    #[serde(default)]
    pub retries: i32,
    #[serde(default)]
    pub summary: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct Event {
    pub id: i64,
    pub protocol_run_id: i64,
    #[serde(default)]
    pub step_run_id: Option<i64>,
    pub event_type: String,
    pub message: String,
    pub created_at: String,
    #[serde(default)]
    pub metadata: Option<Value>,
    #[serde(default)]
    pub protocol_name: Option<String>,
    #[serde(default)]
    pub project_id: Option<i64>,
    #[serde(default)]
    pub project_name: Option<String>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct QueueJob {
    #[serde(default)]
    pub job_id: Option<String>,
    #[serde(default)]
    pub status: Option<String>,
    #[serde(default)]
    pub enqueued_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub started_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub ended_at: Option<DateTime<Utc>>,
    #[serde(default)]
    pub payload: Option<Value>,
}

#[derive(Debug, Clone, Deserialize, Default)]
pub struct BranchList {
    #[serde(default)]
    pub branches: Vec<String>,
}
