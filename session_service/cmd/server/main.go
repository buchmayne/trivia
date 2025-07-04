package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

// Django API client
type DjangoClient struct {
	BaseURL string
	Client  *http.Client
}

func NewDjangoClient(baseURL string) *DjangoClient {
	return &DjangoClient{
		BaseURL: baseURL,
		Client:  &http.Client{},
	}
}

// Django API structs
type SessionCreateRequest struct {
	Game     int    `json:"game"`
	HostName string `json:"host_name"`
	MaxTeams int    `json:"max_teams"`
}

type SessionCreateResponse struct {
	SessionID   int    `json:"session_id"`
	SessionCode string `json:"session_code"`
	GameID      int    `json:"game_id"`
	GameName    string `json:"game_name"`
	MaxTeams    int    `json:"max_teams"`
}

type GameQuestionsResponse struct {
	Game      Game       `json:"game"`
	Questions []Question `json:"questions"`
}

type Game struct {
	ID             int    `json:"id"`
	Name           string `json:"name"`
	Description    string `json:"description"`
	TotalQuestions int    `json:"total_questions"`
}

type Question struct {
	ID               int      `json:"id"`
	Text             string   `json:"text"`
	QuestionNumber   int      `json:"question_number"`
	TotalPoints      int      `json:"total_points"`
	QuestionImageURL *string  `json:"question_image_url"`
	AnswerBank       *string  `json:"answer_bank"`
	QuestionType     string   `json:"question_type"`
	Answers          []Answer `json:"answers"`
}

type Answer struct {
	ID               int     `json:"id"`
	Text             string  `json:"text"`
	AnswerText       *string `json:"answer_text"`
	Points           int     `json:"points"`
	CorrectRank      *int    `json:"correct_rank"`
	DisplayOrder     *int    `json:"display_order"`
	QuestionImageURL *string `json:"question_image_url"`
	AnswerImageURL   *string `json:"answer_image_url"`
}

// Session management
type GameSession struct {
	ID              int              `json:"id"`
	Code            string           `json:"code"`
	GameID          int              `json:"game_id"`
	GameName        string           `json:"game_name"`
	Status          string           `json:"status"` // waiting, active, scoring, completed
	CurrentQuestion int              `json:"current_question"`
	Questions       []Question       `json:"questions"`
	Teams           map[string]*Team `json:"teams"`
	Host            *Client          `json:"-"`
	Clients         map[*Client]bool `json:"-"`
	mu              sync.RWMutex     `json:"-"`
	Broadcast       chan Message     `json:"-"`
	django          *DjangoClient    `json:"-"`
}

type Team struct {
	Name             string            `json:"name"`
	Score            int               `json:"score"`
	Client           *Client           `json:"-"`
	Answers          map[int]string    `json:"answers"`
	AnswerTimestamps map[int]time.Time `json:"-"`
}

type Client struct {
	ID      string
	Conn    *websocket.Conn
	Session *GameSession
	Send    chan Message
	IsHost  bool
}

type Message struct {
	Type string      `json:"type"`
	Data interface{} `json:"data"`
	From string      `json:"from,omitempty"`
}

// Global state
var (
	sessions = make(map[string]*GameSession)
	django   *DjangoClient
	mu       sync.RWMutex
)

func main() {
	fmt.Println("🎯 Trivia Session Service Starting...")

	// Initialize Django client
	django = NewDjangoClient("http://127.0.0.1:8000")

	// Setup routes
	r := mux.NewRouter()

	// API routes
	r.HandleFunc("/api/sessions", createSessionHandler).Methods("POST")
	r.HandleFunc("/api/sessions/{code}", getSessionHandler).Methods("GET")

	// WebSocket route
	r.HandleFunc("/ws/{code}", websocketHandler)

	// Test page
	r.HandleFunc("/", homeHandler)
	r.HandleFunc("/test/{code}", testPageHandler)

	port := ":8080"
	fmt.Printf("🚀 Trivia service running at http://localhost%s\n", port)
	fmt.Println("📡 Django API integration ready")
	fmt.Println("🌐 WebSocket coordination active")
	fmt.Println("\nAPI Endpoints:")
	fmt.Println("  POST /api/sessions - Create new session")
	fmt.Println("  GET  /api/sessions/{code} - Get session info")
	fmt.Println("  WS   /ws/{code} - WebSocket connection")
	fmt.Println("  GET  /test/{code} - Test page for session")

	log.Fatal(http.ListenAndServe(port, r))
}

