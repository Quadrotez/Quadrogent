# Qt's HTML engine only partially supports CSS classes in <style> blocks.
# Inline styles are the ONLY reliable way to style in QTextBrowser.
# This file keeps the Qt widget stylesheet (DARK_THEME) and the
# minimal <style> block used as a base reset (MESSAGE_CSS).

DARK_THEME = """
QMainWindow, QDialog {
    background-color: #0a0a0a;
    color: #e0e0e0;
}
QWidget {
    background-color: #0a0a0a;
    color: #e0e0e0;
    font-family: "Inter", "Segoe UI", "SF Pro Text", sans-serif;
    font-size: 13px;
}

/* ── Sidebar ─────────────────────────── */
#sidebar {
    background-color: #070707;
    border-right: 1px solid #181818;
}
#newChatBtn {
    background-color: transparent;
    color: #d8d8d8;
    border: 1px solid #252525;
    font-size: 12px;
    font-weight: 500;
    padding: 9px 12px;
    margin: 6px 10px 4px 10px;
    border-radius: 7px;
    text-align: left;
}
#newChatBtn:hover { background-color: #141414; border-color: #363636; color: #ffffff; }
#chatList { background-color: #070707; border: none; outline: none; }
#chatList::item {
    padding: 9px 12px; border-radius: 6px;
    color: #484848; margin: 1px 6px; font-size: 12px;
    border-left: 2px solid transparent;
}
#chatList::item:selected {
    background-color: #111111; color: #e0e0e0;
    border-left: 2px solid #e0e0e0;
}
#chatList::item:hover:!selected { background-color: #0d0d0d; color: #777777; }
#settingsBtn {
    background-color: transparent; color: #363636;
    border: none; border-top: 1px solid #111111;
    font-size: 12px; padding: 11px 16px; margin: 0;
    border-radius: 0; text-align: left;
}
#settingsBtn:hover { background-color: #0d0d0d; color: #777777; }

/* ── Top bar ─────────────────────────── */
#chatTopBar {
    background-color: #080808;
    border-bottom: 1px solid #141414;
    min-height: 46px; max-height: 46px;
}
#modelLabel { color: #303030; font-size: 11px; background: transparent; }
#modelCombo {
    background-color: transparent; border: 1px solid #1c1c1c;
    border-radius: 5px; padding: 3px 8px; color: #595959; font-size: 11px; min-width: 190px;
}
#modelCombo:hover { border-color: #2c2c2c; color: #888888; }
#modelCombo::drop-down { border: none; width: 16px; }
#modelCombo QAbstractItemView {
    background-color: #0c0c0c; border: 1px solid #1c1c1c;
    color: #777777; selection-background-color: #181818; outline: none; font-size: 11px;
}
#modelRefreshBtn {
    background-color: transparent; border: 1px solid #181818;
    border-radius: 5px; color: #2e2e2e; font-size: 13px; padding: 0;
}
#modelRefreshBtn:hover { background-color: #0f0f0f; border-color: #2a2a2a; color: #666666; }

/* Mode toggle buttons */
#chatModePersistent, #chatModeTemp {
    background-color: transparent; border: 1px solid #1c1c1c;
    color: #353535; font-size: 10px; padding: 3px 10px;
    border-radius: 0; font-family: "Inter", sans-serif;
}
#chatModePersistent { border-radius: 4px 0 0 4px; border-right: none; }
#chatModeTemp { border-radius: 0 4px 4px 0; }
#chatModePersistent:hover, #chatModeTemp:hover { color: #777777; background: #0f0f0f; }
#chatModePersistent[active="true"], #chatModeTemp[active="true"] {
    background-color: #161616; color: #d0d0d0; border-color: #2a2a2a;
}

#exportBtn {
    background-color: transparent; border: 1px solid #181818;
    border-radius: 5px; color: #2e2e2e; font-size: 11px; padding: 4px 10px;
}
#exportBtn:hover { background-color: #0f0f0f; border-color: #2a2a2a; color: #555555; }

#logToggleTopBtn {
    background-color: transparent; border: 1px solid #181818;
    border-radius: 5px; color: #2a2a2a; font-size: 11px; padding: 4px 10px;
}
#logToggleTopBtn:hover { background: #0f0f0f; border-color: #2a2a2a; color: #555555; }
#logToggleTopBtn[active="true"] {
    background: #111111; border-color: #303030; color: #888888;
}

/* ── Chat area ───────────────────────── */
#chatArea { background-color: #0a0a0a; }
QTextBrowser {
    background-color: #0a0a0a; border: none;
    color: #d0d0d0; padding: 0;
    selection-background-color: #202020;
}

/* ── Input area ──────────────────────── */
#inputArea {
    background-color: #090909;
    border-top: 1px solid #131313;
}
#messageInput {
    background-color: #101010; border: 1px solid #202020;
    border-radius: 10px; padding: 10px 14px;
    color: #eeeeee; font-size: 13px; line-height: 1.5;
}
#messageInput:focus { border-color: #2c2c2c; background-color: #141414; }

/* ── Buttons ─────────────────────────── */
QPushButton {
    background-color: #0f0f0f; color: #777777;
    border: 1px solid #1c1c1c; border-radius: 7px;
    padding: 7px 14px; font-size: 12px;
}
QPushButton:hover { background-color: #161616; border-color: #292929; color: #c8c8c8; }
QPushButton:pressed { background-color: #1c1c1c; }

#sendBtn {
    background-color: #efefef; color: #060606;
    border: none; border-radius: 10px;
    font-weight: 800; font-size: 16px; padding: 0;
}
#sendBtn:hover { background-color: #ffffff; }
#sendBtn:pressed { background-color: #cccccc; }

#attachBtn {
    background-color: transparent; color: #323232;
    border: 1px solid #1a1a1a; border-radius: 10px;
    font-size: 17px; padding: 0;
}
#attachBtn:hover { background-color: #0f0f0f; color: #666666; border-color: #272727; }

/* ── Status / agent bar ──────────────── */
#statusLabel { color: #262626; font-size: 11px; padding: 1px 0; }
#agentStatusBar {
    background: #080808; border-top: 1px solid #0e0e0e;
    padding: 0 16px; min-height: 26px; max-height: 26px;
}
#agentStatusLabel {
    color: #242424; font-size: 11px; background: transparent;
    letter-spacing: 0.5px; font-family: "JetBrains Mono", monospace;
}

/* ── Scrollbar ───────────────────────── */
QScrollBar:vertical { background: transparent; width: 4px; margin: 2px 0; }
QScrollBar::handle:vertical { background: #1c1c1c; border-radius: 2px; min-height: 24px; }
QScrollBar::handle:vertical:hover { background: #2c2c2c; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

/* ── ComboBox ────────────────────────── */
QComboBox {
    background-color: #0d0d0d; border: 1px solid #1a1a1a;
    border-radius: 6px; padding: 5px 10px; color: #555555; font-size: 12px;
}
QComboBox:hover { border-color: #262626; color: #888888; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView {
    background-color: #0d0d0d; border: 1px solid #1c1c1c;
    color: #777777; selection-background-color: #1a1a1a; outline: none;
}

/* ── Labels ──────────────────────────── */
QLabel { color: #484848; background: transparent; }
QCheckBox { color: #555555; spacing: 8px; }
QCheckBox::indicator {
    width: 14px; height: 14px; border: 1px solid #282828;
    border-radius: 3px; background: #0d0d0d;
}
QCheckBox::indicator:checked { background: #dddddd; border-color: #dddddd; }

/* ── Menu ────────────────────────────── */
QMenu {
    background-color: #0c0c0c; border: 1px solid #202020;
    border-radius: 8px; padding: 4px;
}
QMenu::item { padding: 7px 16px; border-radius: 5px; color: #777777; font-size: 12px; }
QMenu::item:selected { background-color: #141414; color: #dddddd; }
QMenu::separator { height: 1px; background: #181818; margin: 4px 8px; }

/* ── Splitter ────────────────────────── */
QSplitter::handle { background: #0f0f0f; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical { height: 1px; }

/* ── LineEdit ────────────────────────── */
QLineEdit {
    background-color: #0d0d0d; border: 1px solid #1a1a1a;
    border-radius: 6px; padding: 7px 12px; color: #cccccc; font-size: 12px;
}
QLineEdit:focus { border-color: #2a2a2a; }

/* ── Tab ─────────────────────────────── */
QTabWidget::pane { border: 1px solid #141414; background: #0a0a0a; }
QTabBar::tab {
    background: transparent; color: #303030;
    padding: 8px 16px; border-bottom: 2px solid transparent; font-size: 12px;
}
QTabBar::tab:selected { color: #c0c0c0; border-bottom: 2px solid #c0c0c0; }
QTabBar::tab:hover:!selected { color: #555555; }

/* ── Right log panel ─────────────────── */
#logPanel { background-color: #060606; border-left: 1px solid #131313; }
#logPanelHeader {
    background: #080808; border-bottom: 1px solid #101010;
    min-height: 38px; max-height: 38px;
}
#logPanelTitle {
    color: #2e2e2e; font-size: 10px; font-weight: 600;
    letter-spacing: 1.2px; background: transparent;
    font-family: "JetBrains Mono", monospace;
}
#logCloseBtn {
    background: transparent; border: 1px solid #181818;
    border-radius: 4px; color: #282828; font-size: 12px; padding: 1px 7px;
}
#logCloseBtn:hover { background: #0f0f0f; color: #555555; border-color: #282828; }

/* ── Dialog ──────────────────────────── */
QDialog { background: #0b0b0b; }
QDialog QLabel { color: #606060; font-size: 12px; }
QTextEdit {
    background-color: #0d0d0d; border: 1px solid #1a1a1a;
    border-radius: 5px; color: #888888; font-size: 12px; padding: 4px;
}
"""

