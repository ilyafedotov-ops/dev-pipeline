use crate::app::{App, LoginForm, Modal, QuickAction, Screen};
mod event_detail;
use crate::state::Page;
use event_detail::draw_event_detail;
use ratatui::{
    layout::{Constraint, Direction, Layout, Rect},
    style::{Color, Modifier, Style},
    text::{Line, Span},
    widgets::{Block, Borders, Clear, List, ListItem, ListState, Paragraph, Tabs, Wrap},
    Frame,
};
use serde_json::Value;
use std::fmt::Write as _;

pub fn draw(
    f: &mut Frame<'_>,
    app: &App,
    modal: Option<&Modal>,
    screen: Screen,
    login_form: &LoginForm,
    menu_index: usize,
    welcome_index: usize,
) {
    let size = f.size();
    match screen {
        Screen::Welcome => draw_welcome(f, size, welcome_index, app),
        Screen::Login => draw_login(f, size, login_form, app),
        Screen::Menu => draw_menu(f, size, menu_index, app),
        Screen::SettingsInfo => draw_settings_info(f, size, app),
        Screen::Help => draw_help(f, size, app),
        Screen::Version => draw_version(f, size, app),
        Screen::Dashboard => {
            let chunks = Layout::default()
                .direction(Direction::Vertical)
                .constraints(
                    [
                        Constraint::Length(3),
                        Constraint::Length(3),
                        Constraint::Min(0),
                        Constraint::Length(2),
                    ]
                    .as_ref(),
                )
                .split(size);

            draw_tabs(f, chunks[0], app);
            draw_action_bar(f, chunks[1], app.state.page);
            draw_body(f, chunks[2], app);
            draw_status(f, chunks[3], app);
            if let Some(modal) = modal {
                draw_modal(f, size, modal);
            }
        }
    }
}

fn draw_tabs(f: &mut Frame<'_>, area: Rect, app: &App) {
    let titles = [
        "Dashboard",
        "Projects",
        "Protocols",
        "Steps",
        "Events",
        "Queues",
        "Settings",
    ]
    .into_iter()
    .map(|t| Line::from(Span::styled(t, Style::default().fg(Color::Cyan))))
    .collect::<Vec<_>>();
    let idx = match app.state.page {
        Page::Dashboard => 0,
        Page::Projects => 1,
        Page::Protocols => 2,
        Page::Steps => 3,
        Page::Events => 4,
        Page::Queues => 5,
        Page::Settings => 6,
    };
    let tabs = Tabs::new(titles)
        .block(Block::default().borders(Borders::ALL).title("Pages"))
        .select(idx)
        .highlight_style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        );
    f.render_widget(tabs, area);
}

fn draw_body(f: &mut Frame<'_>, area: Rect, app: &App) {
    match app.state.page {
        Page::Dashboard => draw_dashboard(f, area, app),
        Page::Projects => draw_projects(f, area, app),
        Page::Protocols => draw_protocols(f, area, app),
        Page::Steps => draw_steps(f, area, app),
        Page::Events => draw_events(f, area, app),
        Page::Queues => draw_queues(f, area, app),
        Page::Settings => draw_settings(f, area, app),
    }
}

fn draw_action_bar(f: &mut Frame<'_>, area: Rect, page: Page) {
    let (primary, secondary) = match page {
        Page::Dashboard | Page::Protocols | Page::Steps => (
            vec![
                ("Enter", "Action palette"),
                ("n", "Run next"),
                ("t", "Retry"),
                ("y", "QA"),
                ("a", "Approve"),
                ("o", "Open PR"),
                ("s", "Start"),
                ("p", "Pause"),
                ("e", "Resume"),
                ("x", "Cancel"),
            ],
            vec![
                ("f", "Step filter"),
                ("J", "Job filter"),
                ("[ / ]", "Branch"),
                ("r", "Refresh"),
                ("m", "Menu"),
                ("q", "Quit"),
            ],
        ),
        Page::Projects => (
            vec![
                ("g", "New project"),
                ("R", "New protocol"),
                ("i", "Import CM"),
                ("A", "Spec audit"),
            ],
            vec![
                ("b", "Reload branches"),
                ("d", "Delete branch"),
                ("c", "Configure"),
                ("m", "Menu"),
                ("q", "Quit"),
            ],
        ),
        Page::Events => (
            vec![("Enter", "Action palette"), ("j/k", "Select event")],
            vec![("r", "Refresh"), ("m", "Menu"), ("q", "Quit")],
        ),
        Page::Queues => (
            vec![("J", "Cycle job filter")],
            vec![("r", "Refresh"), ("m", "Menu"), ("q", "Quit")],
        ),
        Page::Settings => (
            vec![("c", "Configure API/token")],
            vec![("m", "Menu"), ("q", "Quit")],
        ),
    };

    let primary_line = action_line(primary, true);
    let secondary_line = action_line(secondary, false);
    let para = Paragraph::new(vec![primary_line, secondary_line])
        .alignment(ratatui::layout::Alignment::Center)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(format!("Actions — {}", page_label(page))),
        )
        .wrap(Wrap { trim: true });
    f.render_widget(para, area);
}