// Django API integration
func (d *DjangoClient) CreateSession(req SessionCreateRequest) (*SessionCreateResponse, error) {
	url := d.BaseURL + "/quiz/api/sessions/create/"

	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := d.Client.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	var sessionResp SessionCreateResponse
	if err := json.NewDecoder(resp.Body).Decode(&sessionResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &sessionResp, nil
}

func (d *DjangoClient) GetGameQuestions(gameID int) (*GameQuestionsResponse, error) {
	url := fmt.Sprintf("%s/quiz/api/games/%d/questions/", d.BaseURL, gameID)

	resp, err := d.Client.Get(url)
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	var gameResp GameQuestionsResponse
	if err := json.NewDecoder(resp.Body).Decode(&gameResp); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &gameResp, nil
}

// HTTP handlers
func createSessionHandler(w http.ResponseWriter, r *http.Request) {
	var req SessionCreateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Create session in Django
	sessionResp, err := django.CreateSession(req)
	if err != nil {
		log.Printf("Failed to create Django session: %v", err)
		http.Error(w, "Failed to create session", http.StatusInternalServerError)
		return
	}

	// Get questions from Django
	gameData, err := django.GetGameQuestions(sessionResp.GameID)
	if err != nil {
		log.Printf("Failed to get questions: %v", err)
		http.Error(w, "Failed to get questions", http.StatusInternalServerError)
		return
	}

	// Create Go session
	session := &GameSession{
		ID:              sessionResp.SessionID,
		Code:            sessionResp.SessionCode,
		GameID:          sessionResp.GameID,
		GameName:        sessionResp.GameName,
		Status:          "waiting",
		CurrentQuestion: 0,
		Questions:       gameData.Questions,
		Teams:           make(map[string]*Team),
		Clients:         make(map[*Client]bool),
		Broadcast:       make(chan Message, 256),
		django:          django,
	}

	// Store session and start management goroutine
	mu.Lock()
	sessions[session.Code] = session
	mu.Unlock()

	go session.Run()

	fmt.Printf("✅ Created session %s for game '%s' (%d questions)\n",
		session.Code, session.GameName, len(session.Questions))

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"session_code": session.Code,
		"game_name":    session.GameName,
		"questions":    len(session.Questions),
		"status":       session.Status,
	})
}

func getSessionHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := vars["code"]

	mu.RLock()
	session, exists := sessions[code]
	mu.RUnlock()

	if !exists {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	session.mu.RLock()
	defer session.mu.RUnlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"code":             session.Code,
		"game_name":        session.GameName,
		"status":           session.Status,
		"current_question": session.CurrentQuestion,
		"total_questions":  len(session.Questions),
		"teams":            session.getTeamList(),
	})
}

func websocketHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := vars["code"]

	mu.RLock()
	session, exists := sessions[code]
	mu.RUnlock()

	if !exists {
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("Failed to upgrade connection: %v", err)
		return
	}

	clientType := r.URL.Query().Get("type") // "host" or "team"
	clientName := r.URL.Query().Get("name") // team name or host name

	client := &Client{
		ID:      clientName,
		Conn:    conn,
		Session: session,
		Send:    make(chan Message, 256),
		IsHost:  clientType == "host",
	}

	// Register client with session
	session.mu.Lock()
	session.Clients[client] = true
	if client.IsHost {
		session.Host = client
		fmt.Printf("🎪 Host '%s' connected to session %s\n", clientName, code)
	} else {
		fmt.Printf("👥 Client '%s' connected to session %s\n", clientName, code)
	}
	session.mu.Unlock()

	// Send welcome message
	welcome := Message{
		Type: "connected",
		Data: map[string]interface{}{
			"session_code":     session.Code,
			"game_name":        session.GameName,
			"status":           session.Status,
			"current_question": session.CurrentQuestion,
			"total_questions":  len(session.Questions),
			"is_host":          client.IsHost,
		},
	}
	client.Send <- welcome

	// Start client goroutines
	go client.writePump()
	go client.readPump()
}