# MESSAGE_CSS: minimal base only — all real styles are INLINE in Python
# Qt's QTextBrowser only reliably supports inline style="" attributes
MESSAGE_CSS = """
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    background: #0a0a0a;
    color: #c4c4c4;
    font-family: "Inter", "Segoe UI", system-ui, sans-serif;
    font-size: 14px;
    line-height: 1.7;
    padding: 16px 0 12px 0;
}
table { border-collapse: collapse; }
a { color: #6a9fd8; text-decoration: none; }
a:hover { text-decoration: underline; }
code {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12.5px; color: #b5a46a;
    background: #141414; border: 1px solid #1e1e1e;
    padding: 2px 5px; border-radius: 4px;
}
pre {
    background: #080808; border: 1px solid #141414;
    padding: 12px 14px; border-radius: 7px;
    font-size: 12.5px; white-space: pre-wrap; word-wrap: break-word;
    font-family: "JetBrains Mono", "Consolas", monospace; color: #6e6e6e;
    margin: 8px 0;
}
pre code { background: none; border: none; padding: 0; }
h1,h2,h3,h4,h5,h6 { color: #e6e6e6; font-weight: 600; margin: 14px 0 5px 0; }
h1 { font-size: 18px; } h2 { font-size: 16px; } h3 { font-size: 14px; }
strong { color: #ebebeb; font-weight: 600; }
em { font-style: italic; color: #9a9a9a; }
ul, ol { padding-left: 20px; margin: 5px 0; }
li { margin: 3px 0; color: #bcbcbc; }
hr { border: none; border-top: 1px solid #1c1c1c; margin: 10px 0; }
blockquote {
    border-left: 2px solid #242424; padding: 4px 12px;
    color: #606060; margin: 8px 0; font-style: italic;
}
</style>
"""