fn draw_dashboard(f: &mut Frame<'_>, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints(
            [
                Constraint::Percentage(30),
                Constraint::Percentage(30),
                Constraint::Percentage(40),
            ]
            .as_ref(),
        )
        .split(area);

    draw_project_list(f, cols[0], app);
    draw_protocol_list(f, cols[1], app);

    let right = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(60), Constraint::Percentage(40)].as_ref())
        .split(cols[2]);

    draw_step_list(f, right[0], app);
    draw_event_list(f, right[1], app, false);
}

fn draw_projects(f: &mut Frame<'_>, area: Rect, app: &App) {
    let cols = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)].as_ref())
        .split(area);
    draw_project_list(f, cols[0], app);
    draw_branch_list(f, cols[1], app);
}

fn draw_protocols(f: &mut Frame<'_>, area: Rect, app: &App) {
    draw_protocol_list(f, area, app);
}

fn draw_steps(f: &mut Frame<'_>, area: Rect, app: &App) {
    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)].as_ref())
        .split(area);
    draw_step_list(f, layout[0], app);
    draw_event_list(f, layout[1], app, true);
}

fn draw_events(f: &mut Frame<'_>, area: Rect, app: &App) {
    let rows = Layout::default()
        .direction(Direction::Vertical)
        .constraints([Constraint::Percentage(70), Constraint::Percentage(30)].as_ref())
        .split(area);
    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)].as_ref())
        .split(rows[0]);
    draw_event_list(f, layout[0], app, true);
    draw_recent_events(f, layout[1], app);
    draw_event_detail(f, rows[1], app);
}

fn draw_queues(f: &mut Frame<'_>, area: Rect, app: &App) {
    let layout = Layout::default()
        .direction(Direction::Horizontal)
        .constraints([Constraint::Percentage(50), Constraint::Percentage(50)].as_ref())
        .split(area);
    let stats_text = format_value(&app.state.queue_stats);
    let stats = Paragraph::new(stats_text)
        .block(Block::default().borders(Borders::ALL).title("Queue stats"))
        .wrap(Wrap { trim: true });
    f.render_widget(stats, layout[0]);

    let items: Vec<ListItem> = app
        .state
        .queue_jobs
        .iter()
        .map(|job| {
            let label = format!(
                "{} [{}]",
                job.job_id.clone().unwrap_or_else(|| "-".to_string()),
                job.status.clone().unwrap_or_else(|| "-".to_string())
            );
            ListItem::new(label)
        })
        .collect();
    let list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Queue jobs"))
        .highlight_style(Style::default().bg(Color::Blue));
    f.render_widget(list, layout[1]);
}

fn draw_settings(f: &mut Frame<'_>, area: Rect, app: &App) {
    let text: Vec<Line> = vec![
        Line::from(format!("API base: {}", app.client.base_url())),
        Line::from(format!(
            "Token: {} | Project token: {}",
            if app.client.has_token() { "set" } else { "-" },
            if app.client.has_project_token() {
                "set"
            } else {
                "-"
            }
        )),
        Line::from(format!(
            "Auto-refresh: every {}s",
            app.refresh_interval.as_secs()
        )),
        Line::from("Read-only mode (Phase 1)"),
    ];
    let para = Paragraph::new(text)
        .block(Block::default().borders(Borders::ALL).title("Settings"))
        .wrap(Wrap { trim: true });
    f.render_widget(para, area);
}