// Session management
func (s *GameSession) Run() {
	for {
		select {
		case message := <-s.Broadcast:
			s.handleMessage(message)
		}
	}
}

func (s *GameSession) handleMessage(msg Message) {
	s.mu.Lock()
	defer s.mu.Unlock()

	fmt.Printf("🎮 Session %s: %s message from %s\n", s.Code, msg.Type, msg.From)

	switch msg.Type {
	case "join_team":
		s.handleTeamJoin(msg)
	case "host_command":
		s.handleHostCommand(msg)
	case "submit_answer":
		s.handleAnswerSubmission(msg)
	}
}

func (s *GameSession) handleTeamJoin(msg Message) {
	data := msg.Data.(map[string]interface{})
	teamName := data["team_name"].(string)

	if _, exists := s.Teams[teamName]; exists {
		return // Team already exists
	}

	team := &Team{
		Name:             teamName,
		Score:            0,
		Answers:          make(map[int]string),
		AnswerTimestamps: make(map[int]time.Time),
	}

	s.Teams[teamName] = team

	fmt.Printf("✅ Team '%s' joined session %s (%d teams total)\n",
		teamName, s.Code, len(s.Teams))

	s.broadcastToAll(Message{
		Type: "team_joined",
		Data: map[string]interface{}{
			"team_name":   teamName,
			"total_teams": len(s.Teams),
			"teams":       s.getTeamList(),
		},
	})
}

func (s *GameSession) handleHostCommand(msg Message) {
	data := msg.Data.(map[string]interface{})
	command := data["command"].(string)

	switch command {
	case "start_game":
		s.Status = "active"
		fmt.Printf("🚀 Game started in session %s\n", s.Code)

		s.broadcastToAll(Message{
			Type: "game_started",
			Data: map[string]interface{}{
				"message": "Game is starting! Get ready!",
				"status":  s.Status,
			},
		})

	case "show_question":
		questionNum := int(data["question_number"].(float64))
		s.showQuestion(questionNum)

	case "next_question":
		s.nextQuestion()

	case "start_scoring":
		s.startScoringPhase()

	case "score_question":
		questionNum := int(data["question_number"].(float64))
		scores := data["scores"].(map[string]interface{})
		s.scoreQuestion(questionNum, scores)

	case "finish_scoring":
		s.finishScoringPhase()
	}
}

func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func (s *GameSession) showQuestion(questionNum int) {
	if questionNum <= 0 || questionNum > len(s.Questions) {
		return
	}

	s.CurrentQuestion = questionNum
	question := s.Questions[questionNum-1]

	fmt.Printf("❓ Showing Q%d in session %s: %s\n",
		questionNum, s.Code, question.Text[:min(50, len(question.Text))])

	// Send FULL question to host (including all answer options and correct answers)
	s.sendToHost(Message{
		Type: "question_displayed_host",
		Data: map[string]interface{}{
			"question":        question, // Full question with all answers
			"question_number": questionNum,
			"submissions":     s.getSubmissionsForQuestion(questionNum),
		},
	})

	// Send question to teams (without correct answers)
	teamQuestion := s.prepareQuestionForTeams(question)
	s.broadcastToTeams(Message{
		Type: "question_display",
		Data: map[string]interface{}{
			"question":        teamQuestion,
			"question_number": questionNum,
			"total_questions": len(s.Questions),
		},
	})
}

