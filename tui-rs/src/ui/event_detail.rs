use ratatui::{
    style::Style,
    widgets::{Block, Borders, Paragraph, Wrap},
    Frame,
};

use crate::app::App;

pub fn draw_event_detail(f: &mut Frame<'_>, area: ratatui::layout::Rect, app: &App) {
    let selected = app
        .state
        .event_index
        .and_then(|idx| app.state.events.get(idx))
        .or_else(|| app.state.events.last());
    let content = if let Some(ev) = selected {
        let mut text = format!("{} • {}\n{}", ev.event_type, ev.created_at, ev.message);
        if let Some(meta) = &ev.metadata {
            if let Ok(body) = serde_json::to_string_pretty(meta) {
                text.push_str("\n");
                text.push_str(&body);
            }
        }
        text
    } else {
        "No events yet.".into()
    };
    let para = Paragraph::new(content)
        .style(Style::default())
        .block(Block::default().borders(Borders::ALL).title("Event detail"))
        .wrap(Wrap { trim: true });
    f.render_widget(para, area);
}
