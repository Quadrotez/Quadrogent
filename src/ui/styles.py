DARK_THEME = """
QMainWindow, QDialog {
    background-color: #0f0f0f;
    color: #e8e8e8;
}

QWidget {
    background-color: #0f0f0f;
    color: #e8e8e8;
    font-family: "Inter", "Segoe UI", "SF Pro Display", "Helvetica Neue", sans-serif;
    font-size: 14px;
}

/* Sidebar */
#sidebar {
    background-color: #080808;
    border-right: 1px solid #1e1e1e;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #777777;
    border: none;
    padding: 9px 14px;
    text-align: left;
    font-size: 13px;
    border-radius: 8px;
    margin: 1px 8px;
}

#sidebar QPushButton:hover {
    background-color: #141414;
    color: #cccccc;
}

#chatList {
    background-color: #080808;
    border: none;
    outline: none;
}

#chatList::item {
    padding: 9px 14px;
    border-radius: 8px;
    color: #888888;
    margin: 2px 8px;
}

#chatList::item:selected {
    background-color: #1a1a1a;
    color: #f0f0f0;
}

#chatList::item:hover:!selected {
    background-color: #111111;
    color: #bbbbbb;
}

#newChatBtn {
    background-color: #141414;
    color: #cccccc;
    border: 1px solid #222222;
    font-size: 13px;
    padding: 10px 14px;
    margin: 8px;
    border-radius: 8px;
    text-align: left;
}

#newChatBtn:hover {
    background-color: #1e1e1e;
    border-color: #303030;
    color: #ffffff;
}

/* Chat area */
#chatArea {
    background-color: #0f0f0f;
}

QTextBrowser {
    background-color: #0f0f0f;
    border: none;
    color: #d0d0d0;
    padding: 0;
    selection-background-color: #2e2e2e;
}

/* Input area */
#inputArea {
    background-color: #0f0f0f;
    border-top: 1px solid #181818;
}

#messageInput {
    background-color: #161616;
    border: 1px solid #262626;
    border-radius: 14px;
    padding: 11px 16px;
    color: #e8e8e8;
    font-size: 14px;
}

#messageInput:focus {
    border-color: #383838;
    background-color: #191919;
}

/* Buttons */
QPushButton {
    background-color: #1a1a1a;
    color: #bbbbbb;
    border: 1px solid #252525;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #222222;
    border-color: #333333;
    color: #e0e0e0;
}

QPushButton:pressed {
    background-color: #2a2a2a;
}

#sendBtn {
    background-color: #f0f0f0;
    color: #0a0a0a;
    border: none;
    border-radius: 10px;
    font-weight: 600;
    font-size: 16px;
    padding: 0;
}

#sendBtn:hover {
    background-color: #ffffff;
}

#sendBtn:pressed {
    background-color: #d8d8d8;
}

#attachBtn {
    background-color: #141414;
    color: #666666;
    border: 1px solid #202020;
    border-radius: 10px;
    font-size: 20px;
    font-weight: 300;
    padding: 0;
}

#attachBtn:hover {
    background-color: #1e1e1e;
    color: #aaaaaa;
    border-color: #2e2e2e;
}

/* Status */
#statusLabel {
    color: #383838;
    font-size: 11px;
    padding: 2px 4px;
    letter-spacing: 0.3px;
}

/* Scrollbar */
QScrollBar:vertical {
    background: transparent;
    width: 5px;
    margin: 4px 0;
}

QScrollBar::handle:vertical {
    background: #252525;
    border-radius: 2px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #383838;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal { height: 0; }

/* Combo box */
QComboBox {
    background-color: #161616;
    border: 1px solid #252525;
    border-radius: 7px;
    padding: 6px 12px;
    color: #bbbbbb;
    min-width: 100px;
}

QComboBox::drop-down { border: none; width: 20px; }

QComboBox QAbstractItemView {
    background-color: #161616;
    border: 1px solid #252525;
    color: #bbbbbb;
    selection-background-color: #252525;
    outline: none;
}

/* Labels */
QLabel {
    color: #888888;
    background: transparent;
}

/* Checkbox */
QCheckBox { color: #888888; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 1px solid #333333;
    border-radius: 4px;
    background: #161616;
}
QCheckBox::indicator:checked {
    background: #e0e0e0;
    border-color: #e0e0e0;
}

/* Menu */
QMenu {
    background-color: #141414;
    border: 1px solid #252525;
    border-radius: 10px;
    padding: 6px;
}
QMenu::item { padding: 8px 18px; border-radius: 6px; color: #bbbbbb; font-size: 13px; }
QMenu::item:selected { background-color: #1e1e1e; color: #ffffff; }

/* Splitter */
QSplitter::handle { background: #181818; width: 1px; }

/* Line edit */
QLineEdit {
    background-color: #161616;
    border: 1px solid #252525;
    border-radius: 7px;
    padding: 7px 12px;
    color: #d0d0d0;
}
QLineEdit:focus { border-color: #383838; }

/* Tab */
QTabWidget::pane { border: 1px solid #1e1e1e; background: #0f0f0f; }
QTabBar::tab { background: transparent; color: #555555; padding: 8px 20px; border-bottom: 2px solid transparent; font-size: 13px; }
QTabBar::tab:selected { color: #d0d0d0; border-bottom: 2px solid #d0d0d0; }
QTabBar::tab:hover:!selected { color: #888888; }
"""


