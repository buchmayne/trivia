import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import GameList from './components/GameList';
import QuestionPlayground from './pages/QuestionPlayground';

function App() {
  return (
    <div className="bg-gray-100 min-h-screen">
      <header className="bg-blue-600 text-white p-4">
        <h1 className="text-xl font-bold">Trivia App</h1>
      </header>
      <Router>
        <main className="container mx-auto p-4">
          <Routes>
            <Route path="/" element={<GameList />} />
            <Route path="/question-playground" element={<QuestionPlayground />} />
          </Routes>
        </main>
      </Router>
    </div>
  );
}

export default App;