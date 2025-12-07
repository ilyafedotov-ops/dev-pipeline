mod api;
mod app;
mod models;
mod state;
mod ui;

use anyhow::Result;
use api::ApiClient;
use app::App;
use std::env;
use std::time::Duration;
use tracing_subscriber::EnvFilter;

#[tokio::main]
async fn main() -> Result<()> {
    let _ = tracing_subscriber::fmt()
        .with_env_filter(
            EnvFilter::try_from_default_env().unwrap_or_else(|_| EnvFilter::new("info")),
        )
        .with_target(false)
        .try_init();

    let api_base =
        env::var("TASKSGODZILLA_API_BASE").unwrap_or_else(|_| "http://localhost:8011".to_string());
    let api_token = env::var("TASKSGODZILLA_API_TOKEN").ok();
    let project_token = env::var("TASKSGODZILLA_PROJECT_TOKEN").ok();
    let refresh_secs = env::var("TASKSGODZILLA_TUI_REFRESH_SECS")
        .ok()
        .and_then(|s| s.parse::<u64>().ok())
        .unwrap_or(4);

    let client = ApiClient::new(api_base, api_token, project_token)?;
    let mut app = App::new(client, Duration::from_secs(refresh_secs));
    app.run().await
}
