import "./Sidebar.css";

export default function Sidebar({ chats, currentChatId, isLoading, userName, onNewChat, onSelectChat, onDeleteChat, onExportChat, onOpenProfile }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>Чаты</h2>
        <button className="new-chat-btn" onClick={onNewChat} disabled={isLoading}>
          + Новый
        </button>
      </div>
      <div className="chat-list">
        {chats.length === 0 && (
          <div className="chat-list-empty">Нет сохранённых чатов</div>
        )}
        {chats.map((chat) => (
          <div
            key={chat.id}
            className={`chat-item ${currentChatId === chat.id ? "active" : ""}`}
            onClick={() => onSelectChat(chat.id)}
          >
            <span className="chat-item-title">{chat.title}</span>
            <button
              className="chat-item-export"
              onClick={(e) => onExportChat(chat.id, e)}
              title="Экспорт в JSON"
            >
              💾
            </button>
            <button
              className="chat-item-delete"
              onClick={(e) => onDeleteChat(chat.id, e)}
              title="Удалить чат"
            >
              ✕
            </button>
          </div>
        ))}
      </div>
      <div className="sidebar-footer">
        <button className="sidebar-profile-btn" onClick={onOpenProfile} title="Профиль">
          <span className="sidebar-profile-icon">👤</span>
          <span className="sidebar-profile-name">{userName || "Профиль"}</span>
        </button>
      </div>
    </aside>
  );
}
