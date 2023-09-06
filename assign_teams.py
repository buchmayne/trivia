import random
from typing import Optional


class Player:
    def __init__(self, name: str, male: bool, partner: Optional[str] = None):
        self.name = name
        self.partner = partner
        self.male = male

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


def sort_players_by_sex(players: list) -> dict:
    men = []
    women = []
    for player in players:
        if player.male:
            men.append(player)
        else:
            women.append(player)

    return {'men': men, 'women': women}

def assign_teams(players: list, teams: list) -> None:
    # try to balance teams by sex
    sorted_by_sex = sort_players_by_sex(players)
    men = sorted_by_sex['men']
    women = sorted_by_sex['women']
    
    # shuffle male and female player pools
    random.shuffle(men)
    random.shuffle(women)

    # assign teams balanced by sex, and avoiding partners on the same team
    selected_players = []
    select_male = True
    
    while len(selected_players) < len(players):
        if select_male:
            if len(men) > 0:
                chosen_player = random.choice(men)
                for team in teams:
                    if len(team.players) < team.max_team_size:
                        assigned_players = [p for t in teams for p in t.players]
                        if chosen_player.name not in assigned_players:
                            if chosen_player.partner is None or chosen_player.partner not in team.players:
                                team.add_player(chosen_player.name)
                                men = [male_player for male_player in men if male_player.name != chosen_player.name]
                                selected_players.append(chosen_player)
                                select_male = False
            else:
                select_male = False
        else:
            if len(women) > 0:
                chosen_player = random.choice(women)
                for team in teams:
                    if len(team.players) < team.max_team_size:
                        assigned_players = [p for t in teams for p in t.players]
                        if chosen_player.name not in assigned_players:
                            if chosen_player.partner is None or chosen_player.partner not in team.players:
                                team.add_player(chosen_player.name)
                                women = [female_player for female_player in women if female_player.name != chosen_player.name]
                                selected_players.append(chosen_player)
                                select_male = True
            else:
                select_male = True
    

    # print teams
    for team in teams:
        print(f"{team.name}: {', '.join(team.players)}\n")


if __name__ == "__main__":
    # Add participants and determine whether they have a partner
    players = [
        # 1-5
        Player("Mike T", True, "Tayler T"),
        Player("Gerik I", True, "Claire I"),
        Player("Dylan S", True, "Erica B"),
        Player("Andy L", True),
        Player("Claire I", False, "Gerik I"),


	# 5-10
        Player("Erica B", False, "Dylan S"),
        Player("Jenna C", False),
        Player("Andrew D", True),
        Player("Charlie C", True),
        Player("Mitch", True, "Katherine"),

	# 10-15
        Player("Katherine", False, "Mitch"),
	Player("Joshua", True, "Annie"),
	Player("Annie", False, "Joshua"),
	Player("Steven", True),
	Player("Anna", False),
	
	# 15-16
	Player("Jasper", True),
    ]

    # Create teams and set max team size
    teams = [
        Team("Team 1", max_team_size=4),
        Team("Team 2", max_team_size=4),
        Team("Team 3", max_team_size=4),
        Team("Team 4", max_team_size=4),
    ]

    assign_teams(players, teams)
