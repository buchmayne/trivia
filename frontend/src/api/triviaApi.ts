import axios from 'axios';
import { Game, Question, ApiResponse } from '../types/api.types';

// Base URL of your Django API - adjust if needed for your monorepo setup
const API_URL = '/quiz/api';  // Using relative path for same-origin requests

// Function to get all games
export const getGames = async (): Promise<ApiResponse<Game>> => {
  try {
    const response = await axios.get<ApiResponse<Game>>(`${API_URL}/games/`);
    return response.data;
  } catch (error) {
    console.error("Error fetching games:", error);
    throw error;
  }
};

// Function to get a specific game by ID
export const getGameById = async (gameId: number): Promise<Game> => {
  try {
    const response = await axios.get<Game>(`${API_URL}/games/${gameId}/`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching game ${gameId}:`, error);
    throw error;
  }
};

// Function to get questions for a specific game
export const getQuestionsByGame = async (gameId: number): Promise<ApiResponse<Question>> => {
  try {
    const response = await axios.get<ApiResponse<Question>>(`${API_URL}/questions/?game__id=${gameId}`);
    return response.data;
  } catch (error) {
    console.error(`Error fetching questions for game ${gameId}:`, error);
    throw error;
  }
};