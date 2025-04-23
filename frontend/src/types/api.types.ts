// Define the Game structure
export interface Game {
    id: number;
    name: string;
    description: string;
    created_at: string;
    // Add any other fields from your Game model
  }
  
  // Define the Answer structure
  export interface Answer {
    id: number;
    text: string;
    points: number;
    explanation: string | null;
    answer_text: string | null;
    question_image_url: string | null;
    answer_image_url: string | null;
    // Add any other fields from your Answer model
  }
  
  // Define the Question structure
  export interface Question {
    id: number;
    text: string;
    question_number: number;
    total_points: number;
    question_image_url: string | null;
    answer_image_url: string | null;
    answers: Answer[];  // Questions include an array of answers
    // Add any other fields from your Question model
  }
  
  // The API might return paginated results, so define a structure for that
  export interface ApiResponse<T> {
    count?: number;
    next?: string | null;
    previous?: string | null;
    results?: T[];  // The actual data array
  }