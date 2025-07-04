// session_service/cmd/server/django.go
package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type DjangoClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

type GameData struct {
	Game      GameInfo   `json:"game"`
	Questions []Question `json:"questions"`
}

type GameInfo struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

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

func NewDjangoClient(baseURL string) *DjangoClient {
	return &DjangoClient{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *DjangoClient) GetGameQuestions(gameID int) (*GameData, error) {
	url := fmt.Sprintf("%s/quiz/api/games/%d/questions/", c.BaseURL, gameID)
	
	resp, err := c.HTTPClient.Get(url)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch game data: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	var gameData GameData
	if err := json.NewDecoder(resp.Body).Decode(&gameData); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &gameData, nil
}

func (c *DjangoClient) CreateSession(gameID int, hostName string, maxTeams int, sessionCode string) (*SessionCreateResponse, error) {
	url := fmt.Sprintf("%s/quiz/api/sessions/create/", c.BaseURL)
	
	reqData := SessionCreateRequest{
		Game:     gameID,
		HostName: hostName,
		MaxTeams: maxTeams,
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := c.HTTPClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %w", err)
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

func (c *DjangoClient) SubmitTeamAnswer(sessionID int, teamName string, questionID int, answer string) error {
	url := fmt.Sprintf("%s/quiz/api/answers/submit/", c.BaseURL)
	
	reqData := map[string]interface{}{
		"session_id":    sessionID,
		"team_name":     teamName,
		"question_id":   questionID,
		"answer":        answer,
		"submitted_at":  time.Now().Format(time.RFC3339),
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := c.HTTPClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to submit answer: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

func (c *DjangoClient) UpdateSessionStatus(sessionID int, status string) error {
	url := fmt.Sprintf("%s/quiz/api/sessions/%d/status/", c.BaseURL, sessionID)
	
	reqData := map[string]string{
		"status": status,
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPatch, url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to update session status: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type DjangoClient struct {
	BaseURL    string
	HTTPClient *http.Client
}

type GameData struct {
	Game      GameInfo   `json:"game"`
	Questions []Question `json:"questions"`
}

type GameInfo struct {
	ID          int    `json:"id"`
	Name        string `json:"name"`
	Description string `json:"description"`
}

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

func NewDjangoClient(baseURL string) *DjangoClient {
	return &DjangoClient{
		BaseURL: baseURL,
		HTTPClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

func (c *DjangoClient) GetGameQuestions(gameID int) (*GameData, error) {
	url := fmt.Sprintf("%s/quiz/api/games/%d/questions/", c.BaseURL, gameID)
	
	resp, err := c.HTTPClient.Get(url)
	if err != nil {
		return nil, fmt.Errorf("failed to fetch game data: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	var gameData GameData
	if err := json.NewDecoder(resp.Body).Decode(&gameData); err != nil {
		return nil, fmt.Errorf("failed to decode response: %w", err)
	}

	return &gameData, nil
}

func (c *DjangoClient) CreateSession(gameID int, hostName string, maxTeams int, sessionCode string) (*SessionCreateResponse, error) {
	url := fmt.Sprintf("%s/quiz/api/sessions/create/", c.BaseURL)
	
	reqData := SessionCreateRequest{
		Game:     gameID,
		HostName: hostName,
		MaxTeams: maxTeams,
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return nil, fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := c.HTTPClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return nil, fmt.Errorf("failed to create session: %w", err)
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

func (c *DjangoClient) SubmitTeamAnswer(sessionID int, teamName string, questionID int, answer string) error {
	url := fmt.Sprintf("%s/quiz/api/answers/submit/", c.BaseURL)
	
	reqData := map[string]interface{}{
		"session_id":    sessionID,
		"team_name":     teamName,
		"question_id":   questionID,
		"answer":        answer,
		"submitted_at":  time.Now().Format(time.RFC3339),
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	resp, err := c.HTTPClient.Post(url, "application/json", bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to submit answer: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK && resp.StatusCode != http.StatusCreated {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return nil
}

func (c *DjangoClient) UpdateSessionStatus(sessionID int, status string) error {
	url := fmt.Sprintf("%s/quiz/api/sessions/%d/status/", c.BaseURL, sessionID)
	
	reqData := map[string]string{
		"status": status,
	}

	jsonData, err := json.Marshal(reqData)
	if err != nil {
		return fmt.Errorf("failed to marshal request: %w", err)
	}

	req, err := http.NewRequest(http.MethodPatch, url, bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return fmt.Errorf("failed to update session status: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error %d: %s", resp.StatusCode, string(body))
	}

	return nil
}