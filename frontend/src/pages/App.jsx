import React from "react";
import { Routes, Route, Link } from "react-router-dom";

function Home() {
  return (
    <div>
      <h1>AI Study QnA</h1>
      <p>Hello World (Module 1)</p>
    </div>
  );
}

function Upload() {
  return <div>Upload Page</div>;
}

function Chat() {
  return <div>Chat Page</div>;
}

function History() {
  return <div>History Page</div>;
}

export default function App() {
  return (
    <div style={{ padding: 16 }}>
      <nav style={{ display: "flex", gap: 12, marginBottom: 16 }}>
        <Link to="/">Home</Link>
        <Link to="/upload">Upload</Link>
        <Link to="/chat">Chat</Link>
        <Link to="/history">History</Link>
      </nav>
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/upload" element={<Upload />} />
        <Route path="/chat" element={<Chat />} />
        <Route path="/history" element={<History />} />
      </Routes>
    </div>
  );
}
