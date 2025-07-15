package main

import (
	"fmt"
	"math"
	"math/rand"
	"slices"
	"time"
)

type Sex string

const (
	Male   Sex = "male"
	Female Sex = "female"
)

type Player struct {
	Name    string
	Sex     Sex
	Partner *string
}

type Team struct {
	Name           string
	MaxTeamSize    int
	MaxMenOnTeam   int
	MaxWomenOnTeam int
	Players        []Player
}

type Game struct {
	Players []Player
	teams   []Team
}

// Helpers
func PartnerPtr(s string) *string {
	return &s
}

func divmod(a, b int) (int, int) {
	quotient := a / b
	remainder := a % b
	return quotient, remainder
}

// Team methods
func (t Team) HasPlayerObject(targetPlayer Player) bool {
	return slices.Contains(t.Players, targetPlayer)
}

func (t Team) HasPlayerName(name string) bool {
	for _, p := range t.Players {
		if p.Name == name {
			return true
		}
	}
	return false
}

func (t Team) Size() int {
	return len(t.Players)
}

func (t Team) CountPlayersBySex(sex Sex) int {
	count := 0
	for _, player := range t.Players {
		if player.Sex == sex {
			count++
		}
	}
	return count
}

func (t Team) canAddPlayer(player Player) bool {
	// Validate whether a player can be added to a team

	// Is player already assigned to this team
	if t.HasPlayerObject(player) {
		return false
	}

	// Does team have space for new player
	if len(t.Players) >= t.MaxTeamSize {
		return false
	}

	// Does team have space for more male players
	if t.CountPlayersBySex(Male) >= t.MaxMenOnTeam && player.Sex == Male {
		return false
	}

	// Does team have space for more female players
	if t.CountPlayersBySex(Female) >= t.MaxWomenOnTeam && player.Sex == Female {
		return false
	}

	// Is player's partner already on the team
	if player.Partner != nil && t.HasPlayerName(*player.Partner) {
		return false
	}

	return true
}

func (t *Team) AddPlayer(player Player) bool {
	if !t.canAddPlayer(player) {
		return false
	}
	t.Players = append(t.Players, player)
	return true
}

func (g Game) GetTotalPlayers() int {
	return len(g.Players)
}

func (g Game) GetTotalPlayersBySex(sex Sex) int {
	count := 0
	for _, player := range g.Players {
		if player.Sex == sex {
			count++
		}
	}
	return count
}

func (g *Game) Teams() []Team {
	if g.teams == nil {
		g.createTeams()
	}
	return g.teams
}

func (g *Game) createTeams() {
	numberTeams, extraPlayers := divmod(g.GetTotalPlayers(), 4)

	maxMenPerTeam := int(math.Ceil(float64(g.GetTotalPlayersBySex(Male)) / float64(numberTeams)))
	maxWomenPerTeam := int(math.Ceil(float64(g.GetTotalPlayersBySex(Female)) / float64(numberTeams)))

	for i := 0; i < numberTeams; i++ {
		var maxTeamSize int
		if i < extraPlayers {
			maxTeamSize = 5
		} else {
			maxTeamSize = 4
		}

		team := Team{
			Name:           fmt.Sprintf("Team %d", i+1),
			MaxTeamSize:    maxTeamSize,
			MaxMenOnTeam:   maxMenPerTeam,
			MaxWomenOnTeam: maxWomenPerTeam,
		}
		g.teams = append(g.teams, team)
	}
}

func (g *Game) AssignPlayersToTeams() {
	// Create a copy of players slice
	unassignedPlayers := make([]Player, len(g.Players))
	copy(unassignedPlayers, g.Players)

	// Separate players with and without partners
	var playersWithPartners []Player
	var playersWithoutPartners []Player

	for _, player := range unassignedPlayers {
		if player.Partner != nil && *player.Partner != "" {
			playersWithPartners = append(playersWithPartners, player)
		} else {
			playersWithoutPartners = append(playersWithoutPartners, player)
		}
	}

	// Shuffle players without partners
	rand.Shuffle(len(playersWithoutPartners), func(i, j int) {
		playersWithoutPartners[i], playersWithoutPartners[j] = playersWithoutPartners[j], playersWithoutPartners[i]
	})

	// Combine: partners first, then shuffled singles
	unassignedPlayers = append(playersWithPartners, playersWithoutPartners...)

	// Assignment loop
	for len(unassignedPlayers) > 0 {
		initialCount := len(unassignedPlayers)

		// Try to assign each player
		for i := len(unassignedPlayers) - 1; i >= 0; i-- {
			player := unassignedPlayers[i]
			assigned := false

			for j := range g.teams {
				if g.teams[j].AddPlayer(player) {
					// Remove from unassigned (by index)
					unassignedPlayers = append(unassignedPlayers[:i], unassignedPlayers[i+1:]...)
					assigned = true
					break
				}
			}

			if assigned {
				break // Start over with updated slice
			}
		}

		// Check if we made progress
		if len(unassignedPlayers) == initialCount {
			fmt.Printf("\nCannot assign remaining %d players:\n", len(unassignedPlayers))
			for _, player := range unassignedPlayers {
				fmt.Printf(" - %s\n", player.Name)
			}

			// Show team status
			for _, team := range g.teams {
				fmt.Printf("%s: M=%d/%d, F=%d/%d, Size=%d/%d\n",
					team.Name,
					team.CountPlayersBySex(Male), team.MaxMenOnTeam,
					team.CountPlayersBySex(Female), team.MaxWomenOnTeam,
					team.Size(), team.MaxTeamSize,
				)
			}
			break
		}
	}
}
func main() {
	fmt.Println("Running Team Assignment Algorithm")

	players := []Player{
		// 1-5
		{Name: "Gerik", Sex: Male, Partner: PartnerPtr("Claire")},
		{Name: "Claire", Sex: Female, Partner: PartnerPtr("Geirk")},
		{Name: "Walker", Sex: Male, Partner: nil},
		{Name: "Woman B", Sex: Female, Partner: nil},
		{Name: "Andy", Sex: Male, Partner: nil},
		// 6-10
		{Name: "Marley", Sex: Male, Partner: PartnerPtr("Jenna")},
		{Name: "Jenna", Sex: Female, Partner: PartnerPtr("Marley")},
		{Name: "Brittany", Sex: Female, Partner: PartnerPtr("Howie")},
		{Name: "Howie", Sex: Male, Partner: PartnerPtr("Brittany")},
		{Name: "Steven", Sex: Male, Partner: nil},
		// 11-12
		{Name: "Andrew Dang", Sex: Male, Partner: nil},
		{Name: "Colby", Sex: Male, Partner: nil},
	}

	game := Game{
		Players: players,
	}

	game.createTeams()
	game.AssignPlayersToTeams()

	fmt.Println("Teams in game session:")
	for _, team := range game.teams {
		fmt.Printf("%s: \n", team.Name)
		for _, player := range team.Players {
			fmt.Printf("%s\n", player.Name)
		}
	}

	// Practice with time (useful for sessions)
	fmt.Printf("Session would start at: %s\n", time.Now().Format("15:04:05"))
}