fn draw_project_list(f: &mut Frame<'_>, area: Rect, app: &App) {
    let items: Vec<ListItem> = app
        .state
        .projects
        .iter()
        .map(|p| {
            let branch = p.base_branch.clone().unwrap_or_else(|| "-".into());
            ListItem::new(format!("{} • {} ({branch})", p.id, p.name))
        })
        .collect();
    let mut list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Projects"))
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    if let Some(idx) = app.state.project_index {
        list = list.highlight_symbol("➤ ");
        f.render_stateful_widget(list, area, &mut make_state(idx));
    } else {
        f.render_widget(list, area);
    }
}

fn draw_branch_list(f: &mut Frame<'_>, area: Rect, app: &App) {
    let items: Vec<ListItem> = app
        .state
        .branches
        .iter()
        .map(|b| ListItem::new(b.clone()))
        .collect();
    let mut list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Branches"))
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    if let Some(idx) = app.state.branch_index {
        list = list.highlight_symbol("➤ ");
        f.render_stateful_widget(list, area, &mut make_state(idx));
    } else {
        f.render_widget(list, area);
    }
}

fn draw_protocol_list(f: &mut Frame<'_>, area: Rect, app: &App) {
    let items: Vec<ListItem> = app
        .state
        .protocols
        .iter()
        .map(|r| {
            let status = r.status.clone().unwrap_or_else(|| "-".into());
            let branch = r.base_branch.clone().unwrap_or_else(|| "-".into());
            ListItem::new(format!(
                "{} • {} [{status}] ({branch})",
                r.id, r.protocol_name
            ))
        })
        .collect();
    let mut list = List::new(items)
        .block(Block::default().borders(Borders::ALL).title("Protocols"))
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    if let Some(idx) = app.state.protocol_index {
        list = list.highlight_symbol("➤ ");
        f.render_stateful_widget(list, area, &mut make_state(idx));
    } else {
        f.render_widget(list, area);
    }
}

fn draw_step_list(f: &mut Frame<'_>, area: Rect, app: &App) {
    let filter_label = app
        .state
        .step_filter
        .clone()
        .unwrap_or_else(|| "all".into());
    let items: Vec<ListItem> = app
        .state
        .steps
        .iter()
        .map(|s| {
            let status = s.status.clone();
            ListItem::new(format!(
                "{}: {} [{status}] (r={})",
                s.step_index, s.step_name, s.retries
            ))
        })
        .collect();
    let mut list = List::new(items)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title(format!("Steps (filter: {filter_label})")),
        )
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    if let Some(idx) = app.state.step_index {
        list = list.highlight_symbol("➤ ");
        f.render_stateful_widget(list, area, &mut make_state(idx));
    } else {
        f.render_widget(list, area);
    }
}

fn draw_event_list(f: &mut Frame<'_>, area: Rect, app: &App, scoped: bool) {
    let events = if scoped {
        &app.state.events
    } else {
        &app.state.recent_events
    };
    let items: Vec<ListItem> = events
        .iter()
        .rev()
        .take(30)
        .map(|e| ListItem::new(format!("{}: {}", e.event_type, e.message)))
        .collect();
    let block =
        Block::default()
            .borders(Borders::ALL)
            .title(if scoped { "Events" } else { "Events" });
    if scoped {
        let mut list = List::new(items)
            .block(block)
            .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
        if let Some(idx) = app.state.event_index {
            let mut state = ListState::default();
            state.select(Some((events.len().saturating_sub(1)).saturating_sub(idx)));
            list = list.highlight_symbol("➤ ");
            f.render_stateful_widget(list, area, &mut state);
            return;
        }
        f.render_widget(list, area);
    } else {
        let list = List::new(items).block(block);
        f.render_widget(list, area);
    }
}

fn draw_recent_events(f: &mut Frame<'_>, area: Rect, app: &App) {
    let items: Vec<ListItem> = app
        .state
        .recent_events
        .iter()
        .take(30)
        .map(|e| ListItem::new(format!("{}: {}", e.event_type, e.message)))
        .collect();
    let block = Block::default()
        .borders(Borders::ALL)
        .title("Recent events");
    let mut list = List::new(items).block(block);
    if let Some(idx) = app.state.recent_event_index {
        let mut state = ListState::default();
        state.select(Some(idx));
        list = list.highlight_symbol("➤ ");
        f.render_stateful_widget(list, area, &mut state);
    } else {
        f.render_widget(list, area);
    }
}