func (s *GameSession) prepareQuestionForTeams(question Question) Question {
	// Teams see the question and answer options but not correct answers
	teamQuestion := question

	// Create sanitized answers for teams
	teamAnswers := make([]Answer, len(question.Answers))
	for i, answer := range question.Answers {
		teamAnswers[i] = Answer{
			ID:               answer.ID,
			Text:             answer.Text, // Teams see the option text
			QuestionImageURL: answer.QuestionImageURL,
			DisplayOrder:     answer.DisplayOrder,
			// Don't include: answer_text, correct_rank, points
		}
	}
	teamQuestion.Answers = teamAnswers

	return teamQuestion
}

func (s *GameSession) nextQuestion() {
	if s.CurrentQuestion < len(s.Questions) {
		s.showQuestion(s.CurrentQuestion + 1)
	} else {
		// All questions shown - ready for scoring
		s.broadcastToAll(Message{
			Type: "round_complete",
			Data: map[string]interface{}{
				"message":         "Round complete! Ready for scoring.",
				"total_questions": len(s.Questions),
			},
		})
	}
}

func (s *GameSession) startScoringPhase() {
	s.Status = "scoring"
	fmt.Printf("📊 Starting scoring phase for session %s\n", s.Code)

	s.sendToHost(Message{
		Type: "scoring_started",
		Data: map[string]interface{}{
			"message":            "Scoring phase started",
			"questions_to_score": s.getQuestionsForScoring(),
		},
	})

	s.broadcastToTeams(Message{
		Type: "scoring_phase",
		Data: map[string]interface{}{
			"message": "Round complete! Host is scoring answers...",
		},
	})
}

func (s *GameSession) scoreQuestion(questionNum int, scores map[string]interface{}) {
	fmt.Printf("📝 Scoring Q%d in session %s\n", questionNum, s.Code)

	// Update team scores
	for teamName, scoreInterface := range scores {
		if team, exists := s.Teams[teamName]; exists {
			points := int(scoreInterface.(float64))
			team.Score += points
		}
	}

	s.sendToHost(Message{
		Type: "question_scored",
		Data: map[string]interface{}{
			"question_number": questionNum,
			"scores":          scores,
			"leaderboard":     s.getLeaderboard(),
		},
	})
}

func (s *GameSession) finishScoringPhase() {
	s.Status = "active"
	fmt.Printf("✅ Finished scoring phase for session %s\n", s.Code)

	s.broadcastToAll(Message{
		Type: "scoring_complete",
		Data: map[string]interface{}{
			"message":     "Scoring complete!",
			"leaderboard": s.getLeaderboard(),
			"status":      s.Status,
		},
	})
}

func (s *GameSession) handleAnswerSubmission(msg Message) {
	data := msg.Data.(map[string]interface{})
	teamName := data["team_name"].(string)
	answer := data["answer"].(string)
	questionNum := int(data["question_number"].(float64))

	team, exists := s.Teams[teamName]
	if !exists {
		return
	}

	team.Answers[questionNum] = answer
	team.AnswerTimestamps[questionNum] = time.Now()

	fmt.Printf("📝 %s submitted Q%d answer: %s\n", teamName, questionNum, answer)

	s.sendToHost(Message{
		Type: "answer_submitted",
		Data: map[string]interface{}{
			"team_name":       teamName,
			"question_number": questionNum,
			"answer":          answer,
			"submissions":     s.getSubmissionsForQuestion(questionNum),
		},
	})
}

// Helper functions
func (s *GameSession) getTeamList() []map[string]interface{} {
	teams := make([]map[string]interface{}, 0, len(s.Teams))
	for _, team := range s.Teams {
		teams = append(teams, map[string]interface{}{
			"name":  team.Name,
			"score": team.Score,
		})
	}
	return teams
}

