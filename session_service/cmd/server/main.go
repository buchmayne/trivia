package main

import (
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strings"
	"sync"
	"text/template"
	"time"

	"session_service/internal/types"
	"session_service/pkg/django"
	"session_service/web"

	"github.com/gorilla/mux"
	"github.com/gorilla/websocket"
)

// Global state
var (
	sessions     = make(map[string]*types.GameSession)
	djangoClient *django.Client
	mu           sync.RWMutex
	upgrader     = websocket.Upgrader{
		CheckOrigin: func(r *http.Request) bool { return true },
	}
)

// Render template using the web package
func renderTemplate(w http.ResponseWriter, tmpl string, data interface{}) {
	log.Printf("🎨 Rendering template: %s", tmpl)

	w.Header().Set("Content-Type", "text/html; charset=utf-8")

	// Create a new template set with just base.html and the specific page template
	pageTemplate := template.New("page")

	// Parse base template first
	pageTemplate, err := pageTemplate.ParseFS(web.Assets, "templates/base.html")
	if err != nil {
		log.Printf("❌ Error parsing base template: %v", err)
		http.Error(w, "Template error", http.StatusInternalServerError)
		return
	}

	// Parse the specific page template
	pageTemplate, err = pageTemplate.ParseFS(web.Assets, "templates/"+tmpl)
	if err != nil {
		log.Printf("❌ Error parsing page template %s: %v", tmpl, err)
		http.Error(w, "Template error", http.StatusInternalServerError)
		return
	}

	// Execute base.html which will use the content from the specific page
	err = pageTemplate.ExecuteTemplate(w, "base.html", data)
	if err != nil {
		log.Printf("❌ Template execution error: %v", err)
		http.Error(w, "Template error", http.StatusInternalServerError)
		return
	}

	log.Printf("✅ Template rendered successfully")
}

// Static file handler using the web package
func staticHandler(w http.ResponseWriter, r *http.Request) {
	path := strings.TrimPrefix(r.URL.Path, "/static/")

	staticFS := web.GetStaticFS()
	if staticFS == nil {
		http.NotFound(w, r)
		return
	}

	data, err := staticFS.Open(path)
	if err != nil {
		fmt.Printf("❌ Static file not found: %s - %v\n", path, err)
		http.NotFound(w, r)
		return
	}
	defer data.Close()

	// Set content type
	if strings.HasSuffix(path, ".css") {
		w.Header().Set("Content-Type", "text/css")
	} else if strings.HasSuffix(path, ".js") {
		w.Header().Set("Content-Type", "application/javascript")
	}

	fmt.Printf("✅ Served static file: %s\n", path)
	http.ServeContent(w, r, path, time.Time{}, data.(io.ReadSeeker))
}

// Page Handlers
func homeHandler(w http.ResponseWriter, r *http.Request) {
	log.Printf("📍 Home handler called - Method: %s, URL: %s", r.Method, r.URL.Path)

	data := types.PageData{
		Title: "Home",
	}

	renderTemplate(w, "home.html", data)
}

func hostPageHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		data := types.PageData{
			Title: "Host a Trivia Game",
		}
		renderTemplate(w, "host.html", data)
		return
	}

	// Handle POST - create session
	var req struct {
		Game     int    `json:"game"`
		HostName string `json:"host_name"`
		MaxTeams int    `json:"max_teams"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		data := types.PageData{
			Title: "Host a Trivia Game",
			Error: "Invalid form data",
		}
		renderTemplate(w, "host.html", data)
		return
	}

	// Create session (similar logic to API handler)
	code := generateSessionCode()
	session := &types.GameSession{
		Code:      code,
		GameID:    req.Game,
		GameName:  fmt.Sprintf("Game %d", req.Game), // Will be updated from Django
		Status:    "waiting",
		Teams:     make(map[string]*types.Team),
		Clients:   make(map[*types.Client]bool),
		Broadcast: make(chan types.Message),
	}

	mu.Lock()
	sessions[code] = session
	mu.Unlock()

	go session.Run()

	// Redirect to session page
	http.Redirect(w, r, fmt.Sprintf("/session/%s?type=host&name=%s", code, req.HostName), http.StatusSeeOther)
}

func teamJoinHandler(w http.ResponseWriter, r *http.Request) {
	if r.Method == "GET" {
		data := types.PageData{
			Title: "Join a Trivia Game",
		}
		renderTemplate(w, "team_join.html", data)
		return
	}

	// Handle POST - join team
	sessionCode := strings.ToUpper(strings.TrimSpace(r.FormValue("session_code")))
	teamName := strings.TrimSpace(r.FormValue("team_name"))

	if sessionCode == "" || teamName == "" {
		data := types.PageData{
			Title: "Join a Trivia Game",
			Error: "Session code and team name are required",
		}
		renderTemplate(w, "team_join.html", data)
		return
	}

	// Check if session exists
	mu.RLock()
	session, exists := sessions[sessionCode]
	mu.RUnlock()

	if !exists {
		data := types.PageData{
			Title:       "Join a Trivia Game",
			Error:       "Session not found",
			SessionCode: sessionCode,
		}
		renderTemplate(w, "team_join.html", data)
		return
	}

	// Check if team name is taken
	session.Mu.RLock()
	_, teamExists := session.Teams[teamName]
	session.Mu.RUnlock()

	if teamExists {
		data := types.PageData{
			Title:       "Join a Trivia Game",
			Error:       "Team name already taken",
			SessionCode: sessionCode,
		}
		renderTemplate(w, "team_join.html", data)
		return
	}

	// Redirect to session page
	http.Redirect(w, r, fmt.Sprintf("/session/%s?type=team&name=%s", sessionCode, teamName), http.StatusSeeOther)
}

func sessionPageHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := strings.ToUpper(vars["code"])

	mu.RLock()
	session, exists := sessions[code]
	mu.RUnlock()

	if !exists {
		data := types.PageData{
			Title: "Session Not Found",
			Error: "The requested session does not exist",
		}
		renderTemplate(w, "error.html", data)
		return
	}

	clientType := r.URL.Query().Get("type")
	clientName := r.URL.Query().Get("name")

	if clientType == "host" {
		data := struct {
			types.PageData
			Session *types.GameSession
		}{
			PageData: types.PageData{
				Title:       fmt.Sprintf("Host: %s", session.GameName),
				SessionCode: session.Code,
				GameName:    session.GameName,
			},
			Session: session,
		}
		renderTemplate(w, "host_session.html", data)
	} else {
		data := struct {
			types.PageData
			TeamName string
		}{
			PageData: types.PageData{
				Title:       fmt.Sprintf("Team: %s", session.GameName),
				SessionCode: session.Code,
				GameName:    session.GameName,
			},
			TeamName: clientName,
		}
		renderTemplate(w, "team_session.html", data)
	}
}

// API Handlers
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
	gameData, err := djangoClient.GetGameQuestions(req.Game)
	if err != nil {
		log.Printf("Failed to get game data: %v", err)
		http.Error(w, "Failed to create session", http.StatusInternalServerError)
		return
	}

	// Create session
	session := &types.GameSession{
		Code:            code,
		GameID:          req.Game,
		GameName:        fmt.Sprintf("Game %d", req.Game), // Update with actual name from Django
		Status:          "waiting",
		CurrentQuestion: 0,
		Questions:       gameData,
		Teams:           make(map[string]*types.Team),
		Clients:         make(map[*types.Client]bool),
		Broadcast:       make(chan types.Message),
	}

	// Store session
	mu.Lock()
	sessions[code] = session
	mu.Unlock()

	// Start session goroutine
	go session.Run()

	fmt.Printf("🎯 Created session %s for game %d (host: %s)\n", code, req.Game, req.HostName)

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
		"teams":            session.GetTeamList(),
	})
}

func websocketHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	code := vars["code"]

	log.Printf("🔌 WebSocket connection attempt for session: %s", code)

	mu.RLock()
	session, exists := sessions[code]
	mu.RUnlock()

	if !exists {
		log.Printf("❌ Session %s not found for WebSocket", code)
		http.Error(w, "Session not found", http.StatusNotFound)
		return
	}

	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		log.Printf("❌ Failed to upgrade WebSocket connection: %v", err)
		return
	}

	clientType := r.URL.Query().Get("type")
	clientName := r.URL.Query().Get("name")

	log.Printf("🔌 WebSocket client connecting - Type: %s, Name: %s", clientType, clientName)

	client := &types.Client{
		ID:      clientName,
		Conn:    conn,
		Session: session,
		Send:    make(chan types.Message, 256),
		IsHost:  clientType == "host",
	}

	session.Mu.Lock()
	session.Clients[client] = true
	if client.IsHost {
		session.Host = client
		log.Printf("🎪 Host '%s' connected to session %s", clientName, code)
	} else {
		log.Printf("👥 Team '%s' connected to session %s", clientName, code)
	}
	session.Mu.Unlock()

	// Send welcome message
	welcome := types.Message{
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

	go client.WritePump()
	go client.ReadPump()
}

// Utility functions
func generateSessionCode() string {
	chars := "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
	code := make([]byte, 6)
	for i := range code {
		code[i] = chars[time.Now().UnixNano()%int64(len(chars))]
		time.Sleep(time.Nanosecond)
	}
	return string(code)
}

func main() {
	fmt.Println("🎯 Trivia Session Service Starting...")

	djangoClient = django.NewClient("http://127.0.0.1:8000")

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
	r.HandleFunc("/host", hostPageHandler).Methods("GET", "POST")
	r.HandleFunc("/join", teamJoinHandler).Methods("GET", "POST")
	r.HandleFunc("/session/{code}", sessionPageHandler)

	port := ":8080"
	fmt.Printf("🚀 Trivia service running at http://localhost%s\n", port)
	log.Fatal(http.ListenAndServe(port, r))
}
