package main

import (
	"fmt"
	"log"
	"net/http"
)

func main() {
	fmt.Println("🚀 Starting HTTP server learning...")

	// Register route handlers
	http.HandleFunc("/", homeHandler)
	http.HandleFunc("/health", healthHandler)
	http.HandleFunc("/sessions", sessionsHandler)
	http.HandleFunc("/sessions/create", createSessionHandler)

	// Start server
	port := ":8080"
	fmt.Printf("Server running at http://localhost%s\n", port)
	fmt.Println("Try these URLs:")
	fmt.Println("  http://localhost:8080/")
	fmt.Println("  http://localhost:8080/health")
	fmt.Println("  http://localhost:8080/sessions")
	fmt.Println("  http://localhost:8080/sessions/create")

	// This blocks and runs the server
	log.Fatal(http.ListenAndServe(port, nil))
}

// Handler functions - these respond to HTTP requests
func homeHandler(w http.ResponseWriter, r *http.Request) {
	fmt.Fprintf(w, "🎯 Trivia Session Service\n")
	fmt.Fprintf(w, "Available endpoints:\n")
	fmt.Fprintf(w, "  GET  /health\n")
	fmt.Fprintf(w, "  GET  /sessions\n")
	fmt.Fprintf(w, "  POST /sessions/create\n")
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	// Set response headers
	w.Header().Set("Content-Type", "application/json")

	// Write JSON response
	fmt.Fprint(w, `{
		"status": "healthy",
		"service": "trivia-sessions",
		"version": "learning-v1"
	}`)
}

func sessionsHandler(w http.ResponseWriter, r *http.Request) {
	// Handle different HTTP methods
	switch r.Method {
	case "GET":
		// List sessions (mock data for now)
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `{
			"sessions": [
				{"code": "ABC123", "status": "waiting", "teams": 2},
				{"code": "XYZ789", "status": "active", "teams": 5}
			]
		}`)
	default:
		// Method not allowed
		w.WriteHeader(http.StatusMethodNotAllowed)
		fmt.Fprintf(w, "Method %s not allowed", r.Method)
	}
}

func createSessionHandler(w http.ResponseWriter, r *http.Request) {
	// Only allow POST requests
	if r.Method != "POST" {
		w.WriteHeader(http.StatusMethodNotAllowed)
		fmt.Fprint(w, "Only POST method allowed")
		return
	}

	// Mock session creation
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{
		"session_code": "NEW123",
		"status": "created",
		"message": "Session created successfully!"
	}`)
}
