use crate::models::{Event, Project, ProtocolRun, QueueJob, StepRun};
use serde_json::Value;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Page {
    Dashboard,
    Projects,
    Protocols,
    Steps,
    Events,
    Queues,
    Settings,
}

impl Default for Page {
    fn default() -> Self {
        Page::Dashboard
    }
}

impl Page {
    pub fn next(self) -> Self {
        match self {
            Page::Dashboard => Page::Projects,
            Page::Projects => Page::Protocols,
            Page::Protocols => Page::Steps,
            Page::Steps => Page::Events,
            Page::Events => Page::Queues,
            Page::Queues => Page::Settings,
            Page::Settings => Page::Dashboard,
        }
    }

    pub fn prev(self) -> Self {
        match self {
            Page::Dashboard => Page::Settings,
            Page::Projects => Page::Dashboard,
            Page::Protocols => Page::Projects,
            Page::Steps => Page::Protocols,
            Page::Events => Page::Steps,
            Page::Queues => Page::Events,
            Page::Settings => Page::Queues,
        }
    }
}

#[derive(Debug, Default, Clone)]
pub struct AppState {
    pub page: Page,
    pub projects: Vec<Project>,
    pub project_index: Option<usize>,
    pub protocols: Vec<ProtocolRun>,
    pub protocol_index: Option<usize>,
    pub steps: Vec<StepRun>,
    pub step_index: Option<usize>,
    pub step_filter: Option<String>,
    pub events: Vec<Event>,
    pub event_index: Option<usize>,
    pub recent_events: Vec<Event>,
    pub recent_event_index: Option<usize>,
    pub queue_stats: Value,
    pub queue_jobs: Vec<QueueJob>,
    pub branches: Vec<String>,
    pub branch_index: Option<usize>,
    pub job_status_filter: Option<String>,
    pub status: String,
    pub last_error: Option<String>,
    pub refreshing: bool,
}

impl AppState {
    pub fn select_project(&mut self, delta: i32) {
        self.project_index = move_index(self.project_index, self.projects.len(), delta);
    }

    pub fn select_protocol(&mut self, delta: i32) {
        self.protocol_index = move_index(self.protocol_index, self.protocols.len(), delta);
    }

    pub fn select_step(&mut self, delta: i32) {
        self.step_index = move_index(self.step_index, self.steps.len(), delta);
    }

    pub fn selected_project_id(&self) -> Option<i64> {
        self.project_index
            .and_then(|idx| self.projects.get(idx))
            .map(|p| p.id)
    }

    pub fn selected_protocol_id(&self) -> Option<i64> {
        self.protocol_index
            .and_then(|idx| self.protocols.get(idx))
            .map(|p| p.id)
    }

    pub fn selected_step_id(&self) -> Option<i64> {
        self.step_index
            .and_then(|idx| self.steps.get(idx))
            .map(|s| s.id)
    }

    pub fn select_branch(&mut self, delta: i32) {
        self.branch_index = move_index(self.branch_index, self.branches.len(), delta);
    }

    pub fn select_event(&mut self, delta: i32) {
        self.event_index = move_index(self.event_index, self.events.len(), delta);
    }
}

fn move_index(current: Option<usize>, len: usize, delta: i32) -> Option<usize> {
    if len == 0 {
        return None;
    }
    let idx = current.unwrap_or(0) as i32 + delta;
    let idx = idx.clamp(0, (len as i32) - 1);
    Some(idx as usize)
}
