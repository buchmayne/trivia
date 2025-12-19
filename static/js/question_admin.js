document.addEventListener('DOMContentLoaded', function() {
    const gameSelect = document.getElementById('id_game');
    const questionNumberInput = document.getElementById('id_question_number');
    const gameRoundSelect = document.getElementById('id_game_round');

    // Function to update game round based on question number
    const updateGameRound = (questionNumber) => {
        if (!gameRoundSelect || !questionNumber) {
            return;
        }

        const qNum = parseInt(questionNumber);
        let roundId;

        // Determine which round based on question number
        // Questions 1-10: Round 1
        // Questions 11-19: Round 2
        // Questions 20+: Final Round
        if (qNum >= 1 && qNum <= 10) {
            roundId = '1';  // Round 1 ID
        } else if (qNum >= 11 && qNum <= 19) {
            roundId = '2';  // Round 2 ID
        } else if (qNum >= 20) {
            roundId = '3';  // Final Round ID
        }

        // Set the game round select value
        if (roundId) {
            gameRoundSelect.value = roundId;
        }
    };

    if (gameSelect && questionNumberInput) {
        // Function to get the next question number
        const getNextQuestionNumber = async (gameId) => {
            try {
                // Fix the URL to match your urlpatterns
                const response = await fetch(`/quiz/next-question/${gameId}/`);
                const data = await response.json();
                if (data.next_number && (!questionNumberInput.value || questionNumberInput.value === '0')) {
                    questionNumberInput.value = data.next_number;
                    // Update game round based on the new question number
                    updateGameRound(data.next_number);
                }
            } catch (error) {
                console.error('Error fetching next question number:', error);
            }
        };

        // Add event listener to the game select
        gameSelect.addEventListener('change', function() {
            if (this.value) {
                getNextQuestionNumber(this.value);
            }
        });

        // Also check on page load
        if (gameSelect.value) {
            getNextQuestionNumber(gameSelect.value);
        }
    }

    // Add event listener to question number input for manual changes
    if (questionNumberInput && gameRoundSelect) {
        questionNumberInput.addEventListener('input', function() {
            updateGameRound(this.value);
        });

        // Also update on blur (when user leaves the field)
        questionNumberInput.addEventListener('blur', function() {
            updateGameRound(this.value);
        });
    }
});