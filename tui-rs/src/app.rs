use crate::{
    api::{ApiClient, ApiError},
    state::{AppState, Page},
    ui,
};
use anyhow::Result;
use crossterm::{
    event::{Event, EventStream, KeyCode, KeyEvent, KeyModifiers},
    execute,
    terminal::{disable_raw_mode, enable_raw_mode, EnterAlternateScreen, LeaveAlternateScreen},
};
use futures::StreamExt;
use ratatui::{backend::CrosstermBackend, Terminal};
use std::time::Duration;
use std::{env, io};
use tokio::time::{interval, Instant};

pub struct App {
    pub state: AppState,
    pub client: ApiClient,
    pub refresh_interval: Duration,
    modal: Option<Modal>,
    screen: Screen,
    pub auto_login: bool,
    login_form: LoginForm,
    menu_index: usize,
    welcome_index: usize,
}

#[derive(Debug, Clone)]
pub(crate) struct InputField {
    pub label: String,
    pub value: String,
    pub is_secret: bool,
}

#[derive(Debug, Clone)]
pub(crate) enum Modal {
    Form {
        title: String,
        fields: Vec<InputField>,
        focus: usize,
        action: ModalAction,
    },
    Confirm {
        title: String,
        message: String,
        action: ModalAction,
    },
    Palette {
        items: Vec<QuickAction>,
        index: usize,
    },
    Message(String),
}

#[derive(Debug, Clone, Copy)]
pub(crate) enum ModalAction {
    CreateProject,
    CreateProtocol,
    SpecAudit,
    ImportCodeMachine,
    TokenConfig,
    DeleteBranch,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Screen {
    Welcome,
    Login,
    Menu,
    SettingsInfo,
    Help,
    Version,
    Dashboard,
}

#[derive(Debug, Clone)]
pub(crate) struct LoginForm {
    pub fields: Vec<InputField>,
    pub focus: usize,
}

#[derive(Debug, Clone, Copy)]
pub(crate) enum QuickAction {
    RunNext,
    RetryLatest,
    RunQa,
    Approve,
    OpenPr,
    StartProtocol,
    PauseProtocol,
    ResumeProtocol,
    CancelProtocol,
    ImportCodeMachine,
    SpecAudit,
    Configure,
    Menu,
}

impl App {
    pub fn new(client: ApiClient, refresh_interval: Duration) -> Self {
        let auto_login = env::var("TASKSGODZILLA_TUI_AUTOLOGIN")
            .ok()
            .map(|v| v != "0" && v.to_lowercase() != "false")
            .unwrap_or(true);
        let login_form = LoginForm {
            fields: vec![
                InputField {
                    label: "API base".into(),
                    value: client.base_url().to_string(),
                    is_secret: false,
                },
                InputField {
                    label: "API token (optional)".into(),
                    value: "".into(),
                    is_secret: true,
                },
                InputField {
                    label: "Project token (optional)".into(),
                    value: "".into(),
                    is_secret: true,
                },
            ],
            focus: 0,
        };
        Self {
            state: AppState {
                status: "Ready".to_string(),
                ..Default::default()
            },
            client,
            refresh_interval,
            modal: None,
            screen: Screen::Welcome,
            auto_login,
            login_form,
            menu_index: 0,
            welcome_index: 0,
        }
    }

    pub async fn run(&mut self) -> Result<()> {
        enable_raw_mode()?;
        let mut stdout = io::stdout();
        execute!(stdout, EnterAlternateScreen)?;
        let backend = CrosstermBackend::new(stdout);
        let mut terminal = Terminal::new(backend)?;
        terminal.clear()?;

        let mut reader = EventStream::new();
        let mut ticker = interval(self.refresh_interval);
        if self.screen == Screen::Dashboard {
            let _ = self.refresh_all().await;
        }

        loop {
            terminal.draw(|f| {
                ui::draw(
                    f,
                    self,
                    self.modal.as_ref(),
                    self.screen,
                    &self.login_form,
                    self.menu_index,
                    self.welcome_index,
                )
            })?;
            tokio::select! {
                maybe_event = reader.next() => {
                    if let Some(Ok(evt)) = maybe_event {
                        if self.handle_event(evt).await? {
                            break;
                        }
                    }
                }
                _ = ticker.tick() => {
                    self.refresh_scoped().await?;
                }
            }
        }

        disable_raw_mode()?;
        execute!(terminal.backend_mut(), LeaveAlternateScreen)?;
        terminal.show_cursor()?;
        Ok(())
    }

