DARK_THEME = """
QMainWindow, QDialog {
    background-color: #0d0d0d;
    color: #ececec;
}

QWidget {
    background-color: #0d0d0d;
    color: #ececec;
    font-family: "Inter", "Segoe UI", "SF Pro Text", "Helvetica Neue", sans-serif;
    font-size: 14px;
}

/* ── Sidebar ── */
#sidebar {
    background-color: #080808;
    border-right: 1px solid #161616;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #6b6b6b;
    border: none;
    padding: 8px 12px;
    text-align: left;
    font-size: 13px;
    border-radius: 6px;
    margin: 1px 6px;
}

#sidebar QPushButton:hover {
    background-color: #131313;
    color: #c0c0c0;
}

#chatList {
    background-color: #080808;
    border: none;
    outline: none;
}

#chatList::item {
    padding: 8px 12px;
    border-radius: 6px;
    color: #6b6b6b;
    margin: 1px 6px;
    font-size: 13px;
}

#chatList::item:selected {
    background-color: #161616;
    color: #e8e8e8;
}

#chatList::item:hover:!selected {
    background-color: #0f0f0f;
    color: #a0a0a0;
}

#newChatBtn {
    background-color: transparent;
    color: #8a8a8a;
    border: 1px solid #1e1e1e;
    font-size: 13px;
    padding: 9px 12px;
    margin: 6px 8px 4px 8px;
    border-radius: 6px;
    text-align: left;
}

#newChatBtn:hover {
    background-color: #111111;
    border-color: #282828;
    color: #d0d0d0;
}

/* ── Chat area ── */
#chatArea {
    background-color: #0d0d0d;
}

QTextBrowser {
    background-color: #0d0d0d;
    border: none;
    color: #d4d4d4;
    padding: 0;
    selection-background-color: #2a2a2a;
}

/* ── Input area ── */
#inputArea {
    background-color: #0d0d0d;
    border-top: none;
    padding-top: 0;
}

#messageInput {
    background-color: #141414;
    border: 1px solid #212121;
    border-radius: 12px;
    padding: 12px 16px;
    color: #ececec;
    font-size: 14px;
    line-height: 1.5;
}

#messageInput:focus {
    border-color: #303030;
    background-color: #161616;
    outline: none;
}

/* ── Buttons ── */
QPushButton {
    background-color: #141414;
    color: #a0a0a0;
    border: 1px solid #202020;
    border-radius: 7px;
    padding: 7px 14px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #1a1a1a;
    border-color: #2c2c2c;
    color: #d8d8d8;
}

QPushButton:pressed {
    background-color: #222222;
}

#sendBtn {
    background-color: #efefef;
    color: #080808;
    border: none;
    border-radius: 10px;
    font-weight: 700;
    font-size: 15px;
    padding: 0;
}

#sendBtn:hover {
    background-color: #ffffff;
}

#sendBtn:pressed {
    background-color: #d4d4d4;
}

#attachBtn {
    background-color: transparent;
    color: #4a4a4a;
    border: 1px solid #1e1e1e;
    border-radius: 10px;
    font-size: 18px;
    font-weight: 300;
    padding: 0;
}

#attachBtn:hover {
    background-color: #141414;
    color: #888888;
    border-color: #2a2a2a;
}

/* ── Status ── */
#statusLabel {
    color: #3a3a3a;
    font-size: 11px;
    padding: 2px 4px;
    letter-spacing: 0.2px;
}

/* ── Scrollbar ── */
QScrollBar:vertical {
    background: transparent;
    width: 4px;
    margin: 2px 0;
}

QScrollBar::handle:vertical {
    background: #202020;
    border-radius: 2px;
    min-height: 24px;
}

QScrollBar::handle:vertical:hover {
    background: #303030;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

/* ── ComboBox ── */
QComboBox {
    background-color: #111111;
    border: 1px solid #1e1e1e;
    border-radius: 6px;
    padding: 5px 10px;
    color: #888888;
    min-width: 100px;
    font-size: 12px;
}

QComboBox:hover {
    border-color: #282828;
    color: #aaaaaa;
}

QComboBox::drop-down { border: none; width: 18px; }

QComboBox QAbstractItemView {
    background-color: #111111;
    border: 1px solid #1e1e1e;
    color: #888888;
    selection-background-color: #1e1e1e;
    outline: none;
}

/* ── Labels ── */
QLabel {
    color: #6b6b6b;
    background: transparent;
}

/* ── Checkbox ── */
QCheckBox { color: #777777; spacing: 8px; }
QCheckBox::indicator {
    width: 15px; height: 15px;
    border: 1px solid #2e2e2e;
    border-radius: 4px;
    background: #111111;
}
QCheckBox::indicator:checked {
    background: #e0e0e0;
    border-color: #e0e0e0;
}

/* ── Menu ── */
QMenu {
    background-color: #111111;
    border: 1px solid #222222;
    border-radius: 10px;
    padding: 5px;
}
QMenu::item { padding: 8px 16px; border-radius: 5px; color: #a8a8a8; font-size: 13px; }
QMenu::item:selected { background-color: #1a1a1a; color: #e8e8e8; }

/* ── Splitter ── */
QSplitter::handle { background: #131313; width: 1px; }

/* ── LineEdit ── */
QLineEdit {
    background-color: #111111;
    border: 1px solid #1e1e1e;
    border-radius: 6px;
    padding: 7px 12px;
    color: #d0d0d0;
}
QLineEdit:focus { border-color: #303030; }

/* ── Tab ── */
QTabWidget::pane { border: 1px solid #181818; background: #0d0d0d; }
QTabBar::tab { background: transparent; color: #505050; padding: 8px 18px; border-bottom: 2px solid transparent; font-size: 13px; }
QTabBar::tab:selected { color: #d0d0d0; border-bottom: 2px solid #d0d0d0; }
QTabBar::tab:hover:!selected { color: #888888; }

/* ── Chat top bar ── */
#chatTopBar {
    background-color: #0d0d0d;
    border-bottom: 1px solid #141414;
}

/* ── Model selector ── */
#modelCombo {
    background-color: transparent;
    border: 1px solid #1a1a1a;
    border-radius: 5px;
    padding: 3px 8px;
    color: #484848;
    font-size: 12px;
    min-width: 180px;
}
#modelCombo:hover {
    border-color: #252525;
    color: #707070;
}
#modelCombo::drop-down { border: none; width: 16px; }
#modelCombo QAbstractItemView {
    background-color: #0e0e0e;
    border: 1px solid #1a1a1a;
    color: #888888;
    selection-background-color: #161616;
    outline: none;
    font-size: 12px;
}

/* ── Model refresh button ── */
#modelRefreshBtn {
    background-color: transparent;
    border: 1px solid #1a1a1a;
    border-radius: 5px;
    color: #333333;
    font-size: 13px;
    padding: 0;
}
#modelRefreshBtn:hover {
    background-color: #111111;
    border-color: #242424;
    color: #606060;
}

/* ── Export button ── */
#exportBtn {
    background-color: transparent;
    border: 1px solid #1a1a1a;
    border-radius: 5px;
    color: #333333;
    font-size: 12px;
    padding: 4px 10px;
}
#exportBtn:hover {
    background-color: #111111;
    border-color: #242424;
    color: #606060;
}
"""


