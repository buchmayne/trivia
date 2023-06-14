import random
from typing import Optional


class Player:
    def __init__(self, name: str, partner: Optional[str] = None):
        self.name = name
        self.partner = partner

    def __str__(self):
        return self.name


class Team:
    def __init__(self, name: str, max_team_size: int, players=None):
        self.name = name
        self.max_team_size = max_team_size
        if players is not None:
            self.players = list(players)
        else:
            self.players = []

    def add_player(self, player):
        self.players.append(player)

    def __iter__(self):
        return iter(self.players)

    def __str__(self):
        return str([str(player) for player in self.players])


def assign_teams(players: list, teams: list) -> None:
    random.shuffle(players)
    for player in players:
        for team in teams:
            if len(team.players) < team.max_team_size:
                assigned_players = [p for t in teams for p in t.players]
                if player.name not in assigned_players:
                    if player.partner is None or player.partner not in team.players:
                        team.add_player(player.name)

    for team in teams:
        print(f"{team.name}: {', '.join(team.players)}\n")


if __name__ == "__main__":
    # Add participants and determine whether they have a partner
    players = [
        # 1-5
        Player("Mike T", "Tayler T"),
        Player("Gerik I", "Claire I"),
        Player("Alex M", "Hillary M"),
        Player("Dylan S", "Erica B"),
        Player("Andy L"),
        # 5-10
        Player("Tayler T", "Mike T"),
        Player("Claire I", "Gerik I"),
        Player("Brittany R", "Howie R"),
        Player("Hillary M", "Alex M"),
        Player("Erica B", "Dylan S"),
        # 10-15
        Player("Jenna C"),
        Player("Andrew D"),
        Player("James H", "Claire T"),
        Player("Charlie C"),
        Player("Pilar", "Chris H"),
        # 16-20
        Player("Chris H", "Pilar"),
    ]

    # Create teams and set max team size
    teams = [
        Team("Team 1", max_team_size=4),
        Team("Team 2", max_team_size=4),
        Team("Team 3", max_team_size=4),
        Team("Team 4", max_team_size=4),
    ]

    assign_teams(players, teams)
