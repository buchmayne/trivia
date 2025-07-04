package main

import (
	"embed"
	"encoding/json"
	"fmt"
	"html/template"
	"io/fs"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
)

//go:embed templates/* static/*
var embeddedFiles embed.FS

// Template cache
var templates *template.Template

// Types (keeping your existing types)
type Question struct {
	ID               int      `json:"id"`
	Text             string   `json:"text"`
	QuestionImageURL string   `json:"question_image_url"`
	Answers          []Answer `json:"answers"`
	Points           int      `json:"points"`
	QuestionNumber   int      `json:"question_number"`
}

type Answer struct {
	ID               int    `json:"id"`
	Text             string `json:"text"`
	AnswerText       string `json:"answer_text"`
	QuestionImageURL string `json:"question_image_url"`
	DisplayOrder     int    `json:"display_order"`
	CorrectRank      int    `json:"correct_rank"`
	Points           int    `json:"points"`
}

type GameSession struct {
	ID              int              `json:"id"`
	Code            string           `json:"code"`
	GameID          int              `json:"game_id"`
	GameName        string           `json:"game_name"`
	Status          string           `json:"status"`
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
	upgrader = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
)

// Template data structures
type PageData struct {
	Title       string
	SessionCode string
	GameName    string
	Error       string
	Success     string
}

type HostData struct {
	PageData
	Session *GameSession
}

type TeamData struct {
	PageData
	TeamName string
}

func init() {
	// Parse all templates with error handling
	var err error
	templates = template.New("")

	// Check if templates directory exists
	if _, err := fs.Stat(embeddedFiles, "templates"); err != nil {
		log.Println("Warning: templates directory not found in embedded files")
		return
	}

	// Parse base template
	templates, err = templates.ParseFS(embeddedFiles, "templates/base.html")
	if err != nil {
		log.Printf("Warning: Failed to parse base template: %v", err)
		templates = template.Must(template.New("").Parse(fallbackTemplate))
		return
	}

	// Parse all page templates
	templates, err = templates.ParseFS(embeddedFiles, "templates/*.html")
	if err != nil {
		log.Printf("Warning: Failed to parse templates: %v", err)
		templates = template.Must(template.New("").Parse(fallbackTemplate))
	}
}

// Fallback template for when embedded files are missing
const fallbackTemplate = `<!DOCTYPE html>
<html><head><title>{{.Title}}</title></head>
<body>
<h1>Trivia Service</h1>
<p>Templates are loading. Please ensure all template files are in place.</p>
<p>Error: {{.Error}}</p>
</body></html>`

func renderTemplate(w http.ResponseWriter, tmpl string, data interface{}) {
	if templates == nil {
		// Fallback rendering
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprint(w, `<!DOCTYPE html><html><head><title>Trivia Service</title></head>
<body><h1>Trivia Service</h1><p>Service is starting up. Templates not yet loaded.</p></body></html>`)
		return
	}

	err := templates.ExecuteTemplate(w, tmpl, data)
	if err != nil {
		log.Printf("Template error: %v", err)
		// Fallback rendering
		w.Header().Set("Content-Type", "text/html")
		fmt.Fprintf(w, `<!DOCTYPE html><html><head><title>Error</title></head>
<body><h1>Template Error</h1><p>%v</p></body></html>`, err)
	}
}

// Handlers
func homeHandler(w http.ResponseWriter, r *http.Request) {
	data := PageData{
		Title: "Trivia Session Service",
	}
	renderTemplate(w, "home.html", data)
}

func hostPageHandler(w http.ResponseWriter, r *http.Request) {
	data := HostData{
		PageData: PageData{
			Title: "Host Dashboard",
		},
	}
	renderTemplate(w, "host.html", data)
}

func teamJoinHandler(w http.ResponseWriter, r *http.Request) {
	data := TeamData{
		PageData: PageData{
			Title: "Join Game",
		},
	}
	renderTemplate(w, "team_join.html", data)
}

func sessionPageHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := vars["code"]

	mu.RLock()
	session, exists := sessions[code]
	mu.RUnlock()

	if !exists {
		data := PageData{
			Title: "Session Not Found",
			Error: "Session code not found",
		}
		renderTemplate(w, "error.html", data)
		return
	}

	clientType := r.URL.Query().Get("type")

	if clientType == "host" {
		data := HostData{
			PageData: PageData{
				Title:       "Host Dashboard - " + session.GameName,
				SessionCode: session.Code,
				GameName:    session.GameName,
			},
			Session: session,
		}
		renderTemplate(w, "host_session.html", data)
	} else {
		teamName := r.URL.Query().Get("name")
		data := TeamData{
			PageData: PageData{
				Title:       "Playing " + session.GameName,
				SessionCode: session.Code,
				GameName:    session.GameName,
			},
			TeamName: teamName,
		}
		renderTemplate(w, "team_session.html", data)
	}
}