MESSAGE_CSS = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: "Inter", "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 14.5px;
    color: #c8c8c8;
    background: #0d0d0d;
    padding: 24px 0 20px 0;
    line-height: 1.75;
}

/* ── Message layout ── */
.msg-wrap {
    padding: 2px 48px;
    max-width: 100%;
}

.msg-wrap.user {
    display: flex;
    justify-content: flex-end;
    padding: 4px 32px;
}

.bubble-user {
    background: #1a1a1a;
    border: 1px solid #242424;
    border-radius: 18px 18px 4px 18px;
    padding: 11px 16px;
    max-width: 70%;
    color: #e8e8e8;
    font-size: 14.5px;
    word-wrap: break-word;
    line-height: 1.65;
}

.msg-wrap.assistant {
    padding: 4px 48px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
}

/* Assistant avatar dot */
.msg-wrap.assistant::before {
    content: "";
    display: inline-block;
    width: 24px;
    height: 24px;
    min-width: 24px;
    border-radius: 50%;
    background: #1c1c1c;
    border: 1px solid #242424;
    margin-top: 2px;
}

.bubble-assistant {
    color: #cccccc;
    font-size: 14.5px;
    max-width: calc(100% - 36px);
    word-wrap: break-word;
    flex: 1;
}

/* ── Markdown inside assistant ── */
.bubble-assistant h1, .bubble-assistant h2, .bubble-assistant h3,
.bubble-assistant h4, .bubble-assistant h5, .bubble-assistant h6 {
    color: #e4e4e4;
    font-weight: 600;
    margin: 16px 0 6px 0;
    line-height: 1.3;
}
.bubble-assistant h1 { font-size: 20px; }
.bubble-assistant h2 { font-size: 17px; }
.bubble-assistant h3 { font-size: 15px; }
.bubble-assistant h4, .bubble-assistant h5, .bubble-assistant h6 { font-size: 14px; }

