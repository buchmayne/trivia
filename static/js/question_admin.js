document.addEventListener('DOMContentLoaded', function() {
    const gameSelect = document.getElementById('id_game');
    const questionNumberInput = document.getElementById('id_question_number');
    
    if (gameSelect && questionNumberInput) {
        // Function to get the next question number
        const getNextQuestionNumber = async (gameId) => {
            try {
                // Fix the URL to match your urlpatterns
                const response = await fetch(`/quiz/next-question/${gameId}/`);
                const data = await response.json();
                if (data.next_number && (!questionNumberInput.value || questionNumberInput.value === '0')) {
                    questionNumberInput.value = data.next_number;
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
});