// API Handlers (keeping your existing logic)
func createSessionHandler(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Game     int    `json:"game"`
		HostName string `json:"host_name"`
		MaxTeams int    `json:"max_teams"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid JSON", http.StatusBadRequest)
		return
	}

	// Generate session code
	code := generateSessionCode()

	// Get game data from Django
	gameData, err := django.GetGameQuestions(req.Game)
	if err != nil {
		log.Printf("Failed to get game data: %v", err)
		http.Error(w, "Failed to create session", http.StatusInternalServerError)
		return
	}

	// Create session
	session := &GameSession{
		Code:            code,
		GameID:          req.Game,
		GameName:        gameData.Game.Name,
		Status:          "waiting",
		CurrentQuestion: 0,
		Questions:       gameData.Questions,
		Teams:           make(map[string]*Team),
		Clients:         make(map[*Client]bool),
		Broadcast:       make(chan Message),
		django:          django,
	}

	// Store session
	mu.Lock()
	sessions[code] = session
	mu.Unlock()

	// Start session goroutine
	go session.Run()

	fmt.Printf("🎯 Created session %s for game '%s' (host: %s)\n",
		code, session.GameName, req.HostName)

	// Create session in Django
	_, err = django.CreateSession(req.Game, req.HostName, req.MaxTeams, code)
	if err != nil {
		log.Printf("Failed to create Django session: %v", err)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"session_code": code,
		"game_name":    session.GameName,
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

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"session_code":     session.Code,
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

	clientType := r.URL.Query().Get("type")
	clientName := r.URL.Query().Get("name")

	client := &Client{
		ID:      clientName,
		Conn:    conn,
		Session: session,
		Send:    make(chan Message, 256),
		IsHost:  clientType == "host",
	}

	session.mu.Lock()
	session.Clients[client] = true
	if client.IsHost {
		session.Host = client
		fmt.Printf("🎪 Host '%s' connected to session %s\n", clientName, code)
	} else {
		fmt.Printf("👥 Client '%s' connected to session %s\n", clientName, code)
	}
	session.mu.Unlock()

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

	go client.writePump()
	go client.readPump()
}

// Static file handler
func staticHandler(w http.ResponseWriter, r *http.Request) {
	// The path should already have /static/ stripped by http.StripPrefix
	path := r.URL.Path

	// Remove leading slash if present
	if strings.HasPrefix(path, "/") {
		path = path[1:]
	}

	fmt.Printf("🔍 Serving static file: %s\n", path)

	data, err := embeddedFiles.ReadFile("static/" + path)
	if err != nil {
		fmt.Printf("❌ Static file not found: static/%s - %v\n", path, err)
		http.NotFound(w, r)
		return
	}

	// Set content type
	if strings.HasSuffix(path, ".css") {
		w.Header().Set("Content-Type", "text/css")
	} else if strings.HasSuffix(path, ".js") {
		w.Header().Set("Content-Type", "application/javascript")
	}

	fmt.Printf("✅ Served static file: %s (%d bytes)\n", path, len(data))
	w.Write(data)
}

// Utility functions (keeping your existing ones)
func generateSessionCode() string {
	chars := "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	code := make([]byte, 6)
	for i := range code {
		code[i] = chars[time.Now().UnixNano()%int64(len(chars))]
		time.Sleep(time.Nanosecond)
	}
	return string(code)
}

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

// Session methods (keeping your existing logic)
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
		return
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
	}
}

func (s *GameSession) handleAnswerSubmission(msg Message) {
	// Implementation for answer submission
	data := msg.Data.(map[string]interface{})
	teamName := msg.From
	questionNum := int(data["question_number"].(float64))
	answer := data["answer"].(string)

	if team, exists := s.Teams[teamName]; exists {
		team.Answers[questionNum] = answer
		team.AnswerTimestamps[questionNum] = time.Now()

		fmt.Printf("📝 Team '%s' submitted answer for Q%d\n", teamName, questionNum)

		// Notify host of submission
		s.sendToHost(Message{
			Type: "answer_submitted",
			Data: map[string]interface{}{
				"team_name":       teamName,
				"question_number": questionNum,
				"answer":          answer,
				"timestamp":       team.AnswerTimestamps[questionNum],
			},
		})
	}
}

func (s *GameSession) showQuestion(questionNum int) {
	if questionNum <= 0 || questionNum > len(s.Questions) {
		return
	}

	s.CurrentQuestion = questionNum
	question := s.Questions[questionNum-1]

	fmt.Printf("❓ Showing Q%d in session %s\n", questionNum, s.Code)

	// Send to host
	s.sendToHost(Message{
		Type: "question_displayed_host",
		Data: map[string]interface{}{
			"question":        question,
			"question_number": questionNum,
		},
	})

	// Send to teams (without correct answers)
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
	teamQuestion := question
	teamAnswers := make([]Answer, len(question.Answers))
	for i, answer := range question.Answers {
		teamAnswers[i] = Answer{
			ID:               answer.ID,
			Text:             answer.Text,
			QuestionImageURL: answer.QuestionImageURL,
			DisplayOrder:     answer.DisplayOrder,
		}
	}
	teamQuestion.Answers = teamAnswers
	return teamQuestion
}

func (s *GameSession) nextQuestion() {
	if s.CurrentQuestion < len(s.Questions) {
		s.showQuestion(s.CurrentQuestion + 1)
	}
}

func (s *GameSession) broadcastToAll(msg Message) {
	for client := range s.Clients {
		select {
		case client.Send <- msg:
		default:
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

// Client methods
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

func main() {
	fmt.Println("🎯 Trivia Session Service Starting...")

	django = NewDjangoClient("http://127.0.0.1:8000")

	r := mux.NewRouter()

	// Static files MUST come first to avoid conflicts
	r.PathPrefix("/static/").Handler(http.StripPrefix("/static/", http.HandlerFunc(staticHandler)))

	// API routes
	r.HandleFunc("/api/sessions", createSessionHandler).Methods("POST")
	r.HandleFunc("/api/sessions/{code}", getSessionHandler).Methods("GET")

	// WebSocket route
	r.HandleFunc("/ws/{code}", websocketHandler)

	// Page routes
	r.HandleFunc("/", homeHandler)
	r.HandleFunc("/host", hostPageHandler)
	r.HandleFunc("/join", teamJoinHandler)
	r.HandleFunc("/session/{code}", sessionPageHandler)

	port := ":8080"
	fmt.Printf("🚀 Trivia service running at http://localhost%s\n", port)
	log.Fatal(http.ListenAndServe(port, r))
}