    async fn handle_event(&mut self, evt: Event) -> Result<bool> {
        match evt {
            Event::Key(key) => {
                if self.handle_modal_key(&key).await? {
                    return Ok(false);
                }
                if self.screen == Screen::Welcome {
                    return self.handle_welcome_key(key).await;
                }
                if matches!(
                    self.screen,
                    Screen::SettingsInfo | Screen::Help | Screen::Version
                ) {
                    return self.handle_info_key(key).await;
                }
                if self.screen == Screen::Login {
                    return self.handle_login_key(key).await;
                }
                if self.screen == Screen::Menu {
                    return self.handle_menu_key(key).await;
                }
                if self.handle_key(key).await? {
                    return Ok(true);
                }
            }
            _ => {}
        }
        Ok(false)
    }

    async fn handle_key(&mut self, key: KeyEvent) -> Result<bool> {
        if key.modifiers.contains(KeyModifiers::CONTROL) && key.code == KeyCode::Char('c') {
            return Ok(true);
        }
        match key.code {
            KeyCode::Char('q') => return Ok(true),
            KeyCode::Char('r') if !key.modifiers.contains(KeyModifiers::SHIFT) => {
                self.refresh_all().await?;
            }
            KeyCode::Char('m') => {
                self.screen = Screen::Menu;
                self.menu_index = 0;
            }
            KeyCode::Char('h') | KeyCode::Char('?') => {
                self.state.status = "Keys: tab/shift+tab/←/→ pages • arrows/j/k move • r refresh • q quit • n run next • t retry • y QA • a approve • o open PR • s start • p pause • e resume • x cancel • g new project • R new protocol • i import CM • A spec audit • c config • b reload branches • d delete branch • J cycle job filter • [/] branch cycle".into();
            }
            KeyCode::Char('g') => self.open_project_modal(),
            KeyCode::Char('R') => self.open_protocol_modal(),
            KeyCode::Char('c') => self.open_token_modal(),
            KeyCode::Char('i') => self.open_cm_modal(),
            KeyCode::Char('A') => self.open_spec_audit_modal(),
            KeyCode::Char('w') => {
                self.screen = Screen::Welcome;
                self.welcome_index = 0;
            }
            KeyCode::Enter => self.open_action_palette(),
            KeyCode::Char('b') => {
                self.load_branches().await?;
            }
            KeyCode::Char('d') => self.open_delete_branch_modal(),
            KeyCode::Char('J') => {
                self.cycle_job_filter().await?;
            }
            KeyCode::Tab => {
                self.state.page = self.state.page.next();
            }
            KeyCode::BackTab => {
                self.state.page = self.state.page.prev();
            }
            KeyCode::Right => {
                self.state.page = self.state.page.next();
            }
            KeyCode::Left => {
                self.state.page = self.state.page.prev();
            }
            KeyCode::Char('1') => self.state.page = Page::Dashboard,
            KeyCode::Char('2') => self.state.page = Page::Projects,
            KeyCode::Char('3') => self.state.page = Page::Protocols,
            KeyCode::Char('4') => self.state.page = Page::Steps,
            KeyCode::Char('5') => self.state.page = Page::Events,
            KeyCode::Char('6') => self.state.page = Page::Queues,
            KeyCode::Char('7') => self.state.page = Page::Settings,
            KeyCode::Down => {
                self.handle_down();
                self.refresh_selection().await?;
            }
            KeyCode::Up => {
                self.handle_up();
                self.refresh_selection().await?;
            }
            KeyCode::Char('j') => {
                self.handle_down();
                self.refresh_selection().await?;
            }
            KeyCode::Char('k') => {
                self.handle_up();
                self.refresh_selection().await?;
            }
            KeyCode::Char('[') => {
                self.state.select_branch(-1);
            }
            KeyCode::Char(']') => {
                self.state.select_branch(1);
            }
            KeyCode::Char('f') => {
                self.cycle_step_filter().await?;
            }
            KeyCode::Char('n') => self.run_next().await?,
            KeyCode::Char('t') => self.retry_latest().await?,
            KeyCode::Char('y') => self.run_qa_latest().await?,
            KeyCode::Char('a') => self.approve_latest().await?,
            KeyCode::Char('o') => self.open_pr().await?,
            KeyCode::Char('s') => self.protocol_action("start", "Planning enqueued.").await?,
            KeyCode::Char('p') => self.protocol_action("pause", "Protocol paused.").await?,
            KeyCode::Char('e') => self.protocol_action("resume", "Protocol resumed.").await?,
            KeyCode::Char('x') => {
                self.protocol_action("cancel", "Protocol cancelled.")
                    .await?
            }
            _ => {}
        }
        Ok(false)
    }

