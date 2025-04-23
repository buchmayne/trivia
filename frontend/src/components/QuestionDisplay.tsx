import React, { useState } from 'react';
import { Question, Answer } from '../types/api.types';

interface QuestionDisplayProps {
  question: Question;
  onAnswerSubmit: (answerId: number) => void;
  timeLimit?: number; // Optional time limit in seconds
}

const QuestionDisplay: React.FC<QuestionDisplayProps> = ({ 
  question, 
  onAnswerSubmit,
  timeLimit 
}) => {
  const [selectedAnswerId, setSelectedAnswerId] = useState<number | null>(null);
  
  const handleAnswerSelect = (answerId: number) => {
    setSelectedAnswerId(answerId);
  };
  
  const handleSubmit = () => {
    if (selectedAnswerId !== null) {
      onAnswerSubmit(selectedAnswerId);
    }
  };
  
  return (
    <div className="bg-white rounded-lg shadow-lg p-6 max-w-3xl mx-auto">
      {/* Question header with number and points */}
      <div className="mb-6">
        <span className="bg-blue-600 text-white px-3 py-1 rounded-full text-sm mr-2">
          Q{question.question_number}
        </span>
        <span className="text-gray-600 text-sm">
          {question.total_points} {question.total_points === 1 ? 'point' : 'points'}
        </span>
      </div>
      
      {/* Question text */}
      <h2 className="text-xl font-bold mb-6">{question.text}</h2>
      
      {/* Question image if available */}
      {question.question_image_url && (
        <div className="mb-6">
          <img 
            src={question.question_image_url} 
            alt="Question" 
            className="max-w-full rounded-lg mx-auto"
          />
        </div>
      )}
      
      {/* Answer options */}
      <div className="space-y-3 mb-6">
        {question.answers.map((answer) => (
          <div
            key={answer.id}
            className={`p-4 border rounded-lg cursor-pointer transition-colors ${
              selectedAnswerId === answer.id
                ? 'bg-blue-100 border-blue-500'
                : 'hover:bg-gray-50'
            }`}
            onClick={() => handleAnswerSelect(answer.id)}
          >
            <div className="flex items-start">
              <div className="flex-1">
                <p className="font-medium">{answer.text}</p>
              </div>
              {answer.question_image_url && (
                <div className="ml-4 flex-shrink-0">
                  <img
                    src={answer.question_image_url}
                    alt={answer.text}
                    className="w-24 h-24 object-cover rounded"
                  />
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
      
      {/* Submit button */}
      <div className="text-center">
        <button
          onClick={handleSubmit}
          disabled={selectedAnswerId === null}
          className={`px-6 py-2 rounded-lg font-medium ${
            selectedAnswerId === null
              ? 'bg-gray-300 cursor-not-allowed'
              : 'bg-blue-600 text-white hover:bg-blue-700'
          }`}
        >
          Submit Answer
        </button>
      </div>
    </div>
  );
};

export default QuestionDisplay;