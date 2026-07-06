import { useState, useEffect } from "react";
import Auth from "./Auth";
import Chat from "./Chat";
import "./App.css";

const TOKEN_KEY = "eada_token";

export default function App() {
  const [token, setToken] = useState<string | null>(null);

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
  }

  if (!token) {
    return <Auth onAuthenticated={handleAuthenticated} />;
  }

  return (
    <Chat
      token={token}
      onLogout={handleLogout}
    />
  );
}
