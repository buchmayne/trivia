// session_service/static/app.js

// Global utilities and shared functionality
class TriviaApp {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.sessionCode = null;
        this.isHost = false;
        this.currentQuestion = 0;
        this.totalQuestions = 0;
        this.teams = [];
        this.currentAnswer = null;
    }

    // WebSocket connection management
    connectWebSocket(sessionCode, isHost, name = '') {
        if (this.ws) {
            this.ws.close();
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}/ws/${sessionCode}?type=${isHost ? 'host' : 'team'}&name=${encodeURIComponent(name)}`;
        
        console.log('Connecting to WebSocket:', url);
        
        this.ws = new WebSocket(url);
        this.sessionCode = sessionCode;
        this.isHost = isHost;

        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
            this.updateConnectionStatus(true);
        };

        this.ws.onmessage = (event) => {
            const message = JSON.parse(event.data);
            console.log('Received message:', message);
            this.handleMessage(message);
        };

        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            this.updateConnectionStatus(false);
            
            // Attempt to reconnect after 3 seconds
            setTimeout(() => {
                if (!this.isConnected) {
                    console.log('Attempting to reconnect...');
                    this.connectWebSocket(sessionCode, isHost, name);
                }
            }, 3000);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    // Send message via WebSocket
    sendMessage(type, data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            const message = { type, data };
            console.log('Sending message:', message);
            this.ws.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected, cannot send message');
        }
    }

    // Handle incoming messages
    handleMessage(message) {
        switch (message.type) {
            case 'connected':
                this.handleConnected(message.data);
                break;
            case 'team_joined':
                this.handleTeamJoined(message.data);
                break;
            case 'game_started':
                this.handleGameStarted(message.data);
                break;
            case 'question_display':
                this.handleQuestionDisplay(message.data);
                break;
            case 'question_displayed_host':
                this.handleQuestionDisplayHost(message.data);
                break;
            case 'answer_submitted':
                this.handleAnswerSubmitted(message.data);
                break;
            case 'round_complete':
                this.handleRoundComplete(message.data);
                break;
            default:
                console.log('Unhandled message type:', message.type);
        }
    }

    // Message handlers
    handleConnected(data) {
        console.log('Connected to session:', data);
        this.currentQuestion = data.current_question;
        this.totalQuestions = data.total_questions;
        
        if (this.isHost) {
            this.updateHostStatus(data);
        } else {
            this.updateTeamStatus(data);
        }
    }

    handleTeamJoined(data) {
        console.log('Team joined:', data);
        this.teams = data.teams || [];
        this.updateTeamsList();
    }

    handleGameStarted(data) {
        console.log('Game started:', data);
        this.showAlert('Game is starting!', 'success');
        
        if (this.isHost) {
            this.enableHostControls();
        } else {
            this.hideWaitingRoom();
        }
    }

    handleQuestionDisplay(data) {
        console.log('Question displayed:', data);
        this.currentQuestion = data.question_number;
        this.totalQuestions = data.total_questions;
        this.showQuestion(data.question, data.question_number);
    }

    handleQuestionDisplayHost(data) {
        console.log('Question displayed for host:', data);
        this.currentQuestion = data.question_number;
        this.showQuestionHost(data.question, data.question_number);
    }

    handleAnswerSubmitted(data) {
        console.log('Answer submitted:', data);
        if (this.isHost) {
            this.showAnswerSubmission(data);
        }
    }

    handleRoundComplete(data) {
        console.log('Round complete:', data);
        this.showAlert('Round complete! Ready for scoring.', 'success');
    }

    // UI update methods
    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connection-status');
        const textEl = document.getElementById('connection-text');
        
        if (statusEl && textEl) {
            if (connected) {
                statusEl.classList.add('connected');
                statusEl.classList.remove('disconnected');
                textEl.textContent = 'Connected';
            } else {
                statusEl.classList.remove('connected');
                statusEl.classList.add('disconnected');
                textEl.textContent = 'Disconnected';
            }
        }
    }

    updateHostStatus(data) {
        const statusEl = document.getElementById('game-status');
        const questionEl = document.getElementById('current-question');
        const teamCountEl = document.getElementById('team-count');
        
        if (statusEl) statusEl.textContent = data.status || 'Waiting';
        if (questionEl) questionEl.textContent = `${data.current_question}/${data.total_questions}`;
        if (teamCountEl) teamCountEl.textContent = this.teams.length;
    }

    updateTeamStatus(data) {
        const statusEl = document.getElementById('game-status');
        const questionEl = document.getElementById('current-question');
        
        if (statusEl) statusEl.textContent = data.status || 'Waiting';
        if (questionEl) questionEl.textContent = `${data.current_question}/${data.total_questions}`;
    }

    updateTeamsList() {
        const teamsContainer = document.getElementById('teams-container');
        const teamsListCompact = document.getElementById('teams-list');
        
        // Update host view
        if (teamsContainer) {
            if (this.teams.length === 0) {
                teamsContainer.innerHTML = '<div class="no-teams">No teams connected yet</div>';
            } else {
                teamsContainer.innerHTML = this.teams.map(team => `
                    <div class="team-card">
                        <div class="team-name">${this.escapeHtml(team.name)}</div>
                        <div class="team-score">Score: ${team.score || 0}</div>
                    </div>
                `).join('');
            }
        }
        
        // Update team join view
        if (teamsListCompact) {
            if (this.teams.length === 0) {
                teamsListCompact.innerHTML = '<div class="loading">No teams yet...</div>';
            } else {
                teamsListCompact.innerHTML = this.teams.map(team => 
                    `<span class="team-tag">${this.escapeHtml(team.name)}</span>`
                ).join('');
            }
        }
    }

    showQuestion(question, questionNumber) {
        const questionDisplay = document.getElementById('question-display');
        const waitingRoom = document.getElementById('waiting-room');
        const answerSubmitted = document.getElementById('answer-submitted');
        
        // Hide other sections
        if (waitingRoom) waitingRoom.classList.add('hidden');
        if (answerSubmitted) answerSubmitted.classList.add('hidden');
        
        // Show question
        if (questionDisplay) {
            questionDisplay.classList.remove('hidden');
            
            // Update question content
            const questionText = document.getElementById('question-text');
            const questionNum = document.getElementById('question-number');
            const totalQuestions = document.getElementById('total-questions');
            const questionPoints = document.getElementById('question-points');
            const answerOptions = document.getElementById('answer-options');
            
            if (questionText) questionText.textContent = question.text;
            if (questionNum) questionNum.textContent = questionNumber;
            if (totalQuestions) totalQuestions.textContent = this.totalQuestions;
            if (questionPoints) questionPoints.textContent = question.points || 1;
            
            // Create answer options
            if (answerOptions && question.answers) {
                answerOptions.innerHTML = question.answers.map(answer => `
                    <label class="answer-option">
                        <input type="radio" name="answer" value="${answer.id}">
                        <span>${this.escapeHtml(answer.text)}</span>
                    </label>
                `).join('');
                
                // Add event listeners
                const radioButtons = answerOptions.querySelectorAll('input[type="radio"]');
                radioButtons.forEach(radio => {
                    radio.addEventListener('change', () => {
                        this.selectAnswer(radio.value);
                        this.updateAnswerSelection();
                    });
                });
            }
            
            // Reset submit button
            const submitBtn = document.getElementById('submit-answer-btn');
            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.textContent = '📝 Submit Answer';
            }
        }
    }

    showQuestionHost(question, questionNumber) {
        const questionDisplay = document.getElementById('question-display');
        
        if (questionDisplay) {
            questionDisplay.classList.remove('hidden');
            
            const questionText = document.getElementById('question-text');
            const questionNum = document.getElementById('question-number');
            const totalQuestions = document.getElementById('total-questions');
            const questionPoints = document.getElementById('question-points');
            const questionAnswers = document.getElementById('question-answers');
            
            if (questionText) questionText.textContent = question.text;
            if (questionNum) questionNum.textContent = questionNumber;
            if (totalQuestions) totalQuestions.textContent = this.totalQuestions;
            if (questionPoints) questionPoints.textContent = question.points || 1;
            
            // Show all answers with correct answers highlighted
            if (questionAnswers && question.answers) {
                questionAnswers.innerHTML = question.answers.map(answer => `
                    <div class="answer-item ${answer.correct_rank ? 'correct-answer' : ''}">
                        <span class="answer-text">${this.escapeHtml(answer.text)}</span>
                        ${answer.correct_rank ? `<span class="correct-indicator">✓ (${answer.points} pts)</span>` : ''}
                    </div>
                `).join('');
            }
        }
    }

    selectAnswer(answerId) {
        this.currentAnswer = answerId;
    }

    updateAnswerSelection() {
        const submitBtn = document.getElementById('submit-answer-btn');
        if (submitBtn) {
            submitBtn.disabled = !this.currentAnswer;
        }
        
        // Update visual selection
        const options = document.querySelectorAll('.answer-option');
        options.forEach(option => {
            const radio = option.querySelector('input[type="radio"]');
            if (radio.checked) {
                option.classList.add('selected');
            } else {
                option.classList.remove('selected');
            }
        });
    }

    submitAnswer() {
        if (this.currentAnswer && this.currentQuestion) {
            this.sendMessage('submit_answer', {
                question_number: this.currentQuestion,
                answer: this.currentAnswer
            });
            
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
    }

    hideWaitingRoom() {
        const waitingRoom = document.getElementById('waiting-room');
        if (waitingRoom) {
            waitingRoom.classList.add('hidden');
        }
    }

    enableHostControls() {
        const startBtn = document.getElementById('start-game-btn');
        const nextBtn = document.getElementById('next-question-btn');
        
        if (startBtn) startBtn.disabled = true;
        if (nextBtn) nextBtn.disabled = false;
    }

    showAlert(message, type = 'info') {
        // Create and show a temporary alert
        const alert = document.createElement('div');
        alert.className = `alert alert-${type}`;
        alert.textContent = message;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(alert, container.firstChild);
            
            setTimeout(() => {
                alert.remove();
            }, 5000);
        }
    }

    // Utility methods
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTime(timestamp) {
        return new Date(timestamp).toLocaleTimeString();
    }
}

// Global app instance
window.triviaApp = new TriviaApp();

// Utility functions
function copySessionCode() {
    const codeElement = document.getElementById('session-code-display');
    if (codeElement) {
        const code = codeElement.textContent.trim();
        
        if (navigator.clipboard) {
            navigator.clipboard.writeText(code).then(() => {
                triviaApp.showAlert('Session code copied to clipboard!', 'success');
            }).catch(() => {
                fallbackCopyTextToClipboard(code);
            });
        } else {
            fallbackCopyTextToClipboard(code);
        }
    }
}

function fallbackCopyTextToClipboard(text) {
    const textArea = document.createElement('textarea');
    textArea.value = text;
    textArea.style.position = 'fixed';
    textArea.style.top = '0';
    textArea.style.left = '0';
    textArea.style.width = '2em';
    textArea.style.height = '2em';
    textArea.style.padding = '0';
    textArea.style.border = 'none';
    textArea.style.outline = 'none';
    textArea.style.boxShadow = 'none';
    textArea.style.background = 'transparent';
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    
    try {
        document.execCommand('copy');
        triviaApp.showAlert('Session code copied to clipboard!', 'success');
    } catch (err) {
        triviaApp.showAlert('Failed to copy session code', 'error');
    }
    
    document.body.removeChild(textArea);
}

// Auto-uppercase input fields
document.addEventListener('DOMContentLoaded', function() {
    const sessionCodeInputs = document.querySelectorAll('input[name="session_code"]');
    sessionCodeInputs.forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.toUpperCase();
        });
    });
});