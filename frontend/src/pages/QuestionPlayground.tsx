import React, { useState } from 'react';
import QuestionDisplay from '../components/QuestionDisplay';

// Sample question data for testing
const sampleQuestion = {
    id: 17,
    text: "For each of the following charts of google search trends, identify the search term from the chart (3 Points Each)",
    question_type: 3,
    question_number: 17,
    total_points: 12,
    question_image_url: null,
    answer_image_url: null,
    answers: [
        {
            id: 78,
            text: "A.",
            points: 3,
            answer_text: "Bitcoin",
            explanation: "",
            question_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/bitcoin.png",
            answer_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/answer_bitcoin.png"
        },
        {
            id: 79,
            text: "B.",
            points: 3,
            answer_text: "Trump",
            explanation: "",
            question_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/trump.png",
            answer_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/answer_trump.png"
        },
        {
            id: 80,
            text: "C.",
            points: 3,
            answer_text: "Ukraine",
            explanation: "",
            question_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/ukraine.png",
            answer_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/answer_ukraine.png"
        },
        {
            id: 81,
            text: "D.",
            points: 3,
            answer_text: "Covid",
            explanation: "",
            question_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/covid.png",
            answer_image_url: "https://d1eomq1h9ixjmb.cloudfront.net/2024/April/Popularity/answer_covid.png"
        }
    ]
};

const QuestionPlayground: React.FC = () => {
  const [answerResult, setAnswerResult] = useState<string | null>(null);
  
  const handleAnswerSubmit = (answerId: number) => {
    // Find the selected answer from our sample question
    const selectedAnswer = sampleQuestion.answers.find(a => a.id === answerId);
    
    if (selectedAnswer) {
      if (selectedAnswer.points > 0) {
        setAnswerResult(`Correct! You earned ${selectedAnswer.points} points.`);
      } else {
        setAnswerResult("Sorry, that's incorrect.");
      }
    }
  };
  
  return (
    <div className="container mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6 text-center">Question Display Playground</h1>
      
      <QuestionDisplay 
        question={sampleQuestion} 
        onAnswerSubmit={handleAnswerSubmit} 
      />
      
      {answerResult && (
        <div className="mt-6 p-4 rounded-lg text-center font-medium">
          {answerResult}
        </div>
      )}
    </div>
  );
};

export default QuestionPlayground;