func (s *GameSession) getSubmissionsForQuestion(questionNum int) []map[string]interface{} {
	submissions := make([]map[string]interface{}, 0)
	for _, team := range s.Teams {
		if answer, exists := team.Answers[questionNum]; exists {
			submissions = append(submissions, map[string]interface{}{
				"team":   team.Name,
				"answer": answer,
			})
		}
	}
	return submissions
}

func (s *GameSession) getQuestionsForScoring() []map[string]interface{} {
	questionsWithAnswers := make([]map[string]interface{}, 0)

	for i := 1; i <= s.CurrentQuestion; i++ {
		question := s.Questions[i-1]
		submissions := s.getSubmissionsForQuestion(i)

		questionsWithAnswers = append(questionsWithAnswers, map[string]interface{}{
			"question":     question,
			"question_num": i,
			"submissions":  submissions,
		})
	}

	return questionsWithAnswers
}

func (s *GameSession) getLeaderboard() []map[string]interface{} {
	leaderboard := make([]map[string]interface{}, 0, len(s.Teams))
	for _, team := range s.Teams {
		leaderboard = append(leaderboard, map[string]interface{}{
			"name":  team.Name,
			"score": team.Score,
		})
	}
	return leaderboard
}

func (s *GameSession) broadcastToAll(msg Message) {
	for client := range s.Clients {
		select {
		case client.Send <- msg:
		default:
			close(client.Send)
			delete(s.Clients, client)
		}
	}
}

func (s *GameSession) broadcastToTeams(msg Message) {
	for client := range s.Clients {
		if !client.IsHost {
			select {
			case client.Send <- msg:
			default:
			}
		}
	}
}

func (s *GameSession) sendToHost(msg Message) {
	if s.Host != nil {
		select {
		case s.Host.Send <- msg:
		default:
		}
	}
}

// Client WebSocket handlers
func (c *Client) readPump() {
	defer func() {
		c.Session.mu.Lock()
		delete(c.Session.Clients, c)
		c.Session.mu.Unlock()
		c.Conn.Close()
	}()

	for {
		var msg Message
		err := c.Conn.ReadJSON(&msg)
		if err != nil {
			break
		}

		msg.From = c.ID
		c.Session.Broadcast <- msg
	}
}

