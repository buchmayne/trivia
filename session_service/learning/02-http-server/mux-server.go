package main

import (
	"fmt"
	"log"
	"net/http"

	"github.com/gorilla/mux"
)

func main() {
	fmt.Println("🔀 Learning advanced routing with Gorilla Mux...")

	// Create new router
	router := mux.NewRouter()

	// Add routes with better patterns
	router.HandleFunc("/", homeHandler).Methods("GET")
	router.HandleFunc("/health", healthHandler).Methods("GET")

	// API routes with version prefix
	api := router.PathPrefix("/api/v1").Subrouter()
	api.HandleFunc("/sessions", listSessionsHandler).Methods("GET")
	api.HandleFunc("/sessions", createSessionHandler).Methods("POST")
	api.HandleFunc("/sessions/{code}", getSessionHandler).Methods("GET")
	api.HandleFunc("/sessions/{code}/teams", addTeamHandler).Methods("POST")

	// Add middleware
	router.Use(loggingMiddleware)

	port := ":8080"
	fmt.Printf("Server with Mux routing at http://localhost%s\n", port)
	fmt.Println("Try these URLs:")
	fmt.Println("  GET  http://localhost:8080/api/v1/sessions")
	fmt.Println("  POST http://localhost:8080/api/v1/sessions")
	fmt.Println("  GET  http://localhost:8080/api/v1/sessions/ABC123")
	fmt.Println("  POST http://localhost:8080/api/v1/sessions/ABC123/teams")

	log.Fatal(http.ListenAndServe(port, router))
}

// Middleware that logs all requests
func loggingMiddleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		fmt.Printf("📝 %s %s from %s\n", r.Method, r.URL.Path, r.RemoteAddr)
		next.ServeHTTP(w, r)
	})
}

func homeHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Fprint(w, "🎯 Trivia Session Service API\n")
	fmt.Fprint(w, "API endpoints available at /api/v1/\n")
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"status": "healthy", "service": "trivia-sessions"}`)
}

func listSessionsHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{
		"sessions": [
			{"code": "ABC123", "status": "waiting", "teams": 2},
			{"code": "XYZ789", "status": "active", "teams": 5}
		]
	}`)
}

func createSessionHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{
		"session_code": "NEW456",
		"status": "created",
		"message": "Session created with Mux routing!"
	}`)
}

func getSessionHandler(w http.ResponseWriter, r *http.Request) {
	// Extract URL parameter
	vars := mux.Vars(r)
	sessionCode := vars["code"]

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{
		"session_code": "%s",
		"status": "active",
		"teams": 3,
		"current_question": 5
	}`, sessionCode)
}

func addTeamHandler(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	sessionCode := vars["code"]

	w.Header().Set("Content-Type", "application/json")
	fmt.Fprintf(w, `{
		"session_code": "%s",
		"message": "Team added successfully!",
		"team_count": 4
	}`, sessionCode)
}