    async fn handle_welcome_key(&mut self, key: KeyEvent) -> Result<bool> {
        let items = ["Start TasksGodzilla", "Settings", "Help", "Version", "Quit"];
        match key.code {
            KeyCode::Up | KeyCode::Char('k') => {
                if self.welcome_index == 0 {
                    self.welcome_index = items.len().saturating_sub(1);
                } else {
                    self.welcome_index -= 1;
                }
            }
            KeyCode::Down | KeyCode::Char('j') | KeyCode::Tab => {
                self.welcome_index = (self.welcome_index + 1) % items.len();
            }
            KeyCode::BackTab => {
                if self.welcome_index == 0 {
                    self.welcome_index = items.len().saturating_sub(1);
                } else {
                    self.welcome_index -= 1;
                }
            }
            KeyCode::Char('1') => self.welcome_index = 0,
            KeyCode::Char('2') => self.welcome_index = 1,
            KeyCode::Char('3') => self.welcome_index = 2,
            KeyCode::Char('4') => self.welcome_index = 3,
            KeyCode::Char('5') => self.welcome_index = 4,
            KeyCode::Enter => match self.welcome_index {
                0 => {
                    if self.auto_login {
                        self.screen = Screen::Dashboard;
                        self.refresh_all().await?;
                    } else {
                        self.screen = Screen::Login;
                    }
                }
                1 => {
                    self.screen = Screen::SettingsInfo;
                }
                2 => {
                    self.screen = Screen::Help;
                }
                3 => {
                    self.screen = Screen::Version;
                }
                4 => return Ok(true),
                _ => {}
            },
            KeyCode::Esc | KeyCode::Char('q') => return Ok(true),
            _ => {}
        }
        Ok(false)
    }

    async fn handle_login_key(&mut self, key: KeyEvent) -> Result<bool> {
        match key.code {
            KeyCode::Tab => {
                self.login_form.focus = (self.login_form.focus + 1) % self.login_form.fields.len();
            }
            KeyCode::BackTab => {
                if self.login_form.focus == 0 {
                    self.login_form.focus = self.login_form.fields.len() - 1;
                } else {
                    self.login_form.focus -= 1;
                }
            }
            KeyCode::Enter => {
                let base = self.login_form.fields[0].value.trim();
                if base.is_empty() {
                    self.state.status = "API base required".into();
                    return Ok(false);
                }
                let token = self.login_form.fields[1].value.trim();
                let project_token = self.login_form.fields[2].value.trim();
                self.client = ApiClient::new(
                    base.to_string(),
                    if token.is_empty() {
                        None
                    } else {
                        Some(token.to_string())
                    },
                    if project_token.is_empty() {
                        None
                    } else {
                        Some(project_token.to_string())
                    },
                )?;
                self.state.status = format!("Connected to {base}");
                self.screen = Screen::Menu;
                self.menu_index = 0;
            }
            KeyCode::Esc => return Ok(true),
            KeyCode::Backspace => {
                if let Some(field) = self.login_form.fields.get_mut(self.login_form.focus) {
                    field.value.pop();
                }
            }
            KeyCode::Char(c) => {
                if let Some(field) = self.login_form.fields.get_mut(self.login_form.focus) {
                    field.value.push(c);
                }
            }
            _ => {}
        }
        Ok(false)
    }

    async fn handle_menu_key(&mut self, key: KeyEvent) -> Result<bool> {
        let items = ["Dashboard", "Configure API/token", "Quit"];
        match key.code {
            KeyCode::Up => {
                if self.menu_index == 0 {
                    self.menu_index = items.len() - 1;
                } else {
                    self.menu_index -= 1;
                }
            }
            KeyCode::Down => {
                self.menu_index = (self.menu_index + 1) % items.len();
            }
            KeyCode::Tab => {
                self.menu_index = (self.menu_index + 1) % items.len();
            }
            KeyCode::BackTab => {
                if self.menu_index == 0 {
                    self.menu_index = items.len() - 1;
                } else {
                    self.menu_index -= 1;
                }
            }
            KeyCode::Char('j') => {
                self.menu_index = (self.menu_index + 1) % items.len();
            }
            KeyCode::Char('k') => {
                if self.menu_index == 0 {
                    self.menu_index = items.len() - 1;
                } else {
                    self.menu_index -= 1;
                }
            }
            KeyCode::Char('1') => {
                self.menu_index = 0;
                self.screen = Screen::Dashboard;
                self.refresh_all().await?;
            }
            KeyCode::Char('2') => {
                self.menu_index = 1;
                self.open_token_modal();
            }
            KeyCode::Char('3') => return Ok(true),
            KeyCode::Enter => match self.menu_index {
                0 => {
                    self.screen = Screen::Dashboard;
                    self.refresh_all().await?;
                }
                1 => {
                    self.open_token_modal();
                }
                2 => return Ok(true),
                _ => {}
            },
            KeyCode::Char('q') => return Ok(true),
            KeyCode::Esc => {
                self.screen = Screen::Login;
            }
            _ => {}
        }
        Ok(false)
    }

