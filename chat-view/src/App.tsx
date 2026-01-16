import { useState, useEffect, useCallback, useRef } from 'react';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { useChat } from './hooks/useChat';
import type { Session } from './types';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [isSessionsLoading, setIsSessionsLoading] = useState(false);

  const shouldSkipLoadRef = useRef(false);

  // チャットフックの初期化
  // セッションIDが新規発行されたらstateを更新する
  const handleSessionCreated = useCallback((newId: string) => {
    shouldSkipLoadRef.current = true;
    setSessionId(newId);
    fetchSessions(); // リストも更新
  }, []);

  const { chatState, sendMessage, loadHistory, clearChat } = useChat(sessionId, handleSessionCreated);

  // セッション一覧取得
  const fetchSessions = async () => {
    try {
      setIsSessionsLoading(true);
      const res = await fetch('/api/sessions?limit=20');
      if (res.ok) {
        const data = await res.json();
        setSessions(data.sessions);
      }
    } catch (e) {
      console.error("Failed to load sessions", e);
    } finally {
      setIsSessionsLoading(false);
    }
  };

  // 初回ロード & チャット完了時にリスト更新（タイトル更新など反映）
  useEffect(() => {
    fetchSessions();
  }, [chatState.isLoading]); // loadingがfalseになったタイミング（応答完了）で更新

  // セッション切り替え時の処理
  useEffect(() => {
    if (sessionId) {
      if (shouldSkipLoadRef.current) {
        console.log("Skipping loadHistory for newly created session.");
        shouldSkipLoadRef.current = false;
        return;
      }
      loadHistory(sessionId);
    } else {
      clearChat();
    }
  }, [sessionId, loadHistory, clearChat]);

  const handleNewChat = () => {
    setSessionId(null);
  };

  return (
    <div className="flex h-screen bg-gray-100 overflow-hidden">
      <Sidebar
        sessions={sessions}
        currentSessionId={sessionId}
        onSelectSession={setSessionId}
        onNewChat={handleNewChat}
        isLoading={isSessionsLoading}
      />
      <main className="flex-1 flex flex-col h-full min-w-0">
        <ChatWindow
          chatState={chatState}
          onSendMessage={sendMessage}
        />
      </main>
    </div>
  );
}

export default App;