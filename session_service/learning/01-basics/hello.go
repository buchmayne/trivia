package main

import (
	"fmt"
	"time"
)

func main() {
	fmt.Println("🎯 Starting Go journey for trivia sessions!")

	// Practice basic Go syntax
	sessionCode := generateSessionCode()
	fmt.Printf("Generated session code: %s\n", sessionCode)

	// Practice with basic data structures
	teams := []string{"Code Warriors", "Debug Squad", "Syntax Heroes"}
	fmt.Println("Teams ready to join:")
	for i, team := range teams {
		fmt.Printf("  %d. %s\n", i+1, team)
	}

	// Practice with time (useful for sessions)
	fmt.Printf("Session would start at: %s\n", time.Now().Format("15:04:05"))
}

func generateSessionCode() string {
	// Simple session code generator
	codes := []string{"ALPHA", "BRAVO", "DELTA", "GAMMA", "OMEGA"}
	return codes[len(codes)-1] // Just return last one for now
}