    async fn handle_info_key(&mut self, key: KeyEvent) -> Result<bool> {
        match self.screen {
            Screen::SettingsInfo => match key.code {
                KeyCode::Char('c') => {
                    self.open_token_modal();
                }
                KeyCode::Enter => {
                    self.screen = Screen::Dashboard;
                    self.state.page = Page::Settings;
                    self.refresh_all().await?;
                }
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Char('w') => {
                    self.screen = Screen::Welcome;
                }
                KeyCode::Char('m') => {
                    self.screen = Screen::Menu;
                    self.menu_index = 0;
                }
                _ => {}
            },
            Screen::Help => match key.code {
                KeyCode::Enter => {
                    self.screen = Screen::Dashboard;
                    self.refresh_all().await?;
                }
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Char('w') => {
                    self.screen = Screen::Welcome;
                }
                KeyCode::Char('m') => {
                    self.screen = Screen::Menu;
                    self.menu_index = 0;
                }
                _ => {}
            },
            Screen::Version => match key.code {
                KeyCode::Esc | KeyCode::Char('q') | KeyCode::Char('w') => {
                    self.screen = Screen::Welcome;
                }
                KeyCode::Char('m') => {
                    self.screen = Screen::Menu;
                    self.menu_index = 0;
                }
                _ => {}
            },
            _ => {}
        }
        Ok(false)
    }

    fn handle_down(&mut self) {
        match self.state.page {
            Page::Dashboard | Page::Projects => self.state.select_project(1),
            Page::Protocols => self.state.select_protocol(1),
            Page::Steps => self.state.select_step(1),
            Page::Events => self.state.select_event(1),
            Page::Queues => {
                if let Some(idx) = self.state.branch_index {
                    self.state.branch_index =
                        Some((idx + 1).min(self.state.branches.len().saturating_sub(1)));
                }
            }
            _ => {}
        }
    }

    fn handle_up(&mut self) {
        match self.state.page {
            Page::Dashboard | Page::Projects => self.state.select_project(-1),
            Page::Protocols => self.state.select_protocol(-1),
            Page::Steps => self.state.select_step(-1),
            Page::Events => self.state.select_event(-1),
            Page::Queues => {
                if let Some(idx) = self.state.branch_index {
                    self.state.branch_index = Some(idx.saturating_sub(1));
                }
            }
            _ => {}
        }
    }

    async fn refresh_selection(&mut self) -> Result<()> {
        match self.state.page {
            Page::Dashboard | Page::Projects => {
                self.load_protocols().await?;
                self.load_steps().await?;
                self.load_events().await?;
                self.load_branches().await?;
            }
            Page::Protocols => {
                self.load_steps().await?;
                self.load_events().await?;
            }
            Page::Steps => {
                self.load_events().await?;
            }
            _ => {}
        }
        Ok(())
    }

    pub async fn refresh_all(&mut self) -> Result<()> {
        if self.screen != Screen::Dashboard {
            return Ok(());
        }
        self.state.refreshing = true;
        self.state.last_error = None;
        self.state.status = "Refreshing...".to_string();
        let start = Instant::now();
        self.load_projects().await?;
        self.load_protocols().await?;
        self.load_steps().await?;
        self.load_events().await?;
        self.load_recent_events().await?;
        self.load_queue().await?;
        self.load_branches().await?;
        self.state.refreshing = false;
        self.state.status = format!("Refreshed in {}ms", start.elapsed().as_millis());
        Ok(())
    }

    pub async fn refresh_scoped(&mut self) -> Result<()> {
        self.refresh_all().await
    }

