package main

import (
	"fmt"
	"log"
	"net/http"
)

func main() {
	fmt.Println("🎮 Trivia Session Service")
	fmt.Println("This will eventually handle real-time trivia sessions!")

	// TODO: Add WebSocket handling
	// TODO: Add Django API integration
	// TODO: Add session management

	// For now, just a simple HTTP server
	http.HandleFunc("/health", healthCheck)

	port := ":8080"
	fmt.Printf("Server starting on http://localhost%s\n", port)
	fmt.Println("Visit http://localhost:8080/health to test")

	log.Fatal(http.ListenAndServe(port, nil))
}

func healthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	fmt.Fprint(w, `{"status": "ok", "service": "trivia-sessions"}`)
}