.bubble-assistant strong { color: #e8e8e8; font-weight: 600; }
.bubble-assistant em { font-style: italic; color: #b0b0b0; }

.bubble-assistant ul, .bubble-assistant ol {
    padding-left: 20px;
    margin: 6px 0;
}
.bubble-assistant li {
    margin: 4px 0;
    color: #c0c0c0;
}

.bubble-assistant a {
    color: #6ba3d6;
    text-decoration: none;
}
.bubble-assistant a:hover { text-decoration: underline; }

.bubble-assistant hr {
    border: none;
    border-top: 1px solid #202020;
    margin: 12px 0;
}

.bubble-assistant .blockquote {
    border-left: 3px solid #2a2a2a;
    padding: 4px 14px;
    color: #787878;
    margin: 8px 0;
    font-style: italic;
}

.bubble-assistant code {
    background: #161616;
    border: 1px solid #222222;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: "JetBrains Mono", "Fira Code", "Consolas", monospace;
    font-size: 13px;
    color: #c0a870;
}

.code-block {
    margin: 10px 0;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #1c1c1c;
    background: #0a0a0a;
}
.code-lang {
    display: block;
    background: #0e0e0e;
    color: #3a3a3a;
    font-size: 10.5px;
    padding: 5px 14px;
    letter-spacing: 0.6px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    text-transform: uppercase;
    border-bottom: 1px solid #161616;
}
.code-block pre {
    background: #0a0a0a;
    padding: 14px 16px;
    margin: 0;
}
.code-block pre code {
    background: none;
    border: none;
    padding: 0;
    font-size: 13px;
    color: #8a8a8a;
    color: #9ca3af;
}

/* ── Error / tool ── */
.msg-wrap.error { padding: 4px 48px; }
.bubble-error {
    color: #e05555;
    border-left: 2px solid #c03333;
    padding-left: 12px;
    font-size: 13.5px;
    max-width: 88%;
    line-height: 1.6;
}

.tool-wrap { padding: 2px 48px 2px 84px; }
.tool-header {
    color: #2e2e2e;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    margin-bottom: 4px;
}
.tool-body {
    background: #090909;
    border: 1px solid #181818;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    color: #404040;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-width: 92%;
    line-height: 1.5;
}

/* ── Streaming cursor ── */
.cursor {
    display: inline-block;
    width: 2px;
    height: 15px;
    background: #404040;
    margin-left: 2px;
    vertical-align: text-bottom;
    animation: blink 1s step-end infinite;
}
@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

/* ── Generic code / pre ── */
code {
    background: #161616;
    border: 1px solid #202020;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    color: #c0a870;
}
pre {
    background: #0a0a0a;
    border: 1px solid #181818;
    padding: 14px 16px;
    border-radius: 9px;
    font-size: 13px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    color: #7a7a7a;
    margin: 8px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
pre code { background: none; border: none; padding: 0; }

/* ── Math (LaTeX rendered) ── */
.math-block {
    display: block;
    background: #0e0e0e;
    border: 1px solid #1c1c1c;
    border-radius: 6px;
    padding: 10px 16px;
    margin: 8px 0;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13.5px;
    color: #b8a060;
    text-align: center;
    overflow-x: auto;
}
.math-inline {
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    color: #b8a060;
    background: #111111;
    padding: 1px 4px;
    border-radius: 3px;
}


/* ── Tool output improvements ── */
.tool-header { display: flex; align-items: center; gap: 8px; }
.tool-name {
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
}
.tool-header-ok .tool-name { color: #3a6a3a; }
.tool-header-err .tool-name { color: #7a3030; }

.ec-ok {
    font-size: 10px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    color: #2e5a2e;
    background: #0d1a0d;
    border: 1px solid #1a3a1a;
    border-radius: 3px;
    padding: 0px 5px;
}
.ec-err {
    font-size: 10px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    color: #7a2020;
    background: #1a0808;
    border: 1px solid #3a1010;
    border-radius: 3px;
    padding: 0px 5px;
}

</style>
"""

# File chip + file card CSS appended to MESSAGE_CSS
_EXTRA = """
.attach-chip {
    background: #141414;
    border: 1px solid #202020;
    border-radius: 8px;
    margin-bottom: 6px;
}
.attach-chip .ac-icon {
    padding: 8px 8px 8px 10px;
    font-size: 15px;
}
.attach-chip .ac-name {
    padding: 8px 6px;
    color: #c0c0c0;
    font-size: 13px;
    font-weight: 500;
}
.attach-chip .ac-ext {
    padding: 8px 10px 8px 4px;
    color: #484848;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.bubble-file-text {
    color: #e0e0e0;
    font-size: 14px;
    padding-top: 6px;
}

.fc-wrap {
    padding: 4px 32px 4px 84px;
}
.file-card {
    background: #0e0e0e;
    border: 1px solid #1c1c1c;
    border-radius: 10px;
    max-width: 360px;
}
.file-card .fc-icon-cell {
    padding: 12px 10px 12px 14px;
    font-size: 22px;
    vertical-align: middle;
}
.file-card .fc-info-cell {
    padding: 12px 8px;
    vertical-align: middle;
}
.file-card .fc-name {
    color: #d0d0d0;
    font-size: 13px;
    font-weight: 500;
}
.file-card .fc-meta {
    color: #383838;
    font-size: 11px;
    margin-top: 2px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.file-card .fc-action-cell {
    padding: 12px 14px 12px 8px;
    vertical-align: middle;
}
.fc-link {
    color: #5a8fc0;
    font-size: 12px;
    text-decoration: none;
    white-space: nowrap;
}
"""

MESSAGE_CSS = MESSAGE_CSS.replace("</style>", _EXTRA + "\n</style>")
