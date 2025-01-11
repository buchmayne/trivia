document.addEventListener('DOMContentLoaded', function() {
    // Helper function to determine if we're in answer view
    function isAnswerView() {
        return window.location.pathname.includes('answer');
    }

    // Helper function to get correct URL based on view mode
    function getNavigationUrl(gameId, roundId, categoryId, questionId) {
        if (isAnswerView()) {
            return `/quiz/game/${gameId}/answers/round/${roundId}/answers/category/${categoryId}/question/${questionId}/`;
        } else {
            return `/quiz/game/${gameId}/questions/round/${roundId}/questions/category/${categoryId}/question/${questionId}/`;
        }
    }
    
    // Round selector handling
    const roundSelector = document.getElementById('roundSelector');
    if (roundSelector) {
        roundSelector.addEventListener('change', async function() {
            const gameId = document.querySelector('.question-nav-button').dataset.gameId;
            const roundId = this.value;
            
            try {
                const response = await fetch(`/quiz/game/${gameId}/questions/round/${roundId}/questions-list/`);
                const data = await response.json();
                updateQuestionButtons(data.questions, roundId, gameId);
            } catch (error) {
                console.error('Error:', error);
            }
        });
    }

    // Function to update question buttons
    function updateQuestionButtons(questions, roundId, gameId) {
        const navigator = document.querySelector('.question-navigator');
        navigator.innerHTML = questions.map(q => `
            <button class="question-nav-button"
                    data-question-id="${q.id}"
                    data-category-id="${q.category_id}"
                    data-round-id="${roundId}"
                    data-game-id="${gameId}">
                ${q.question_number}
            </button>
        `).join('');
        
        // Reattach click handlers to new buttons
        attachQuestionButtonHandlers();
    }

    // Function to attach click handlers to question buttons
    function attachQuestionButtonHandlers() {
        document.querySelectorAll('.question-nav-button').forEach(button => {
            button.addEventListener('click', handleQuestionButtonClick);
        });
    }

    // Question button click handler
    function handleQuestionButtonClick() {
        const gameId = this.dataset.gameId;
        const roundId = this.dataset.roundId;
        const categoryId = this.dataset.categoryId;
        const questionId = this.dataset.questionId;
        
        // const newUrl = `/quiz/game/${gameId}/questions/round/${roundId}/questions/category/${categoryId}/question/${questionId}/`;
        const newUrl = getNavigationUrl(gameId, roundId, categoryId, questionId);
        window.location.href = newUrl;
    }

    // Initial attachment of handlers to existing buttons
    document.querySelectorAll('.question-nav-button').forEach(button => {
        button.addEventListener('click', handleQuestionButtonClick);
    });

    const viewToggle = document.getElementById('viewToggle');
    if (viewToggle) {
        viewToggle.addEventListener('click', function() {
            const currentPath = window.location.pathname;
            // Replace all instances of 'questions' with 'answers' or vice versa
            const newPath = currentPath.includes('answers') 
                ? currentPath.replace(/answers/g, 'questions')
                : currentPath.replace(/questions/g, 'answers');
            window.location.href = newPath;
        });
    }
});