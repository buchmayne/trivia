// Just the essential WebSocket connection code
class SessionConnection {
    constructor(sessionCode, isHost = false) {
        this.sessionCode = sessionCode;
        this.isHost = isHost;
        this.socket = null;
        this.connect();
    }
    
    connect() {
        this.socket = new WebSocket(`ws://localhost:8080/session/${this.sessionCode}`);
        this.socket.onmessage = (event) => this.handleMessage(JSON.parse(event.data));
    }
    
    handleMessage(data) {
        switch(data.type) {
            case 'team_joined':
                this.updateTeamsList(data.teams);
                break;
            case 'game_started':
                this.showQuestion(data.question);
                break;
            case 'scores_updated':
                this.updateScores(data.scores);
                break;
        }
    }
    
    // Basic DOM manipulation methods
    updateTeamsList(teams) {
        const container = document.getElementById('teams-list');
        container.innerHTML = teams.map(team => 
            `<div class="team-item">${team.name}</div>`
        ).join('');
    }
    
    showQuestion(question) {
        window.location.href = `/sessions/live/${this.sessionCode}/`;
    }
}

// Usage in templates
window.SessionConnection = SessionConnection;