    async fn load_projects(&mut self) -> Result<()> {
        match self.client.projects().await {
            Ok(data) => {
                self.state.projects = data;
                if self.state.projects.is_empty() {
                    self.state.project_index = None;
                } else if self
                    .state
                    .project_index
                    .map(|idx| idx >= self.state.projects.len())
                    .unwrap_or(true)
                {
                    self.state.project_index = Some(0);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_protocols(&mut self) -> Result<()> {
        let Some(project_id) = self.state.selected_project_id() else {
            self.state.protocols.clear();
            self.state.protocol_index = None;
            return Ok(());
        };
        match self.client.protocols(project_id).await {
            Ok(data) => {
                self.state.protocols = data;
                if self.state.protocols.is_empty() {
                    self.state.protocol_index = None;
                } else if self
                    .state
                    .protocol_index
                    .map(|idx| idx >= self.state.protocols.len())
                    .unwrap_or(true)
                {
                    self.state.protocol_index = Some(0);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_steps(&mut self) -> Result<()> {
        let Some(protocol_id) = self.state.selected_protocol_id() else {
            self.state.steps.clear();
            self.state.step_index = None;
            return Ok(());
        };
        match self.client.steps(protocol_id).await {
            Ok(data) => {
                self.state.steps = data
                    .into_iter()
                    .filter(|s| {
                        if let Some(filter) = &self.state.step_filter {
                            &s.status == filter
                        } else {
                            true
                        }
                    })
                    .collect();
                if self.state.steps.is_empty() {
                    self.state.step_index = None;
                } else if self
                    .state
                    .step_index
                    .map(|idx| idx >= self.state.steps.len())
                    .unwrap_or(true)
                {
                    self.state.step_index = Some(self.state.steps.len() - 1);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_events(&mut self) -> Result<()> {
        let Some(protocol_id) = self.state.selected_protocol_id() else {
            self.state.events.clear();
            self.state.event_index = None;
            return Ok(());
        };
        match self.client.events(protocol_id).await {
            Ok(data) => {
                self.state.events = data;
                if self.state.events.is_empty() {
                    self.state.event_index = None;
                } else if self
                    .state
                    .event_index
                    .map(|idx| idx >= self.state.events.len())
                    .unwrap_or(true)
                {
                    self.state.event_index = Some(self.state.events.len() - 1);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_recent_events(&mut self) -> Result<()> {
        match self.client.recent_events(50).await {
            Ok(data) => {
                self.state.recent_events = data;
                if self.state.recent_events.is_empty() {
                    self.state.recent_event_index = None;
                } else if self
                    .state
                    .recent_event_index
                    .map(|idx| idx >= self.state.recent_events.len())
                    .unwrap_or(true)
                {
                    self.state.recent_event_index = Some(0);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_queue(&mut self) -> Result<()> {
        match self.client.queue_stats().await {
            Ok(data) => self.state.queue_stats = data,
            Err(err) => self.set_error(err),
        }
        match self
            .client
            .queue_jobs(self.state.job_status_filter.as_deref())
            .await
        {
            Ok(data) => self.state.queue_jobs = data,
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    async fn load_branches(&mut self) -> Result<()> {
        let Some(project_id) = self.state.selected_project_id() else {
            self.state.branches.clear();
            self.state.branch_index = None;
            return Ok(());
        };
        match self.client.branches(project_id).await {
            Ok(list) => {
                self.state.branches = list.branches;
                if self.state.branches.is_empty() {
                    self.state.branch_index = None;
                } else if self
                    .state
                    .branch_index
                    .map(|idx| idx >= self.state.branches.len())
                    .unwrap_or(true)
                {
                    self.state.branch_index = Some(0);
                }
            }
            Err(err) => self.set_error(err),
        }
        Ok(())
    }

    fn set_error(&mut self, err: ApiError) {
        self.state.last_error = Some(err.to_string());
    }

    fn open_project_modal(&mut self) {
        self.modal = Some(Modal::Form {
            title: "Create project".into(),
            fields: vec![
                InputField {
                    label: "Name".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Git URL".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Base branch".into(),
                    value: "main".into(),
                    is_secret: false,
                },
            ],
            focus: 0,
            action: ModalAction::CreateProject,
        });
    }

    fn open_protocol_modal(&mut self) {
        self.modal = Some(Modal::Form {
            title: "Create protocol".into(),
            fields: vec![
                InputField {
                    label: "Protocol name".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Base branch".into(),
                    value: "main".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Description (optional)".into(),
                    value: "".into(),
                    is_secret: false,
                },
            ],
            focus: 0,
            action: ModalAction::CreateProtocol,
        });
    }

    fn open_token_modal(&mut self) {
        self.modal = Some(Modal::Form {
            title: "Configure API/token".into(),
            fields: vec![
                InputField {
                    label: "API base".into(),
                    value: self.client.base_url().to_string(),
                    is_secret: false,
                },
                InputField {
                    label: "API token (optional)".into(),
                    value: "".into(),
                    is_secret: true,
                },
                InputField {
                    label: "Project token (optional)".into(),
                    value: "".into(),
                    is_secret: true,
                },
            ],
            focus: 0,
            action: ModalAction::TokenConfig,
        });
    }

    fn open_spec_audit_modal(&mut self) {
        let project_default = self
            .state
            .selected_project_id()
            .map(|p| p.to_string())
            .unwrap_or_default();
        let protocol_default = self
            .state
            .selected_protocol_id()
            .map(|p| p.to_string())
            .unwrap_or_default();
        self.modal = Some(Modal::Form {
            title: "Spec audit".into(),
            fields: vec![
                InputField {
                    label: "Project ID (optional)".into(),
                    value: project_default,
                    is_secret: false,
                },
                InputField {
                    label: "Protocol ID (optional)".into(),
                    value: protocol_default,
                    is_secret: false,
                },
                InputField {
                    label: "Backfill? (y/N)".into(),
                    value: "y".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Interval seconds (optional)".into(),
                    value: "".into(),
                    is_secret: false,
                },
            ],
            focus: 0,
            action: ModalAction::SpecAudit,
        });
    }

    fn open_cm_modal(&mut self) {
        self.modal = Some(Modal::Form {
            title: "Import CodeMachine".into(),
            fields: vec![
                InputField {
                    label: "Protocol name".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Workspace path".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Base branch".into(),
                    value: "main".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Description (optional)".into(),
                    value: "".into(),
                    is_secret: false,
                },
                InputField {
                    label: "Enqueue? (y/N)".into(),
                    value: "y".into(),
                    is_secret: false,
                },
            ],
            focus: 0,
            action: ModalAction::ImportCodeMachine,
        });
    }

    fn open_action_palette(&mut self) {
        let items = vec![
            QuickAction::RunNext,
            QuickAction::RetryLatest,
            QuickAction::RunQa,
            QuickAction::Approve,
            QuickAction::OpenPr,
            QuickAction::StartProtocol,
            QuickAction::PauseProtocol,
            QuickAction::ResumeProtocol,
            QuickAction::CancelProtocol,
            QuickAction::ImportCodeMachine,
            QuickAction::SpecAudit,
            QuickAction::Configure,
            QuickAction::Menu,
        ];
        self.modal = Some(Modal::Palette { items, index: 0 });
    }

    fn open_delete_branch_modal(&mut self) {
        if let Some(idx) = self.state.branch_index {
            if let Some(branch) = self.state.branches.get(idx) {
                self.modal = Some(Modal::Confirm {
                    title: "Delete branch".into(),
                    message: format!("Delete remote branch '{branch}'?"),
                    action: ModalAction::DeleteBranch,
                });
            }
        }
    }

    async fn handle_modal_key(&mut self, key: &KeyEvent) -> Result<bool> {
        if self.modal.is_none() {
            return Ok(false);
        }
        match self.modal.as_mut().unwrap() {
            Modal::Message(_) => {
                if matches!(key.code, KeyCode::Enter | KeyCode::Esc) {
                    self.modal = None;
                }
                return Ok(true);
            }
            Modal::Confirm { action, .. } => {
                if key.code == KeyCode::Enter {
                    let action = *action;
                    self.modal = None;
                    self.handle_modal_submit(action).await?;
                } else if key.code == KeyCode::Esc {
                    self.modal = None;
                }
                return Ok(true);
            }
            Modal::Palette { items, index } => {
                match key.code {
                    KeyCode::Up | KeyCode::Char('k') => {
                        if *index == 0 {
                            *index = items.len().saturating_sub(1);
                        } else {
                            *index -= 1;
                        }
                    }
                    KeyCode::Down | KeyCode::Char('j') => {
                        *index = (*index + 1) % items.len();
                    }
                    KeyCode::Enter => {
                        let action = items.get(*index).copied();
                        self.modal = None;
                        if let Some(act) = action {
                            self.run_quick_action(act).await?;
                        }
                    }
                    KeyCode::Esc => {
                        self.modal = None;
                    }
                    _ => {}
                }
                return Ok(true);
            }
            Modal::Form {
                fields,
                focus,
                action,
                ..
            } => {
                match key.code {
                    KeyCode::Tab => {
                        *focus = (*focus + 1) % fields.len();
                    }
                    KeyCode::BackTab => {
                        if *focus == 0 {
                            *focus = fields.len() - 1;
                        } else {
                            *focus -= 1;
                        }
                    }
                    KeyCode::Enter => {
                        let action = *action;
                        let data = fields.clone();
                        self.modal = None;
                        self.handle_form_submit(action, data).await?;
                    }
                    KeyCode::Esc => {
                        self.modal = None;
                    }
                    KeyCode::Backspace => {
                        if let Some(field) = fields.get_mut(*focus) {
                            field.value.pop();
                        }
                    }
                    KeyCode::Char(c) => {
                        if let Some(field) = fields.get_mut(*focus) {
                            field.value.push(c);
                        }
                    }
                    _ => {}
                }
                return Ok(true);
            }
        }
    }

    async fn handle_form_submit(
        &mut self,
        action: ModalAction,
        fields: Vec<InputField>,
    ) -> Result<()> {
        match action {
            ModalAction::CreateProject => {
                if fields.len() >= 3 {
                    let name = fields[0].value.trim();
                    let git = fields[1].value.trim();
                    let branch = fields[2].value.trim();
                    if name.is_empty() || git.is_empty() {
                        self.state.last_error = Some("Name and Git URL required".into());
                        return Ok(());
                    }
                    match self
                        .client
                        .create_project(name, git, if branch.is_empty() { "main" } else { branch })
                        .await
                    {
                        Ok(proj) => {
                            self.state.status = format!("Created project {}", proj.id);
                            self.refresh_all().await?;
                        }
                        Err(err) => self.set_error(err),
                    }
                }
            }
            ModalAction::CreateProtocol => {
                if let Some(project_id) = self.state.selected_project_id() {
                    if fields.len() >= 3 {
                        let name = fields[0].value.trim();
                        let branch = fields[1].value.trim();
                        let desc = fields[2].value.trim();
                        if name.is_empty() {
                            self.state.last_error = Some("Protocol name required".into());
                            return Ok(());
                        }
                        match self
                            .client
                            .create_protocol(
                                project_id,
                                name,
                                if branch.is_empty() { "main" } else { branch },
                                if desc.is_empty() {
                                    None
                                } else {
                                    Some(desc.to_string())
                                },
                            )
                            .await
                        {
                            Ok(run) => {
                                self.state.protocol_index = None;
                                self.state.status = format!("Created protocol {}", run.id);
                                self.refresh_all().await?;
                            }
                            Err(err) => self.set_error(err),
                        }
                    }
                } else {
                    self.state.last_error = Some("Select a project first".into());
                }
            }
            ModalAction::SpecAudit => {
                let project_id = fields
                    .get(0)
                    .and_then(|f| f.value.trim().parse::<i64>().ok());
                let protocol_id = fields
                    .get(1)
                    .and_then(|f| f.value.trim().parse::<i64>().ok());
                let backfill = fields
                    .get(2)
                    .map(|f| f.value.trim().to_lowercase().starts_with('y'))
                    .unwrap_or(false);
                let interval_seconds = fields
                    .get(3)
                    .and_then(|f| f.value.trim().parse::<i64>().ok());
                match self
                    .client
                    .spec_audit(project_id, protocol_id, backfill, interval_seconds)
                    .await
                {
                    Ok(_) => self.state.status = "Spec audit enqueued".into(),
                    Err(err) => self.set_error(err),
                }
            }
            ModalAction::ImportCodeMachine => {
                if let Some(project_id) = self.state.selected_project_id() {
                    if fields.len() >= 5 {
                        let name = fields[0].value.trim();
                        let path = fields[1].value.trim();
                        let branch = fields[2].value.trim();
                        let desc = fields[3].value.trim();
                        let enqueue = fields[4].value.trim().to_lowercase().starts_with('y');
                        if name.is_empty() || path.is_empty() {
                            self.state.last_error =
                                Some("Protocol name and workspace path required".into());
                            return Ok(());
                        }
                        match self
                            .client
                            .import_codemachine(
                                project_id,
                                name,
                                path,
                                if branch.is_empty() { "main" } else { branch },
                                if desc.is_empty() {
                                    None
                                } else {
                                    Some(desc.to_string())
                                },
                                enqueue,
                            )
                            .await
                        {
                            Ok(_) => {
                                self.state.status = "Import enqueued".into();
                                self.refresh_all().await?;
                            }
                            Err(err) => self.set_error(err),
                        }
                    }
                } else {
                    self.state.last_error = Some("Select a project first".into());
                }
            }
            ModalAction::TokenConfig => {
                if fields.len() >= 3 {
                    let api_base = fields[0].value.trim();
                    let token = fields[1].value.trim();
                    let project_token = fields[2].value.trim();
                    if !api_base.is_empty() {
                        self.client = ApiClient::new(
                            api_base.to_string(),
                            if token.is_empty() {
                                None
                            } else {
                                Some(token.to_string())
                            },
                            if project_token.is_empty() {
                                None
                            } else {
                                Some(project_token.to_string())
                            },
                        )?;
                        self.state.status = format!("API base set to {api_base}");
                    }
                }
            }
            ModalAction::DeleteBranch => {
                if let Some(idx) = self.state.branch_index {
                    if let (Some(branch), Some(project_id)) = (
                        self.state.branches.get(idx),
                        self.state.selected_project_id(),
                    ) {
                        match self.client.delete_branch(project_id, branch).await {
                            Ok(_) => {
                                self.state.status = format!("Deleted branch {branch}");
                                self.load_branches().await?;
                            }
                            Err(err) => self.set_error(err),
                        }
                    }
                }
            }
        }
        Ok(())
    }

    async fn handle_modal_submit(&mut self, action: ModalAction) -> Result<()> {
        match action {
            ModalAction::DeleteBranch => self.handle_form_submit(action, vec![]).await?,
            _ => {}
        }
        Ok(())
    }

    async fn run_quick_action(&mut self, action: QuickAction) -> Result<()> {
        match action {
            QuickAction::RunNext => self.run_next().await?,
            QuickAction::RetryLatest => self.retry_latest().await?,
            QuickAction::RunQa => self.run_qa_latest().await?,
            QuickAction::Approve => self.approve_latest().await?,
            QuickAction::OpenPr => self.open_pr().await?,
            QuickAction::StartProtocol => {
                self.protocol_action("start", "Planning enqueued.").await?
            }
            QuickAction::PauseProtocol => self.protocol_action("pause", "Protocol paused.").await?,
            QuickAction::ResumeProtocol => {
                self.protocol_action("resume", "Protocol resumed.").await?
            }
            QuickAction::CancelProtocol => {
                self.protocol_action("cancel", "Protocol cancelled.")
                    .await?
            }
            QuickAction::ImportCodeMachine => self.open_cm_modal(),
            QuickAction::SpecAudit => self.open_spec_audit_modal(),
            QuickAction::Configure => self.open_token_modal(),
            QuickAction::Menu => {
                self.screen = Screen::Menu;
                self.menu_index = 0;
            }
        }
        Ok(())
    }

    async fn run_next(&mut self) -> Result<()> {
        if let Some(protocol_id) = self.state.selected_protocol_id() {
            match self.client.step_run_next(protocol_id).await {
                Ok(_) => {
                    self.state.status = "Run next enqueued".into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn retry_latest(&mut self) -> Result<()> {
        if let Some(protocol_id) = self.state.selected_protocol_id() {
            match self.client.step_retry_latest(protocol_id).await {
                Ok(_) => {
                    self.state.status = "Retry enqueued".into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn run_qa_latest(&mut self) -> Result<()> {
        if let Some(step) = self.state.steps.last() {
            match self.client.step_run_qa(step.id).await {
                Ok(_) => {
                    self.state.status = "QA enqueued".into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn approve_latest(&mut self) -> Result<()> {
        if let Some(step) = self.state.steps.last() {
            match self.client.step_approve(step.id).await {
                Ok(_) => {
                    self.state.status = "Approved".into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn open_pr(&mut self) -> Result<()> {
        if let Some(protocol_id) = self.state.selected_protocol_id() {
            match self.client.protocol_open_pr(protocol_id).await {
                Ok(_) => {
                    self.state.status = "Open PR enqueued".into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn protocol_action(&mut self, action: &str, success: &str) -> Result<()> {
        if let Some(protocol_id) = self.state.selected_protocol_id() {
            match self.client.protocol_action(protocol_id, action).await {
                Ok(_) => {
                    self.state.status = success.into();
                    self.refresh_all().await?;
                }
                Err(err) => self.set_error(err),
            }
        }
        Ok(())
    }

    async fn cycle_job_filter(&mut self) -> Result<()> {
        let order = [
            None,
            Some("queued"),
            Some("started"),
            Some("failed"),
            Some("finished"),
        ];
        let idx = order
            .iter()
            .position(|v| v.as_deref() == self.state.job_status_filter.as_deref())
            .unwrap_or(0);
        let next = order[(idx + 1) % order.len()];
        self.state.job_status_filter = next.map(|s| s.to_string());
        self.state.status = format!(
            "Job filter: {}",
            self.state
                .job_status_filter
                .clone()
                .unwrap_or_else(|| "all".into())
        );
        self.load_queue().await?;
        Ok(())
    }

    async fn cycle_step_filter(&mut self) -> Result<()> {
        let order = [
            None,
            Some("pending"),
            Some("running"),
            Some("needs_qa"),
            Some("failed"),
        ];
        let idx = order
            .iter()
            .position(|v| v.as_deref() == self.state.step_filter.as_deref())
            .unwrap_or(0);
        let next = order[(idx + 1) % order.len()];
        self.state.step_filter = next.map(|s| s.to_string());
        self.state.status = format!(
            "Step filter: {}",
            self.state
                .step_filter
                .clone()
                .unwrap_or_else(|| "all".into())
        );
        self.load_steps().await?;
        Ok(())
    }
}
