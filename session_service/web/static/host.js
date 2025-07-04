// session_service/static/host.js

// Host-specific functionality
class HostController {
    constructor() {
        this.sessionData = null;
        this.gameStarted = false;
    }

    init() {
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Session creation form
        const createForm = document.getElementById('create-session-form');
        if (createForm) {
            createForm.addEventListener('submit', (e) => this.handleCreateSession(e));
        }

        // Host control buttons
        const startGameBtn = document.getElementById('start-game-btn');
        if (startGameBtn) {
            startGameBtn.addEventListener('click', () => this.startGame());
        }

        const nextQuestionBtn = document.getElementById('next-question-btn');
        if (nextQuestionBtn) {
            nextQuestionBtn.addEventListener('click', () => this.nextQuestion());
        }

        const showQuestionBtn = document.getElementById('show-question-btn');
        if (showQuestionBtn) {
            showQuestionBtn.addEventListener('click', () => this.showCurrentQuestion());
        }

        const showScoresBtn = document.getElementById('show-scores-btn');
        if (showScoresBtn) {
            showScoresBtn.addEventListener('click', () => this.showScores());
        }

        const endSessionBtn = document.getElementById('end-session-btn');
        if (endSessionBtn) {
            endSessionBtn.addEventListener('click', () => this.endSession());
        }
    }

    async handleCreateSession(e) {
        e.preventDefault();
        
        const formData = new FormData(e.target);
        const data = {
            game: parseInt(formData.get('game')),
            host_name: formData.get('host_name'),
            max_teams: parseInt(formData.get('max_teams'))
        };

        try {
            this.showLoading('Creating session...');
            
            const response = await fetch('/api/sessions', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(data)
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();
            this.sessionData = result;
            
            console.log('Session created:', result);
            
            // Hide setup form and show session dashboard
            this.showSessionDashboard(result);
            
            // Connect to WebSocket
            triviaApp.connectWebSocket(result.session_code, true, data.host_name);
            
        } catch (error) {
            console.error('Error creating session:', error);
            triviaApp.showAlert('Failed to create session. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }

    showSessionDashboard(sessionData) {
        const setupForm = document.getElementById('setup-form');
        const sessionDashboard = document.getElementById('session-dashboard');
        const sessionCodeDisplay = document.getElementById('session-code-display');

        if (setupForm) setupForm.classList.add('hidden');
        if (sessionDashboard) sessionDashboard.classList.remove('hidden');
        if (sessionCodeDisplay) sessionCodeDisplay.textContent = sessionData.session_code;

        // Update page title
        document.title = `Host Dashboard - ${sessionData.game_name} - Trivia Service`;
    }

    startGame() {
        if (!this.gameStarted) {
            triviaApp.sendMessage('host_command', {
                command: 'start_game'
            });
            this.gameStarted = true;
            
            const startBtn = document.getElementById('start-game-btn');
            const nextBtn = document.getElementById('next-question-btn');
            const showQuestionBtn = document.getElementById('show-question-btn');
            
            if (startBtn) {
                startBtn.disabled = true;
                startBtn.textContent = '✅ Game Started';
            }
            if (nextBtn) nextBtn.disabled = false;
            if (showQuestionBtn) showQuestionBtn.disabled = false;
        }
    }

    nextQuestion() {
        triviaApp.sendMessage('host_command', {
            command: 'next_question'
        });
    }

    showCurrentQuestion() {
        const questionNum = triviaApp.currentQuestion || 1;
        triviaApp.sendMessage('host_command', {
            command: 'show_question',
            question_number: questionNum
        });
    }

    showScores() {
        triviaApp.sendMessage('host_command', {
            command: 'show_scores'
        });
    }

    endSession() {
        if (confirm('Are you sure you want to end this session? This cannot be undone.')) {
            triviaApp.sendMessage('host_command', {
                command: 'end_session'
            });
            
            // Disconnect WebSocket
            if (triviaApp.ws) {
                triviaApp.ws.close();
            }
            
            // Redirect to home page
            setTimeout(() => {
                window.location.href = '/';
            }, 2000);
        }
    }

    showAnswerSubmission(data) {
        console.log('Answer submitted:', data);
        
        // Create a temporary notification
        const notification = document.createElement('div');
        notification.className = 'alert alert-success';
        notification.textContent = `${data.team_name} submitted an answer for Question ${data.question_number}`;
        
        const container = document.querySelector('.container');
        if (container) {
            container.insertBefore(notification, container.firstChild);
            
            setTimeout(() => {
                notification.remove();
            }, 3000);
        }
    }

    updateGameStatus(status) {
        const statusEl = document.getElementById('game-status');
        if (statusEl) {
            statusEl.textContent = status;
        }
        
        // Update button states based on status
        this.updateControlButtons(status);
    }

    updateControlButtons(status) {
        const startBtn = document.getElementById('start-game-btn');
        const nextBtn = document.getElementById('next-question-btn');
        const showScoresBtn = document.getElementById('show-scores-btn');
        
        switch (status) {
            case 'waiting':
                if (startBtn) startBtn.disabled = false;
                if (nextBtn) nextBtn.disabled = true;
                if (showScoresBtn) showScoresBtn.disabled = true;
                break;
            case 'active':
                if (startBtn) startBtn.disabled = true;
                if (nextBtn) nextBtn.disabled = false;
                if (showScoresBtn) showScoresBtn.disabled = false;
                break;
            case 'scoring':
                if (startBtn) startBtn.disabled = true;
                if (nextBtn) nextBtn.disabled = true;
                if (showScoresBtn) showScoresBtn.disabled = false;
                break;
            case 'completed':
                if (startBtn) startBtn.disabled = true;
                if (nextBtn) nextBtn.disabled = true;
                if (showScoresBtn) showScoresBtn.disabled = false;
                break;
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

    // Handle host-specific messages
    handleHostMessage(message) {
        switch (message.type) {
            case 'team_joined':
                this.handleTeamJoined(message.data);
                break;
            case 'answer_submitted':
                this.showAnswerSubmission(message.data);
                break;
            case 'game_started':
                this.updateGameStatus('active');
                break;
            case 'question_displayed_host':
                this.handleQuestionDisplayed(message.data);
                break;
        }
    }

    handleTeamJoined(data) {
        triviaApp.showAlert(`Team "${data.team_name}" joined the game!`, 'success');
        
        // Update team count
        const teamCountEl = document.getElementById('team-count');
        if (teamCountEl) {
            teamCountEl.textContent = data.total_teams;
        }
    }

    handleQuestionDisplayed(data) {
        console.log('Question displayed to teams:', data);
        
        // Update current question indicator
        const currentQuestionEl = document.getElementById('current-question');
        if (currentQuestionEl) {
            currentQuestionEl.textContent = `${data.question_number}/${triviaApp.totalQuestions}`;
        }
        
        // Show host view of the question
        triviaApp.showQuestionHost(data.question, data.question_number);
    }
}

// Initialize host controller when page loads
const hostController = new HostController();

document.addEventListener('DOMContentLoaded', function() {
    hostController.init();
    
    // Override triviaApp message handler to include host-specific logic
    const originalHandleMessage = triviaApp.handleMessage.bind(triviaApp);
    triviaApp.handleMessage = function(message) {
        originalHandleMessage(message);
        hostController.handleHostMessage(message);
    };
});

// Export for global access
window.hostController = hostController;