fn draw_status(f: &mut Frame<'_>, area: Rect, app: &App) {
    let mut line = format!("Status: {}", app.state.status);
    if let Some(err) = &app.state.last_error {
        let _ = write!(line, " • Error: {}", err);
    }
    let para = Paragraph::new(line)
        .style(Style::default().fg(Color::White))
        .block(Block::default().borders(Borders::ALL).title("Status"))
        .wrap(Wrap { trim: true });
    f.render_widget(para, area);
}

fn draw_login(f: &mut Frame<'_>, area: Rect, login: &LoginForm, app: &App) {
    let panel = centered_rect(70, 70, area);
    let block = Block::default()
        .borders(Borders::ALL)
        .title("Connect to TasksGodzilla");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints(
            [
                Constraint::Length(6),
                Constraint::Length(3),
                Constraint::Length(6),
                Constraint::Length(3),
                Constraint::Min(0),
            ]
            .as_ref(),
        )
        .split(inner);
    let banner = Paragraph::new(vec![
        Line::from("████████╗ █████╗ ███████╗██╗  ██╗███████╗ ██████╗ "),
        Line::from("╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔═══██╗"),
        Line::from("   ██║   ███████║███████╗█████╔╝ ███████╗██║   ██║"),
        Line::from("   ██║   ██╔══██║╚════██║██╔═██╗ ╚════██║██║   ██║"),
        Line::from("   ██║   ██║  ██║███████║██║  ██╗███████║╚██████╔╝"),
        Line::from("   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ "),
    ])
    .style(Style::default().fg(Color::Cyan))
    .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(banner, layout[0]);

    let title = Paragraph::new("TasksGodzilla TUI — Login")
        .style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        )
        .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(title, layout[1]);

    let mut lines: Vec<Line> = Vec::new();
    for (idx, field) in login.fields.iter().enumerate() {
        let mut label = format!("{}: ", field.label);
        if idx == login.focus {
            label.insert_str(0, "> ");
        } else {
            label.insert_str(0, "  ");
        }
        let value = if field.is_secret {
            "******".to_string()
        } else {
            field.value.clone()
        };
        lines.push(Line::from(format!("{label}{value}")));
    }
    let form = Paragraph::new(lines)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("API connection"),
        )
        .wrap(Wrap { trim: true });
    f.render_widget(form, layout[2]);

    let help = Paragraph::new("Tab/Shift-Tab move • Enter connect • Esc quit (tokens optional)")
        .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(help, layout[3]);

    let status = Paragraph::new(format!("Status: {}", app.state.status))
        .block(Block::default().borders(Borders::ALL).title("Status"));
    f.render_widget(status, layout[4]);
}

fn draw_welcome(f: &mut Frame<'_>, area: Rect, welcome_index: usize, app: &App) {
    let panel = centered_rect(80, 70, area);
    let block = Block::default()
        .borders(Borders::ALL)
        .title("Welcome to TasksGodzilla");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints(
            [
                Constraint::Length(7),
                Constraint::Length(4),
                Constraint::Length(9),
                Constraint::Length(3),
                Constraint::Length(3),
            ]
            .as_ref(),
        )
        .split(inner);

    let banner = Paragraph::new(vec![
        Line::from("████████╗ █████╗ ███████╗██╗  ██╗███████╗ ██████╗ "),
        Line::from("╚══██╔══╝██╔══██╗██╔════╝██║ ██╔╝██╔════╝██╔═══██╗"),
        Line::from("   ██║   ███████║███████╗█████╔╝ ███████╗██║   ██║"),
        Line::from("   ██║   ██╔══██║╚════██║██╔═██╗ ╚════██║██║   ██║"),
        Line::from("   ██║   ██║  ██║███████║██║  ██╗███████║╚██████╔╝"),
        Line::from("   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚══════╝ ╚═════╝ "),
    ])
    .style(Style::default().fg(Color::Cyan))
    .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(banner, layout[0]);

    let subtitle = Paragraph::new(format!(
        "Fast terminal UI for orchestrator — v{}",
        env!("CARGO_PKG_VERSION")
    ))
    .style(Style::default().fg(Color::Yellow))
    .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(subtitle, layout[1]);

    let items = ["Start TasksGodzilla", "Settings", "Help", "Version", "Quit"];
    let list_items: Vec<ListItem> = items
        .iter()
        .enumerate()
        .map(|(idx, item)| {
            let prefix = if idx == welcome_index { "➤ " } else { "  " };
            ListItem::new(format!("{prefix}{item}"))
        })
        .collect();
    let list = List::new(list_items)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Choose an option"),
        )
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    f.render_widget(list, layout[2]);

    let help = Paragraph::new("Up/Down/Tab select • Enter confirm • 1/2/3/4 shortcuts • q quit")
        .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(help, layout[3]);

    let status = Paragraph::new(format!("Status: {}", app.state.status))
        .block(Block::default().borders(Borders::ALL).title("Status"));
    f.render_widget(status, layout[4]);
}

