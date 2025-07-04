// session_service/static/team.js

// Team-specific functionality
class TeamController {
    constructor() {
        this.teamName = null;
        this.hasJoined = false;
        this.currentAnswer = null;
        this.answerSubmitted = false;
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Team join form
        const joinForm = document.getElementById('join-session-form');
        if (joinForm) {
            joinForm.addEventListener('submit', (e) => this.handleJoinSession(e));
        }

        // Answer submission
        const submitBtn = document.getElementById('submit-answer-btn');
        if (submitBtn) {
            submitBtn.addEventListener('click', () => this.submitAnswer());
        }

        // Auto-uppercase session code
        const sessionCodeInput = document.getElementById('session-code');
        if (sessionCodeInput) {
            sessionCodeInput.addEventListener('input', function() {
                this.value = this.value.toUpperCase();
            });
        }
    }

    async handleJoinSession(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const sessionCode = formData.get('session_code').toUpperCase();
        const teamName = formData.get('team_name').trim();

        if (!sessionCode || !teamName) {
            triviaApp.showAlert('Please enter both session code and team name', 'error');
            return;
        }

        try {
            this.showLoading('Joining session...');
            
            // First, verify the session exists
            const response = await fetch(`/api/sessions/${sessionCode}`);
            
            if (!response.ok) {
                if (response.status === 404) {
                    throw new Error('Session not found. Please check your session code.');
                } else {
                    throw new Error(`Error: ${response.status}`);
                }
            }

            const sessionData = await response.json();
            console.log('Session found:', sessionData);
            
            // Store team info
            this.teamName = teamName;
            this.hasJoined = true;
            
            // Show team dashboard
            this.showTeamDashboard(sessionData, teamName);
            
            // Connect to WebSocket
            triviaApp.connectWebSocket(sessionCode, false, teamName);
            
            // Send join message
            setTimeout(() => {
                triviaApp.sendMessage('join_team', {
                    team_name: teamName
                });
            }, 500);
            
        } catch (error) {
            console.error('Error joining session:', error);
            triviaApp.showAlert(error.message || 'Failed to join session. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    showTeamDashboard(sessionData, teamName) {
        const joinForm = document.getElementById('join-form');
        const teamDashboard = document.getElementById('team-dashboard');
        const gameTitle = document.getElementById('game-title');
        const teamNameDisplay = document.getElementById('team-name-display');
        const sessionCodeDisplay = document.getElementById('session-code-display');

        if (joinForm) joinForm.classList.add('hidden');
        if (teamDashboard) teamDashboard.classList.remove('hidden');
        if (gameTitle) gameTitle.textContent = `Playing ${sessionData.game_name}`;
        if (teamNameDisplay) teamNameDisplay.textContent = teamName;
        if (sessionCodeDisplay) sessionCodeDisplay.textContent = sessionData.session_code;

        // Update page title
        document.title = `${teamName} - ${sessionData.game_name} - Trivia Service`;
    }

    submitAnswer() {
        if (this.currentAnswer && triviaApp.currentQuestion && !this.answerSubmitted) {
            triviaApp.sendMessage('submit_answer', {
                question_number: triviaApp.currentQuestion,
                answer: this.currentAnswer
            });
            
            this.answerSubmitted = true;
            this.showAnswerSubmitted();
        }
    }

    showAnswerSubmitted() {
        const answerForm = document.getElementById('answer-form');
        const answerSubmitted = document.getElementById('answer-submitted');
        const submittedAnswerText = document.getElementById('submitted-answer-text');
        
        if (answerForm) answerForm.classList.add('hidden');
        if (answerSubmitted) answerSubmitted.classList.remove('hidden');
        
        // Show selected answer text
        if (submittedAnswerText && this.currentAnswer) {
            const selectedOption = document.querySelector(`input[value="${this.currentAnswer}"]`);
            if (selectedOption) {
                const answerText = selectedOption.parentElement.querySelector('span').textContent;
                submittedAnswerText.textContent = answerText;
            }
        }
        
        triviaApp.showAlert('Answer submitted successfully!', 'success');
    }

    // Handle answer selection
    selectAnswer(answerId) {
        this.currentAnswer = answerId;
        this.updateAnswerSelection();
    }

    updateAnswerSelection() {
        const submitBtn = document.getElementById('submit-answer-btn');
        if (submitBtn && !this.answerSubmitted) {
            submitBtn.disabled = !this.currentAnswer;
        }
        
        // Update visual selection
        const options = document.querySelectorAll('.answer-option');
        options.forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            if (radio && radio.checked) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
    }

    // Reset for new question
    resetForNewQuestion() {
        this.currentAnswer = null;
        this.answerSubmitted = false;
        
        // Show answer form, hide submitted message
        const answerForm = document.getElementById('answer-form');
        const answerSubmitted = document.getElementById('answer-submitted');
        
        if (answerForm) answerForm.classList.remove('hidden');
        if (answerSubmitted) answerSubmitted.classList.add('hidden');
        
        // Reset submit button
        const submitBtn = document.getElementById('submit-answer-btn');
        if (submitBtn) {
            submitBtn.disabled = true;
            submitBtn.textContent = '📝 Submit Answer';
        }
        
        // Clear radio selections
        const radioButtons = document.querySelectorAll('input[type="radio"]');
        radioButtons.forEach(radio => {
            radio.checked = false;
        });
        
        // Clear visual selections
        const options = document.querySelectorAll('.answer-option');
        options.forEach(option => {
            option.classList.remove('selected');
        });
    }

    // Handle team-specific messages
    handleTeamMessage(message) {
        switch (message.type) {
            case 'question_display':
                this.handleQuestionDisplay(message.data);
                break;
            case 'game_started':
                this.handleGameStarted(message.data);
                break;
            case 'team_joined':
                this.handleTeamUpdate(message.data);
                break;
            case 'scores_update':
                this.handleScoresUpdate(message.data);
                break;
        }
    }

    handleQuestionDisplay(data) {
        console.log('New question received:', data);
        
        // Reset for new question
        this.resetForNewQuestion();
        
        // Set up answer options with event listeners
        setTimeout(() => {
            const answerOptions = document.getElementById('answer-options');
            if (answerOptions) {
                const radioButtons = answerOptions.querySelectorAll('input[type="radio"]');
                radioButtons.forEach(radio => {
                    radio.addEventListener('change', () => {
                        if (radio.checked) {
                            this.selectAnswer(radio.value);
                        }
                    });
                });
            }
        }, 100);
    }

    handleGameStarted(data) {
        console.log('Game started:', data);
        
        // Hide waiting room
        const waitingRoom = document.getElementById('waiting-room');
        if (waitingRoom) {
            waitingRoom.classList.add('hidden');
        }
        
        triviaApp.showAlert('Game is starting! Get ready for the first question.', 'success');
    }

    handleTeamUpdate(data) {
        console.log('Teams updated:', data);
        // Teams list is handled by the main TriviaApp class
    }

    handleScoresUpdate(data) {
        console.log('Scores updated:', data);
        if (data.scores) {
            this.displayScores(data.scores);
        }
    }

    displayScores(scores) {
        const scoresDisplay = document.getElementById('scores-display');
        const scoresList = document.getElementById('scores-list');
        
        if (scoresDisplay && scoresList && scores) {
            scoresDisplay.classList.remove('hidden');
            
            // Sort scores by points (descending)
            const sortedScores = Object.entries(scores)
                .map(([team, score]) => ({ team, score }))
                .sort((a, b) => b.score - a.score);
            
            scoresList.innerHTML = sortedScores.map((item, index) => {
                const rank = index + 1;
                const rankClass = rank <= 3 ? `rank-${rank}` : '';
                
                return `
                    <div class="score-item ${rankClass}">
                        <span class="score-rank">${rank}</span>
                        <span class="score-team">${this.escapeHtml(item.team)}</span>
                        <span class="score-points">${item.score} pts</span>
                    </div>
                `;
            }).join('');
        }
    }

    showLoading(message = 'Loading...') {
        // Create or update loading indicator
        let loading = document.getElementById('loading-indicator');
        if (!loading) {
            loading = document.createElement('div');
            loading.id = 'loading-indicator';
            loading.className = 'alert';
            loading.style.position = 'fixed';
            loading.style.top = '20px';
            loading.style.right = '20px';
            loading.style.zIndex = '1000';
            document.body.appendChild(loading);
        }
        loading.textContent = message;
        loading.style.display = 'block';
    }

    hideLoading() {
        const loading = document.getElementById('loading-indicator');
        if (loading) {
            loading.style.display = 'none';
        }
    }

    // Utility methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    getSelectedAnswer() {
        const selectedRadio = document.querySelector('input[name="answer"]:checked');
        return selectedRadio ? selectedRadio.value : null;
    }

    isAnswerSubmitted() {
        return this.answerSubmitted;
    }

    getTeamName() {
        return this.teamName;
    }
}

// Initialize team controller when page loads
const teamController = new TeamController();

document.addEventListener('DOMContentLoaded', function() {
    teamController.init();
    
    // Override triviaApp message handler to include team-specific logic
    const originalHandleMessage = triviaApp.handleMessage.bind(triviaApp);
    triviaApp.handleMessage = function(message) {
        originalHandleMessage(message);
        teamController.handleTeamMessage(message);
    };
    
    // Override selectAnswer to use team controller
    const originalSelectAnswer = triviaApp.selectAnswer.bind(triviaApp);
    triviaApp.selectAnswer = function(answerId) {
        originalSelectAnswer(answerId);
        teamController.selectAnswer(answerId);
    };
    
    // Override submitAnswer to use team controller
    triviaApp.submitAnswer = function() {
        teamController.submitAnswer();
    };
});

// Export for global access
window.teamController = teamController;