MESSAGE_CSS = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
    font-family: "Inter", "Segoe UI", "SF Pro", "Helvetica Neue", sans-serif;
    font-size: 14px;
    color: #cccccc;
    background: #0f0f0f;
    padding: 16px 0 12px 0;
    line-height: 1.7;
}

.msg-wrap {
    padding: 3px 24px;
}

.msg-wrap.user {
    display: flex;
    justify-content: flex-end;
    padding: 4px 20px;
}

.bubble-user {
    background: #1c1c1c;
    border: 1px solid #282828;
    border-radius: 16px 16px 4px 16px;
    padding: 10px 15px;
    max-width: 74%;
    color: #ececec;
    font-size: 14px;
    word-wrap: break-word;
}

.msg-wrap.assistant {
    padding: 4px 24px;
}

.bubble-assistant {
    color: #c0c0c0;
    font-size: 14px;
    max-width: 90%;
    word-wrap: break-word;
}

.msg-wrap.error {
    padding: 4px 24px;
}

.bubble-error {
    color: #ee5555;
    border-left: 2px solid #cc3333;
    padding-left: 12px;
    font-size: 13px;
    max-width: 88%;
}

.tool-wrap {
    padding: 2px 24px;
}

.tool-header {
    color: #333333;
    font-size: 10px;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    margin-bottom: 3px;
}

.tool-body {
    background: #0b0b0b;
    border: 1px solid #1c1c1c;
    border-radius: 8px;
    padding: 9px 13px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    color: #484848;
    white-space: pre-wrap;
    word-wrap: break-word;
    max-width: 88%;
}

.cursor {
    display: inline-block;
    width: 2px;
    height: 14px;
    background: #484848;
    margin-left: 1px;
    vertical-align: text-bottom;
    animation: blink 0.9s step-end infinite;
}

@keyframes blink {
    0%, 100% { opacity: 1; }
    50% { opacity: 0; }
}

code {
    background: #181818;
    border: 1px solid #222222;
    padding: 1px 5px;
    border-radius: 4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
    color: #b0b0b0;
}

pre {
    background: #0b0b0b;
    border: 1px solid #1c1c1c;
    padding: 12px 14px;
    border-radius: 8px;
    font-size: 13px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    color: #888888;
    margin: 6px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}

pre code { background: none; border: none; padding: 0; }
</style>
"""

# Appended: file chip + file card CSS for MESSAGE_CSS
_EXTRA = """
.attach-chip {
    background: #1a1a1a;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    margin-bottom: 6px;
}
.attach-chip .ac-icon {
    padding: 7px 8px 7px 10px;
    font-size: 15px;
}
.attach-chip .ac-name {
    padding: 7px 6px;
    color: #cccccc;
    font-size: 13px;
    font-weight: 500;
}
.attach-chip .ac-ext {
    padding: 7px 10px 7px 4px;
    color: #555555;
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
    padding: 4px 24px;
}
.file-card {
    background: #111111;
    border: 1px solid #1e1e1e;
    border-radius: 10px;
    max-width: 380px;
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
    color: #444444;
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
    color: #5599dd;
    font-size: 12px;
    text-decoration: none;
    white-space: nowrap;
}
"""

# Inject into MESSAGE_CSS
MESSAGE_CSS = MESSAGE_CSS.replace("</style>", _EXTRA + "\n</style>")
