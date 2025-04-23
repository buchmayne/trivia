import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getGameById, getQuestionsByGame } from '../api/triviaApi';
import { Game, Question } from '../types/api.types';

const GameDetail: React.FC = () => {
  const { gameId } = useParams<{ gameId: string }>();
  const [game, setGame] = useState<Game | null>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchGameData = async () => {
      try {
        setLoading(true);
        if (!gameId) return;
        
        const gameData = await getGameById(parseInt(gameId));
        setGame(gameData);
        
        const questionsData = await getQuestionsByGame(parseInt(gameId));
        setQuestions(questionsData.results || []);
        
        setLoading(false);
      } catch (err) {
        setError('Failed to load game data');
        setLoading(false);
      }
    };

    fetchGameData();
  }, [gameId]);

  if (loading) return <div className="text-center p-4">Loading game details...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;
  if (!game) return <div className="text-center p-4">Game not found</div>;

  return (
    <div className="container mx-auto p-4">
      <Link to="/" className="text-blue-500 mb-4 inline-block">← Back to Games</Link>
      
      <h1 className="text-3xl font-bold mb-4">{game.name}</h1>
      <p className="mb-6">{game.description}</p>
      
      <h2 className="text-2xl font-semibold mb-3">Questions</h2>
      <div className="space-y-4">
        {questions.map((question) => (
          <div key={question.id} className="border p-4 rounded-lg">
            <h3 className="text-xl mb-2">
              <span className="font-semibold">#{question.question_number}:</span> {question.text}
            </h3>
            <p className="text-sm text-gray-600">Points: {question.total_points}</p>
          </div>
        ))}
      </div>
    </div>
  );
};

export default GameDetail;