import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getGames } from '../api/triviaApi';
import { Game } from '../types/api.types';

const GameList: React.FC = () => {
  // State to store the list of games
  const [games, setGames] = useState<Game[]>([]);
  // State to track loading status
  const [loading, setLoading] = useState<boolean>(true);
  // State to store any error messages
  const [error, setError] = useState<string | null>(null);

  // useEffect hook to fetch data when component mounts
  useEffect(() => {
    const fetchGames = async () => {
      try {
        setLoading(true);
        const data = await getGames();
        setGames(data.results || []);
        setLoading(false);
      } catch (err) {
        setError('Failed to fetch games. Please try again later.');
        setLoading(false);
      }
    };

    fetchGames();
  }, []);

  if (loading) return <div className="text-center p-4">Loading games...</div>;
  if (error) return <div className="text-red-500 p-4">{error}</div>;

  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Available Trivia Games</h1>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {games.map((game) => (
          <Link 
            to={`/games/${game.id}`} 
            key={game.id} 
            className="block p-4 border rounded-lg hover:shadow-md transition-shadow"
          >
            <h2 className="text-xl font-semibold">{game.name}</h2>
            <p className="text-gray-600">{game.description || ''}</p>
            <div className="mt-2 text-blue-500">View Game →</div>
          </Link>
        ))}
      </div>
    </div>
  );
};

export default GameList;