//! MiniMax Scraper — OS-like browser UI for documentation scraping.

mod api;
mod app;
mod components;
mod state;

fn main() {
    dioxus_logger::init(tracing::Level::INFO).expect("failed to init logger");
    dioxus::launch(app::App);
}