fn draw_settings_info(f: &mut Frame<'_>, area: Rect, app: &App) {
    let panel = centered_rect(70, 70, area);
    let block = Block::default().borders(Borders::ALL).title("Settings");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let text = vec![
        Line::from(format!("API base: {}", app.client.base_url())),
        Line::from(format!(
            "API token: {}",
            if app.client.has_token() { "set" } else { "-" }
        )),
        Line::from(format!(
            "Project token: {}",
            if app.client.has_project_token() {
                "set"
            } else {
                "-"
            }
        )),
        Line::from(format!(
            "Refresh interval: {}s",
            app.refresh_interval.as_secs()
        )),
        Line::from(format!(
            "Autologin: {}",
            if app.auto_login {
                "enabled"
            } else {
                "disabled"
            }
        )),
        Line::from(""),
        Line::from("Enter → open dashboard settings tab"),
        Line::from("c → configure API/token • m → main menu • q/Esc → back"),
    ];
    let para = Paragraph::new(text)
        .alignment(ratatui::layout::Alignment::Left)
        .block(block);
    f.render_widget(para, inner);
}

fn draw_help(f: &mut Frame<'_>, area: Rect, _app: &App) {
    let panel = centered_rect(80, 75, area);
    let block = Block::default().borders(Borders::ALL).title("Help");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let text = vec![
        heading_line("Navigation"),
        Line::from(" tab/shift-tab or ←/→ cycle pages • 1-7 jump • ↑↓/j k move • m main menu • w welcome • q/Esc back"),
        Line::from(""),
        heading_line("Pages"),
        Line::from(" Dashboard, Projects, Protocols, Steps, Events, Queues, Settings"),
        Line::from(" Dashboard = projects+protocols+steps+events; Steps/Events show scoped events; Queues show stats/jobs."),
        Line::from(""),
        heading_line("Actions"),
        Line::from(" Enter quick actions • n run next • t retry • y QA • a approve • o open PR"),
        Line::from(" s start • p pause • e resume • x cancel • f step filter • J job filter • [/] branch • r refresh"),
        Line::from(""),
        heading_line("Modals & CRUD"),
        Line::from(" g new project • R new protocol • i import CodeMachine • A spec audit • c configure tokens"),
        Line::from(" b reload branches • d delete branch (selected)"),
        Line::from(""),
        heading_line("Welcome / Menu"),
        Line::from(" Welcome: Start TasksGodzilla, Settings, Help, Version, Quit"),
        Line::from(" Main menu: Dashboard, Configure API/token, Quit"),
        Line::from(""),
        heading_line("Environment"),
        Line::from(" TASKSGODZILLA_API_BASE | TASKSGODZILLA_API_TOKEN | TASKSGODZILLA_PROJECT_TOKEN"),
        Line::from(" TASKSGODZILLA_TUI_AUTOLOGIN (default 1) | TASKSGODZILLA_TUI_REFRESH_SECS (default 4)"),
        Line::from(""),
        Line::from("Enter → dashboard • m → main menu • w → welcome • q/Esc → back"),
    ];
    let para = Paragraph::new(text)
        .alignment(ratatui::layout::Alignment::Left)
        .block(block);
    f.render_widget(para, inner);
}

