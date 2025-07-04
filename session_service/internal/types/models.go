package types

import (
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gorilla/websocket"
)

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
	Mu              sync.RWMutex     `json:"-"` // Exported for access from main
	Broadcast       chan Message     `json:"-"`
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

type PageData struct {
	Title       string
	SessionCode string
	GameName    string
	Error       string
	Success     string
}

// GameSession methods
func (s *GameSession) Run() {
	for {
		select {
		case message := <-s.Broadcast:
			s.HandleMessage(message)
		}
	}
}

func (s *GameSession) HandleMessage(msg Message) {
	s.Mu.Lock()
	defer s.Mu.Unlock()

	log.Printf("🎮 Session %s: Received '%s' message from '%s'", s.Code, msg.Type, msg.From)
	log.Printf("📊 Message data: %+v", msg.Data)

	switch msg.Type {
	case "join_team":
		log.Printf("🔄 Processing team join...")
		s.HandleTeamJoin(msg)
	case "host_command":
		log.Printf("🔄 Processing host command...")
		s.HandleHostCommand(msg)
	case "submit_answer":
		log.Printf("🔄 Processing answer submission...")
		s.HandleAnswerSubmission(msg)
	default:
		log.Printf("⚠️ Unknown message type: %s", msg.Type)
	}
}

func (s *GameSession) HandleTeamJoin(msg Message) {
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

	s.BroadcastToAll(Message{
		Type: "team_joined",
		Data: map[string]interface{}{
			"team_name":   teamName,
			"total_teams": len(s.Teams),
			"teams":       s.GetTeamList(),
		},
	})
}

func (s *GameSession) HandleHostCommand(msg Message) {
	data := msg.Data.(map[string]interface{})
	command := data["command"].(string)

	log.Printf("🎯 Processing host command: %s", command)

	switch command {
	case "start_game":
		s.Status = "active"
		fmt.Printf("🚀 Game started in session %s\n", s.Code)
		s.BroadcastToAll(Message{
			Type: "game_started",
			Data: map[string]interface{}{
				"message": "Game is starting! Get ready!",
				"status":  s.Status,
			},
		})
	case "show_question":
		questionNum := int(data["question_number"].(float64))
		log.Printf("🎯 Attempting to show question %d (total questions: %d)", questionNum, len(s.Questions))

		if len(s.Questions) == 0 {
			log.Printf("❌ No questions available in session!")
			return
		}

		s.ShowQuestion(questionNum)
	case "next_question":
		log.Printf("🎯 Attempting next question (current: %d, total: %d)", s.CurrentQuestion, len(s.Questions))

		if len(s.Questions) == 0 {
			log.Printf("❌ No questions available in session!")
			return
		}
		s.NextQuestion()
	case "show_answers":
		s.ShowAnswers()
	case "end_game":
		s.Status = "completed"
		s.BroadcastToAll(Message{
			Type: "game_ended",
			Data: map[string]interface{}{
				"message": "Game completed!",
				"status":  s.Status,
				"teams":   s.GetTeamList(),
			},
		})
	}
}

func (s *GameSession) HandleAnswerSubmission(msg Message) {
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

	fmt.Printf("📝 Team '%s' submitted answer for question %d: %s\n",
		teamName, questionNum, answer)

	s.SendToHost(Message{
		Type: "answer_submitted",
		Data: map[string]interface{}{
			"team_name":       teamName,
			"question_number": questionNum,
			"answer":          answer,
			"timestamp":       team.AnswerTimestamps[questionNum],
		},
	})
}

func (s *GameSession) ShowQuestion(questionNum int) {
	log.Printf("🎯 ShowQuestion called: questionNum=%d, total=%d", questionNum, len(s.Questions))

	if questionNum < 1 || questionNum > len(s.Questions) {
		log.Printf("❌ Invalid question number: %d (valid range: 1-%d)", questionNum, len(s.Questions))
		return
	}

	s.CurrentQuestion = questionNum
	question := s.Questions[questionNum-1]

	log.Printf("🎯 Showing question: %+v", question)

	// Send full question to host
	hostMsg := Message{
		Type: "question_displayed",
		Data: map[string]interface{}{
			"question_number": questionNum,
			"question":        question,
			"total_questions": len(s.Questions),
		},
	}
	log.Printf("🎪 Sending question to host: %+v", hostMsg)
	s.SendToHost(hostMsg)

	// Send question without correct answers to teams
	teamQuestion := s.PrepareQuestionForTeams(question)
	teamMsg := Message{
		Type: "question_displayed",
		Data: map[string]interface{}{
			"question_number": questionNum,
			"question":        teamQuestion,
			"total_questions": len(s.Questions),
		},
	}
	log.Printf("👥 Sending question to teams: %+v", teamMsg)
	s.BroadcastToTeams(teamMsg)
}

func (s *GameSession) PrepareQuestionForTeams(question Question) Question {
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

func (s *GameSession) ShowAnswers() {
	if s.CurrentQuestion == 0 {
		return
	}

	question := s.Questions[s.CurrentQuestion-1]

	s.BroadcastToAll(Message{
		Type: "answers_revealed",
		Data: map[string]interface{}{
			"question_number": s.CurrentQuestion,
			"question":        question,
			"total_questions": len(s.Questions),
		},
	})
}

func (s *GameSession) NextQuestion() {
	if s.CurrentQuestion < len(s.Questions) {
		s.ShowQuestion(s.CurrentQuestion + 1)
	}
}

func (s *GameSession) GetTeamList() []map[string]interface{} {
	teams := make([]map[string]interface{}, 0, len(s.Teams))
	for _, team := range s.Teams {
		teams = append(teams, map[string]interface{}{
			"name":  team.Name,
			"score": team.Score,
		})
	}
	return teams
}

func (s *GameSession) BroadcastToAll(msg Message) {
	for client := range s.Clients {
		select {
		case client.Send <- msg:
		default:
		}
	}
}

func (s *GameSession) BroadcastToTeams(msg Message) {
	for client := range s.Clients {
		if !client.IsHost {
			select {
			case client.Send <- msg:
			default:
			}
		}
	}
}

func (s *GameSession) SendToHost(msg Message) {
	if s.Host != nil {
		select {
		case s.Host.Send <- msg:
		default:
		}
	}
}

// Client methods
func (c *Client) ReadPump() {
	defer func() {
		c.Session.Mu.Lock()
		delete(c.Session.Clients, c)
		c.Session.Mu.Unlock()
		c.Conn.Close()
	}()

	for {
		var msg Message
		err := c.Conn.ReadJSON(&msg)
		if err != nil {
			log.Printf("WebSocket read error: %v", err)
			break
		}
		msg.From = c.ID
		c.Session.Broadcast <- msg
	}
}

func (c *Client) WritePump() {
	defer c.Conn.Close()
	for {
		select {
		case message, ok := <-c.Send:
			if !ok {
				c.Conn.WriteMessage(websocket.CloseMessage, []byte{})
				return
			}
			if err := c.Conn.WriteJSON(message); err != nil {
				log.Printf("WebSocket write error: %v", err)
				return
			}
		}
	}
}
