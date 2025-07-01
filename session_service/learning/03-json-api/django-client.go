package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
)

// Structs that match your Django API responses
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
	QuestionImageURL *string `json:"question_image_url"`
}

type GameQuestionsResponse struct {
	Game      Game       `json:"game"`
	Questions []Question `json:"questions"`
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

func (d *DjangoClient) CreateSession(req SessionCreateRequest) (*SessionCreateResponse, error) {
	url := d.BaseURL + "/quiz/api/sessions/create/"

	// Convert Go struct to JSON
	jsonData, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	// Make HTTP POST request
	resp, err := d.Client.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to make request: %w", err)
	}
	defer resp.Body.Close()

	// Check status code
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	// Parse JSON response
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

func main() {
	fmt.Println("🔗 Testing Django API integration...")

	// Create Django client
	client := NewDjangoClient("http://127.0.0.1:8000")

	// Test 1: Create a session
	fmt.Println("\n📝 Creating a new session...")
	sessionReq := SessionCreateRequest{
		Game:     1, // Make sure you have a game with ID 1 in Django
		HostName: "Go Test Host",
		MaxTeams: 8,
	}

	session, err := client.CreateSession(sessionReq)
	if err != nil {
		log.Printf("❌ Failed to create session: %v", err)
		return
	}

	fmt.Printf("✅ Session created successfully!\n")
	fmt.Printf("   Session Code: %s\n", session.SessionCode)
	fmt.Printf("   Game: %s (ID: %d)\n", session.GameName, session.GameID)
	fmt.Printf("   Session ID: %d\n", session.SessionID)

	// Test 2: Get questions for the game
	fmt.Println("\n📚 Fetching game questions...")
	gameData, err := client.GetGameQuestions(session.GameID)
	if err != nil {
		log.Printf("❌ Failed to get questions: %v", err)
		return
	}

	fmt.Printf("✅ Retrieved %d questions for '%s'\n", len(gameData.Questions), gameData.Game.Name)

	// Show first few questions
	for i, question := range gameData.Questions {
		if i >= 3 { // Just show first 3
			break
		}
		fmt.Printf("   Q%d: %s (%d points, %d answers)\n",
			question.QuestionNumber,
			truncateString(question.Text, 50),
			question.TotalPoints,
			len(question.Answers))
	}

	fmt.Println("\n🎉 Django integration working perfectly!")
	fmt.Println("🚀 Ready to build WebSocket session management!")
}

func truncateString(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