func (c *Client) writePump() {
	defer c.Conn.Close()

	for {
		select {
		case message, ok := <-c.Send:
			if !ok {
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.Conn.WriteJSON(message); err != nil {
				return
			}
		}
	}
}

// Test pages
func homeHandler(w http.ResponseWriter, r *http.Request) {
	html := `<!DOCTYPE html>
<html><head><title>Trivia Service</title></head>
<body>
<h1>🎯 Trivia Session Service</h1>
<h2>Create New Session</h2>
<form id="createForm">
<label>Game ID: <input type="number" id="gameId" value="1"></label><br>
<label>Host Name: <input type="text" id="hostName" value="Test Host"></label><br>
<label>Max Teams: <input type="number" id="maxTeams" value="10"></label><br>
<button type="submit">Create Session</button>
</form>
<div id="result"></div>

<script>
document.getElementById('createForm').onsubmit = async (e) => {
  e.preventDefault();
  const data = {
    game: parseInt(document.getElementById('gameId').value),
    host_name: document.getElementById('hostName').value,
    max_teams: parseInt(document.getElementById('maxTeams').value)
  };
  
  const resp = await fetch('/api/sessions', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(data)
  });
  
  const result = await resp.json();
  document.getElementById('result').innerHTML = 
    '<h3>Session Created!</h3>' +
    '<p>Code: <strong>' + result.session_code + '</strong></p>' +
    '<p>Game: ' + result.game_name + '</p>' +
    '<p><a href="/test/' + result.session_code + '">Test Page</a></p>';
};
</script>
</body></html>`

	w.Header().Set("Content-Type", "text/html")
	fmt.Fprint(w, html)
}

func testPageHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := vars["code"]

	html := fmt.Sprintf(`<!DOCTYPE html>
<html><head><title>Test Session %s</title>
<style>
body { font-family: Arial, sans-serif; margin: 20px; }
.section { border: 1px solid #ccc; margin: 10px 0; padding: 15px; border-radius: 5px; }
.host-controls { background-color: #fff3cd; }
.team-controls { background-color: #d4edda; }
#messages { height: 300px; overflow-y: scroll; border: 1px solid #ddd; padding: 10px; margin: 10px 0; }
.message { margin: 5px 0; padding: 5px; border-radius: 3px; }
.team-joined { background-color: #d1ecf1; }
.game-started { background-color: #d4edda; }
.question-display { background-color: #fff3cd; }
button { padding: 8px 15px; margin: 5px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
button:hover { background-color: #0056b3; }
button:disabled { background-color: #ccc; cursor: not-allowed; }
input { padding: 5px; margin: 5px; border: 1px solid #ddd; border-radius: 3px; }
</style></head>
<body>
<h1>🎮 Session: %s</h1>

<div class="section host-controls">
<h3>🎪 Host Controls</h3>
<button onclick="connectHost()" id="hostBtn">Connect as Host</button>
<div id="hostControls" style="display:none;">
  <div id="gameControls">
    <button onclick="startGame()" id="startBtn">Start Game</button>
    <button onclick="showQuestion()" id="showQuestionBtn" disabled>Show Question 1</button>
    <button onclick="nextQuestion()" id="nextBtn" disabled>Next Question</button>
  </div>
  <div id="scoringControls" style="display:none;">
    <button onclick="startScoring()" id="startScoringBtn">Start Scoring</button>
    <div id="scoringInterface" style="display:none;">
      <p>Score each question for each team:</p>
      <div id="scoringQuestions"></div>
      <button onclick="finishScoring()" id="finishScoringBtn">Finish Scoring</button>
    </div>
  </div>
</div>
</div>

<div class="section team-controls">
<h3>👥 Team Controls</h3>
<input type="text" id="teamName" placeholder="Team name" value="Test Team">
<button onclick="connectTeam()" id="teamBtn">Connect as Team</button>
<div id="teamControls" style="display:none;">
  <input type="text" id="answerInput" placeholder="Your answer" disabled>
  <button onclick="submitAnswer()" id="submitBtn" disabled>Submit Answer</button>
</div>
</div>

<div class="section">
<h3>📊 Session Status</h3>
<div id="status">Not connected</div>
<div><strong>Teams:</strong> <span id="teamList">None</span></div>
<div><strong>Current Question:</strong> <span id="currentQuestion">None</span></div>
</div>

<div class="section">
<h3>📝 Messages</h3>
<div id="messages"></div>
</div>

<script>
let ws = null;
let isHost = false;
let currentQuestionNum = 0;
let totalQuestions = 0;

function connectHost() {
  ws = new WebSocket('ws://localhost:8080/ws/%s?type=host&name=TestHost');
  isHost = true;
  setupWebSocket('Host');
  document.getElementById('hostBtn').disabled = true;
  document.getElementById('hostControls').style.display = 'block';
}

function connectTeam() {
  const teamName = document.getElementById('teamName').value;
  if (!teamName.trim()) {
    alert('Please enter a team name');
    return;
  }
  ws = new WebSocket('ws://localhost:8080/ws/%s?type=team&name=' + encodeURIComponent(teamName));
  isHost = false;
  setupWebSocket('Team: ' + teamName);
  document.getElementById('teamBtn').disabled = true;
  document.getElementById('teamControls').style.display = 'block';
  
  // Send join team message
  setTimeout(() => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({
        type: 'join_team',
        data: { team_name: teamName }
      }));
    }
  }, 100);
}

function setupWebSocket(label) {
  ws.onopen = () => {
    document.getElementById('status').textContent = '✅ Connected as ' + label;
    addMessage('system', 'Connected as ' + label);
  };
  
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };
  
  ws.onclose = () => {
    document.getElementById('status').textContent = '❌ Disconnected';
    addMessage('system', 'Disconnected');
  };
}

function handleMessage(msg) {
  switch(msg.type) {
    case 'connected':
      totalQuestions = msg.data.total_questions;
      updateGameInfo(msg.data);
      break;
      
    case 'team_joined':
      addMessage('team-joined', '🎉 Team "' + msg.data.team_name + '" joined! (' + msg.data.total_teams + ' teams total)');
      updateTeamList(msg.data.teams);
      break;
      
    case 'game_started':
      addMessage('game-started', '🚀 ' + msg.data.message);
      if (isHost) {
        document.getElementById('showQuestionBtn').disabled = false;
      }
      break;
      
    case 'question_display':
      currentQuestionNum = msg.data.question_number;
      const question = msg.data.question;
      
      // Display question for teams
      let questionDisplay = '❓ Q' + msg.data.question_number + ': ' + question.text;
      if (question.answer_bank) {
        questionDisplay += '\\nAnswer Bank: ' + question.answer_bank;
      }
      if (question.answers && question.answers.length > 0) {
        questionDisplay += '\\nOptions: ';
        question.answers.forEach((answer, idx) => {
          questionDisplay += '\\n' + (idx + 1) + '. ' + answer.text;
        });
      }
      
      addMessage('question-display', questionDisplay);
      document.getElementById('currentQuestion').textContent = 'Question ' + msg.data.question_number + ' of ' + msg.data.total_questions;
      
      if (!isHost) {
        document.getElementById('answerInput').disabled = false;
        document.getElementById('submitBtn').disabled = false;
      }
      break;
      
    case 'question_displayed_host':
      if (isHost) {
        currentQuestionNum = msg.data.question_number;
        const hostQuestion = msg.data.question;
        
        // Display FULL question for host (including correct answers)
        let hostDisplay = '🎪 HOST VIEW - Q' + msg.data.question_number + ': ' + hostQuestion.text;
        if (hostQuestion.answer_bank) {
          hostDisplay += '\\nAnswer Bank: ' + hostQuestion.answer_bank;
        }
        if (hostQuestion.answers && hostQuestion.answers.length > 0) {
          hostDisplay += '\\nAll Answer Options:';
          hostQuestion.answers.forEach((answer, idx) => {
            hostDisplay += '\\n' + (idx + 1) + '. ' + answer.text;
            if (answer.answer_text) {
              hostDisplay += ' → ' + answer.answer_text;
            }
            if (answer.correct_rank) {
              hostDisplay += ' (Rank: ' + answer.correct_rank + ')';
            }
            if (answer.points) {
              hostDisplay += ' [' + answer.points + ' pts]';
            }
          });
        }
        
        addMessage('question-display', hostDisplay);
        document.getElementById('nextBtn').disabled = false;
      }
      break;
      
    case 'answer_submitted':
      if (isHost) {
        addMessage('system', '📝 ' + msg.data.team_name + ' submitted: "' + msg.data.answer + '"');
      }
      break;
      
    case 'round_complete':
      addMessage('system', '🏁 Round complete! All questions shown.');
      if (isHost) {
        document.getElementById('nextBtn').disabled = true;
        document.getElementById('showQuestionBtn').disabled = true;
        document.getElementById('scoringControls').style.display = 'block';
      }
      break;
      
    case 'scoring_started':
      addMessage('system', '📊 Scoring phase started');
      if (isHost) {
        document.getElementById('scoringInterface').style.display = 'block';
        displayScoringInterface(msg.data.questions_to_score);
      }
      break;
      
    case 'scoring_phase':
      addMessage('system', '⏳ ' + msg.data.message);
      break;
      
    case 'scoring_complete':
      addMessage('system', '✅ Scoring complete!');
      updateTeamList(msg.data.leaderboard);
      break;
      
    case 'game_completed':
      addMessage('game-started', '🏁 Game completed!');
      break;
      
    default:
      addMessage('system', msg.type + ': ' + JSON.stringify(msg.data));
  }
}

function addMessage(type, text) {
  const div = document.createElement('div');
  div.className = 'message ' + type;
  div.style.whiteSpace = 'pre-line'; // This makes \\n work in the display
  div.textContent = new Date().toLocaleTimeString() + ' - ' + text;
  document.getElementById('messages').appendChild(div);
  document.getElementById('messages').scrollTop = document.getElementById('messages').scrollHeight;
}

function updateTeamList(teams) {
  if (teams && teams.length > 0) {
    const teamNames = teams.map(team => team.name + ' (' + team.score + ')').join(', ');
    document.getElementById('teamList').textContent = teamNames;
  } else {
    document.getElementById('teamList').textContent = 'None';
  }
}

function updateGameInfo(data) {
  document.getElementById('currentQuestion').textContent = 
    data.current_question > 0 ? 'Question ' + data.current_question + ' of ' + data.total_questions : 'Not started';
}

// Host controls
function startGame() {
  if (ws && isHost) {
    ws.send(JSON.stringify({
      type: 'host_command',
      data: { command: 'start_game' }
    }));
    document.getElementById('startBtn').disabled = true;
  }
}

function showQuestion() {
  if (ws && isHost) {
    const questionNum = currentQuestionNum + 1;
    ws.send(JSON.stringify({
      type: 'host_command',
      data: { command: 'show_question', question_number: questionNum }
    }));
    document.getElementById('showQuestionBtn').textContent = 'Show Question ' + (questionNum + 1);
    document.getElementById('showQuestionBtn').disabled = true;
  }
}

function nextQuestion() {
  if (ws && isHost) {
    ws.send(JSON.stringify({
      type: 'host_command',
      data: { command: 'next_question' }
    }));
    
    if (currentQuestionNum < totalQuestions) {
      document.getElementById('showQuestionBtn').disabled = false;
      document.getElementById('showQuestionBtn').textContent = 'Show Question ' + (currentQuestionNum + 1);
    }
  }
}

function startScoring() {
  if (ws && isHost) {
    ws.send(JSON.stringify({
      type: 'host_command',
      data: { command: 'start_scoring' }
    }));
    document.getElementById('startScoringBtn').disabled = true;
  }
}

function finishScoring() {
  if (ws && isHost) {
    ws.send(JSON.stringify({
      type: 'host_command',
      data: { command: 'finish_scoring' }
    }));
  }
}

function displayScoringInterface(questionsToScore) {
  const container = document.getElementById('scoringQuestions');
  container.innerHTML = '';
  
  questionsToScore.forEach(questionData => {
    const div = document.createElement('div');
    div.innerHTML = '<h4>Q' + questionData.question_num + ': ' + questionData.question.text + '</h4>';
    
    questionData.submissions.forEach(submission => {
      div.innerHTML += '<p><strong>' + submission.team + ':</strong> "' + submission.answer + '" ' +
        '<input type="number" min="0" max="' + questionData.question.total_points + '" ' +
        'placeholder="Points" id="score_' + questionData.question_num + '_' + submission.team + '"></p>';
    });
    
    container.appendChild(div);
  });
}

// Team controls
function submitAnswer() {
  const answer = document.getElementById('answerInput').value.trim();
  if (!answer) {
    alert('Please enter an answer');
    return;
  }
  
  if (ws && !isHost) {
    ws.send(JSON.stringify({
      type: 'submit_answer',
      data: { 
        team_name: document.getElementById('teamName').value,
        answer: answer,
        question_number: currentQuestionNum
      }
    }));
    
    document.getElementById('answerInput').value = '';
    document.getElementById('submitBtn').disabled = true;
    addMessage('system', '✅ Answer submitted: "' + answer + '"');
  }
}

// Enable Enter key for answer submission
document.addEventListener('DOMContentLoaded', function() {
  document.getElementById('answerInput').addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
      submitAnswer();
    }
  });
});
</script>
</body></html>`, code, code, code, code)

	w.Header().Set("Content-Type", "text/html")
	fmt.Fprint(w, html)

}