fn draw_version(f: &mut Frame<'_>, area: Rect, _app: &App) {
    let panel = centered_rect(60, 50, area);
    let block = Block::default().borders(Borders::ALL).title("Version");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let text = vec![
        Line::from(format!("TasksGodzilla TUI v{}", env!("CARGO_PKG_VERSION"))),
        Line::from("Rust ratatui client for the orchestrator."),
        Line::from(""),
        Line::from("m → main menu • q/Esc → back"),
    ];
    let para = Paragraph::new(text)
        .alignment(ratatui::layout::Alignment::Center)
        .block(block);
    f.render_widget(para, inner);
}

fn draw_menu(f: &mut Frame<'_>, area: Rect, menu_index: usize, app: &App) {
    let panel = centered_rect(60, 50, area);
    let block = Block::default()
        .borders(Borders::ALL)
        .title("TasksGodzilla");
    f.render_widget(Clear, panel);
    f.render_widget(block.clone(), panel);
    let inner = shrink(panel, 1);
    let layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints(
            [
                Constraint::Length(3),
                Constraint::Length(9),
                Constraint::Length(3),
                Constraint::Length(3),
            ]
            .as_ref(),
        )
        .split(inner);

    let title = Paragraph::new("Main menu")
        .style(
            Style::default()
                .fg(Color::Yellow)
                .add_modifier(Modifier::BOLD),
        )
        .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(title, layout[0]);

    let items = ["Dashboard", "Configure API/token", "Quit"];
    let list_items: Vec<ListItem> = items
        .iter()
        .enumerate()
        .map(|(idx, item)| {
            let prefix = if idx == menu_index { "➤ " } else { "  " };
            ListItem::new(format!("{prefix}{item}"))
        })
        .collect();
    let list = List::new(list_items)
        .block(
            Block::default()
                .borders(Borders::ALL)
                .title("Select an option"),
        )
        .highlight_style(Style::default().bg(Color::Blue).fg(Color::White));
    f.render_widget(list, layout[1]);

    let help =
        Paragraph::new("Up/Down/Tab select • Enter confirm • 1/2/3 shortcuts • Esc back • q quit")
            .alignment(ratatui::layout::Alignment::Center);
    f.render_widget(help, layout[2]);

    let status = Paragraph::new(format!("Status: {}", app.state.status))
        .block(Block::default().borders(Borders::ALL).title("Status"));
    f.render_widget(status, layout[3]);
}

fn draw_modal(f: &mut Frame<'_>, size: Rect, modal: &Modal) {
    let area = centered_rect(60, 60, size);
    f.render_widget(Clear, area);
    match modal {
        Modal::Message(msg) => {
            let para = Paragraph::new(msg.clone())
                .block(Block::default().borders(Borders::ALL).title("Message"))
                .wrap(Wrap { trim: true });
            f.render_widget(para, area);
        }
        Modal::Confirm { title, message, .. } => {
            let para = Paragraph::new(vec![
                Line::from(title.clone()),
                Line::from(""),
                Line::from(message.clone()),
                Line::from("Enter to confirm, Esc to cancel"),
            ])
            .block(Block::default().borders(Borders::ALL).title(title.clone()))
            .wrap(Wrap { trim: true });
            f.render_widget(para, area);
        }
        Modal::Form {
            title,
            fields,
            focus,
            ..
        } => {
            let mut lines: Vec<Line> = Vec::new();
            lines.push(Line::from(title.clone()));
            lines.push(Line::from(""));
            for (idx, field) in fields.iter().enumerate() {
                let mut label = format!("{}: ", field.label);
                if idx == *focus {
                    label.insert_str(0, "> ");
                } else {
                    label.insert_str(0, "  ");
                }
                let value = if field.is_secret {
                    "******".to_string()
                } else {
                    field.value.clone()
                };
                lines.push(Line::from(format!("{label}{value}")));
            }
            lines.push(Line::from(""));
            lines.push(Line::from("Enter submit • Tab next • Esc cancel"));
            let para = Paragraph::new(lines)
                .block(Block::default().borders(Borders::ALL).title(title.clone()))
                .wrap(Wrap { trim: true });
            f.render_widget(para, area);
        }
        Modal::Palette { items, index } => {
            let mut lines: Vec<Line> = Vec::new();
            lines.push(Line::from("Actions"));
            lines.push(Line::from(""));
            for (idx, item) in items.iter().enumerate() {
                let label = format!(
                    "{} {}",
                    if idx == *index { "➤" } else { " " },
                    format_quick_action(*item)
                );
                lines.push(Line::from(label));
            }
            lines.push(Line::from(""));
            lines.push(Line::from("Enter run • j/k move • Esc close"));
            let para = Paragraph::new(lines)
                .block(
                    Block::default()
                        .borders(Borders::ALL)
                        .title("Action palette"),
                )
                .wrap(Wrap { trim: true });
            f.render_widget(para, area);
        }
    }
}

