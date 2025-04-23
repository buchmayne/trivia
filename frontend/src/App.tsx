import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import GameList from './components/GameList';

function App() {
  return (
    <div className="bg-gray-100 min-h-screen">
      <header className="bg-blue-600 text-white p-4">
        <h1 className="text-xl font-bold">Trivia App</h1>
      </header>
      <main className="container mx-auto p-4">
        <h2 className="text-2xl mb-4">Welcome to Trivia App</h2>
        {/* Your router will go here eventually */}
      </main>
    </div>
  );
}

export default App;