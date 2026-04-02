DARK_THEME = """
QMainWindow, QDialog {
    background-color: #1a1a1a;
    color: #e0e0e0;
}

QWidget {
    background-color: #1a1a1a;
    color: #e0e0e0;
    font-family: "Segoe UI", "SF Pro", "Helvetica Neue", sans-serif;
    font-size: 14px;
}

/* Sidebar */
#sidebar {
    background-color: #111111;
    border-right: 1px solid #2a2a2a;
}

#sidebar QPushButton {
    background-color: transparent;
    color: #b0b0b0;
    border: none;
    padding: 10px 16px;
    text-align: left;
    font-size: 13px;
    border-radius: 6px;
    margin: 2px 8px;
}

#sidebar QPushButton:hover {
    background-color: #252525;
    color: #ffffff;
}

#sidebar QPushButton:checked, #sidebar QPushButton[active="true"] {
    background-color: #2a2a2a;
    color: #ffffff;
}

/* Chat list */
#chatList {
    background-color: #111111;
    border: none;
}

#chatList::item {
    padding: 10px 16px;
    border-bottom: 1px solid #1f1f1f;
    color: #c0c0c0;
}

#chatList::item:selected {
    background-color: #2a2a2a;
    color: #ffffff;
}

#chatList::item:hover {
    background-color: #202020;
}

/* Chat area */
#chatArea {
    background-color: #1a1a1a;
    border: none;
}

/* Messages */
QTextBrowser {
    background-color: #1a1a1a;
    border: none;
    color: #e0e0e0;
    padding: 16px;
    font-size: 14px;
    line-height: 1.6;
}

/* Input area */
#inputArea {
    background-color: #1a1a1a;
    border-top: 1px solid #2a2a2a;
}

#messageInput {
    background-color: #252525;
    border: 1px solid #333333;
    border-radius: 12px;
    padding: 12px 16px;
    color: #e0e0e0;
    font-size: 14px;
    min-height: 20px;
    max-height: 150px;
}

#messageInput:focus {
    border-color: #505050;
}

/* Buttons */
QPushButton {
    background-color: #2a2a2a;
    color: #e0e0e0;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 8px 16px;
    font-size: 13px;
}

QPushButton:hover {
    background-color: #333333;
    border-color: #444444;
}

QPushButton:pressed {
    background-color: #404040;
}

#sendBtn {
    background-color: #ffffff;
    color: #000000;
    border: none;
    border-radius: 8px;
    padding: 8px 20px;
    font-weight: bold;
}

#sendBtn:hover {
    background-color: #e0e0e0;
}

#sendBtn:disabled {
    background-color: #333333;
    color: #666666;
}

#newChatBtn {
    background-color: #252525;
    color: #ffffff;
    border: 1px solid #333333;
    font-size: 13px;
    padding: 10px;
    margin: 8px;
}

/* Scroll bars */
QScrollBar:vertical {
    background: transparent;
    width: 8px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #404040;
    border-radius: 4px;
    min-height: 30px;
}

QScrollBar::handle:vertical:hover {
    background: #555555;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

/* Combo box */
QComboBox {
    background-color: #252525;
    border: 1px solid #333333;
    border-radius: 6px;
    padding: 6px 12px;
    color: #e0e0e0;
    min-width: 100px;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #252525;
    border: 1px solid #333333;
    color: #e0e0e0;
    selection-background-color: #404040;
}

/* Labels */
QLabel {
    color: #b0b0b0;
    background: transparent;
}

#statusLabel {
    color: #666666;
    font-size: 12px;
    padding: 4px 8px;
}

/* Checkbox */
QCheckBox {
    color: #b0b0b0;
    spacing: 8px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #444444;
    border-radius: 3px;
    background: #252525;
}

QCheckBox::indicator:checked {
    background: #ffffff;
    border-color: #ffffff;
}

/* Menu */
QMenu {
    background-color: #222222;
    border: 1px solid #333333;
    border-radius: 8px;
    padding: 4px;
}

QMenu::item {
    padding: 8px 24px;
    border-radius: 4px;
    color: #e0e0e0;
}

QMenu::item:selected {
    background-color: #333333;
}

/* Splitter */
QSplitter::handle {
    background: #2a2a2a;
    width: 1px;
}

/* Tab widget */
QTabWidget::pane {
    border: 1px solid #2a2a2a;
    background: #1a1a1a;
}

QTabBar::tab {
    background: #1a1a1a;
    color: #888888;
    padding: 8px 20px;
    border-bottom: 2px solid transparent;
}

QTabBar::tab:selected {
    color: #ffffff;
    border-bottom: 2px solid #ffffff;
}
"""


MESSAGE_CSS = """
<style>
body {
    font-family: "Segoe UI", "SF Pro", "Helvetica Neue", sans-serif;
    font-size: 14px;
    color: #e0e0e0;
    background: #1a1a1a;
    margin: 0;
    padding: 0;
}
.message {
    padding: 12px 20px;
    margin: 4px 0;
    border-radius: 4px;
    line-height: 1.6;
}
.user {
    color: #ffffff;
    border-left: 3px solid #ffffff;
    padding-left: 16px;
}
.assistant {
    color: #d0d0d0;
}
.tool {
    background: #111111;
    border: 1px solid #2a2a2a;
    border-radius: 8px;
    padding: 10px 14px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 12px;
    color: #888888;
    margin: 6px 0;
    white-space: pre-wrap;
    word-wrap: break-word;
}
.error {
    color: #ff6b6b;
    border-left: 3px solid #ff6b6b;
    padding-left: 16px;
}
.tool-label {
    color: #555555;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
}
.cursor {
    color: #666666;
    animation: blink 0.8s step-end infinite;
}
@keyframes blink {
    50% { opacity: 0; }
}
code {
    background: #252525;
    padding: 2px 6px;
    border-radius: 4px;
    font-family: "JetBrains Mono", "Consolas", monospace;
    font-size: 13px;
}
pre {
    background: #111111;
    padding: 12px;
    border-radius: 8px;
    overflow-x: auto;
    font-size: 13px;
}
</style>
"""