fn page_label(page: Page) -> &'static str {
    match page {
        Page::Dashboard => "Dashboard",
        Page::Projects => "Projects",
        Page::Protocols => "Protocols",
        Page::Steps => "Steps",
        Page::Events => "Events",
        Page::Queues => "Queues",
        Page::Settings => "Settings",
    }
}

fn action_line(items: Vec<(&str, &str)>, emphasize: bool) -> Line<'static> {
    let mut spans: Vec<Span> = Vec::new();
    for (idx, (key, label)) in items.into_iter().enumerate() {
        if idx > 0 {
            spans.push(Span::raw("  "));
        }
        spans.push(Span::styled(
            format!(" {key} "),
            Style::default()
                .bg(if emphasize { Color::Green } else { Color::Blue })
                .fg(Color::Black)
                .add_modifier(Modifier::BOLD),
        ));
        spans.push(Span::styled(
            format!(" {label}"),
            Style::default().fg(Color::Gray),
        ));
    }
    Line::from(spans)
}

fn heading_line(text: &str) -> Line<'static> {
    Line::from(Span::styled(
        text.to_string(),
        Style::default()
            .fg(Color::Yellow)
            .add_modifier(Modifier::BOLD),
    ))
}

fn centered_rect(percent_x: u16, percent_y: u16, r: Rect) -> Rect {
    let popup_layout = Layout::default()
        .direction(Direction::Vertical)
        .constraints(
            [
                Constraint::Percentage((100 - percent_y) / 2),
                Constraint::Percentage(percent_y),
                Constraint::Percentage((100 - percent_y) / 2),
            ]
            .as_ref(),
        )
        .split(r);
    let vertical = popup_layout[1];
    let horizontal = Layout::default()
        .direction(Direction::Horizontal)
        .constraints(
            [
                Constraint::Percentage((100 - percent_x) / 2),
                Constraint::Percentage(percent_x),
                Constraint::Percentage((100 - percent_x) / 2),
            ]
            .as_ref(),
        )
        .split(vertical);
    horizontal[1]
}

fn shrink(area: Rect, padding: u16) -> Rect {
    Rect {
        x: area.x.saturating_add(padding),
        y: area.y.saturating_add(padding),
        width: area
            .width
            .saturating_sub(padding.saturating_mul(2).min(area.width)),
        height: area
            .height
            .saturating_sub(padding.saturating_mul(2).min(area.height)),
    }
}

fn make_state(selected: usize) -> ListState {
    let mut state = ListState::default();
    state.select(Some(selected));
    state
}

fn format_value(value: &Value) -> String {
    match value {
        Value::Null => "-".to_string(),
        _ => serde_json::to_string_pretty(value).unwrap_or_else(|_| "-".to_string()),
    }
}

fn format_quick_action(action: QuickAction) -> String {
    match action {
        QuickAction::RunNext => "Run next (n)",
        QuickAction::RetryLatest => "Retry latest (t)",
        QuickAction::RunQa => "Run QA (y)",
        QuickAction::Approve => "Approve (a)",
        QuickAction::OpenPr => "Open PR (o)",
        QuickAction::StartProtocol => "Start protocol (s)",
        QuickAction::PauseProtocol => "Pause protocol (p)",
        QuickAction::ResumeProtocol => "Resume protocol (e)",
        QuickAction::CancelProtocol => "Cancel protocol (x)",
        QuickAction::ImportCodeMachine => "Import CodeMachine (i)",
        QuickAction::SpecAudit => "Spec audit (A)",
        QuickAction::Configure => "Configure API/token (c)",
        QuickAction::Menu => "Main menu (m)",
    }
    .to_string()
}
