import { useState, useEffect } from "react";
import Auth from "./Auth";
import Chat from "./Chat";
import "./App.css";

const TOKEN_KEY = "eada_token";

export default function App() {
  const [token, setToken] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | undefined>(
    undefined
  );

  useEffect(() => {
    const saved = localStorage.getItem(TOKEN_KEY);
    if (saved) setToken(saved);
  }, []);

  function handleAuthenticated(newToken: string) {
    localStorage.setItem(TOKEN_KEY, newToken);
    setToken(newToken);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setConversationId(undefined);
  }

  if (!token) {
    return <Auth onAuthenticated={handleAuthenticated} />;
  }

  return (
    <Chat
      token={token}
      conversationId={conversationId}
      onConversationStarted={setConversationId}
      onLogout={handleLogout}
    />
  );
}