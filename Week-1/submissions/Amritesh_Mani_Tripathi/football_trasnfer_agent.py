from ollama import chat
# ─────────────────────────────────────────────
# TOOLS
# ─────────────────────────────────────────────
def search_players(position: str) -> str:
    """Search players by position."""

    players = {
        "goalkeeper": [
            "Marc-Andre ter Stegen",
            "Alisson Becker",
            "Keylor Navas"
        ],

        "defender": [
            "Dayot Upamecano",
            "Antonio Rudiger",
            "Marc Guéhi",
            "Alphonso Davies"
        ],

        "midfielder": [
            "Frenkie de Jong",
            "Bernardo Silva",
            "Casemiro",
            "Vitinha"
        ],

        "striker": [
            "Victor Osimhen",
            "Alexander Isak",
            "Dusan Vlahovic",
            "Julián Álvarez",
            "Anthony Gordon"
        ]
    }

    position_lower = position.lower()

    for pos, player_list in players.items():
        if pos in position_lower:
            return (
                f"Found {len(player_list)} {pos}s:\n"
                + "\n".join(player_list)
            )

    return (
        "Position not found. Try: "
        "goalkeeper, defender, midfielder, striker."
    )


def get_player_details(player_name: str) -> str:

    players = {

        "Marc-Andre ter Stegen": {
            "club": "Barcelona",
            "value": "€20M",
            "clean_sheets": 12,
            "saves": 95,
            "save_percentage": "74%"
        },

        "Alisson Becker": {
            "club": "Liverpool",
            "value": "€25M",
            "clean_sheets": 14,
            "saves": 102,
            "save_percentage": "78%"
        },

        "Keylor Navas": {
            "club": "Free Agent",
            "value": "Free Transfer",
            "clean_sheets": 9,
            "saves": 81,
            "save_percentage": "76%"
        },

        "Dayot Upamecano": {
            "club": "Bayern Munich",
            "value": "€50M",
            "tackles": 78,
            "interceptions": 61,
            "clearances": 97,
            "goal_line_clearances": 3
        },

        "Antonio Rudiger": {
            "club": "Real Madrid",
            "value": "€40M",
            "tackles": 82,
            "interceptions": 65,
            "clearances": 110,
            "goal_line_clearances": 4
        },

        "Marc Guehi": {
            "club": "Crystal Palace",
            "value": "€45M",
            "tackles": 84,
            "interceptions": 72,
            "clearances": 121,
            "goal_line_clearances": 5
        },

        "Alphonso Davies": {
            "club": "Bayern Munich",
            "value": "€60M",
            "tackles": 71,
            "interceptions": 43,
            "assists": 8,
            "progressive_carries": 145
        },

        "Frenkie de Jong": {
            "club": "Barcelona",
            "value": "€70M",
            "goals": 4,
            "assists": 7,
            "key_passes": 56,
            "pass_accuracy": "91%"
        },

        "Bernardo Silva": {
            "club": "Manchester City",
            "value": "€60M",
            "goals": 8,
            "assists": 11,
            "key_passes": 68,
            "pass_accuracy": "89%"
        },

        "Casemiro": {
            "club": "Manchester United",
            "value": "€15M",
            "goals": 3,
            "assists": 2,
            "tackles": 93,
            "interceptions": 79
        },

        "Vitinha": {
            "club": "PSG",
            "value": "€75M",
            "goals": 7,
            "assists": 10,
            "key_passes": 72,
            "pass_accuracy": "92%"
        },

        "Victor Osimhen": {
            "club": "Napoli",
            "value": "€75M",
            "goals": 31,
            "assists": 6,
            "shots_on_target": 65,
            "minutes_per_goal": 109
        },

        "Alexander Isak": {
            "club": "Newcastle United",
            "value": "€100M",
            "goals": 27,
            "assists": 7,
            "shots_on_target": 71,
            "minutes_per_goal": 118
        },

        "Dusan Vlahovic": {
            "club": "Juventus",
            "value": "€45M",
            "goals": 18,
            "assists": 4,
            "shots_on_target": 51,
            "minutes_per_goal": 142
        },

        "Julian Alvarez": {
            "club": "Atletico Madrid",
            "value": "€90M",
            "goals": 29,
            "assists": 8,
            "shots_on_target": 67,
            "minutes_per_goal": 114
        },

        "Anthony Gordon": {
            "club": "Newcastle United",
            "value": "€65M",
            "goals": 12,
            "assists": 15,
            "successful_dribbles": 98,
            "key_passes": 63
        }
    }

    player = players.get(player_name)

    if not player:
        return f"Player '{player_name}' not found."

    result = (
        f"\nPlayer: {player_name}"
        f"\nClub: {player['club']}"
        f"\nEstimated Value: {player['value']}"
    )

    for stat, value in player.items():
        if stat not in ["club", "value"]:
            result += f"\n{stat.replace('_', ' ').title()}: {value}"

    return result


def check_availability(player_name: str) -> str:

    availability = {

        "Marc-Andre ter Stegen": {
            "status": "Not for Sale",
            "estimated_fee": "€25M"
        },

        "Alisson Becker": {
            "status": "Difficult Transfer",
            "estimated_fee": "€35M"
        },

        "Keylor Navas": {
            "status": "Free Agent",
            "estimated_fee": "Free"
        },

        "Dayot Upamecano": {
            "status": "Available",
            "estimated_fee": "€50M"
        },

        "Antonio Rudiger": {
            "status": "Not for Sale",
            "estimated_fee": "€40M"
        },

        "Marc Guehi": {
            "status": "Available",
            "estimated_fee": "€45M"
        },

        "Alphonso Davies": {
            "status": "Difficult Transfer",
            "estimated_fee": "€60M"
        },

        "Frenkie de Jong": {
            "status": "Available",
            "estimated_fee": "€70M"
        },

        "Bernardo Silva": {
            "status": "Available",
            "estimated_fee": "€60M"
        },

        "Casemiro": {
            "status": "Available",
            "estimated_fee": "€15M"
        },

        "Vitinha": {
            "status": "Not for Sale",
            "estimated_fee": "€75M"
        },

        "Victor Osimhen": {
            "status": "Available",
            "estimated_fee": "€75M"
        },

        "Alexander Isak": {
            "status": "Difficult Transfer",
            "estimated_fee": "€100M"
        },

        "Dusan Vlahovic": {
            "status": "Available",
            "estimated_fee": "€45M"
        },

        "Julian Alvarez": {
            "status": "Not for Sale",
            "estimated_fee": "€90M"
        },

        "Anthony Gordon": {
            "status": "Available",
            "estimated_fee": "€65M"
        }
    }

    player = availability.get(player_name)

    if player is None:
        return f"Player '{player_name}' not found."

    status = player["status"]
    fee = player["estimated_fee"]

    if status == "Free Agent":
        return f"{player_name} is a FREE AGENT and can be signed without a transfer fee."

    if status == "Available":
        return f"{player_name} is AVAILABLE for transfer. Estimated fee: {fee}."

    if status == "Difficult Transfer":
        return f"{player_name} could be signed, but negotiations will be difficult. Estimated fee: {fee}."

    return f"{player_name} is currently NOT FOR SALE."


# ─────────────────────────────────────────────
# TOOL REGISTRY
# ─────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "search_players": search_players,
    "get_player_details": get_player_details,
    "check_availability": check_availability,
}


# ─────────────────────────────────────────────
# TOOL DEFINITIONS
# ─────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_players",
            "description": (
                "Search players by position. "
                "Supported positions: goalkeeper, defender, midfielder, striker."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "position": {
                        "type": "string"
                    }
                },
                "required": ["position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_player_details",
            "description": (
                "Get detailed information about a player including "
                "club, transfer value, goals, assists, defensive stats, "
                "goalkeeping stats, and other performance metrics."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string"
                    }
                },
                "required": ["player_name"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check whether a player is available for transfer, is a free agent, or is not for sale.",
            "parameters": {
                "type": "object",
                "properties": {
                    "player_name": {
                        "type": "string"
                    }
                },
                "required": ["player_name"]
            }
        }
    }
]


# ─────────────────────────────────────────────
# AGENT
# ─────────────────────────────────────────────

class TransferAgent:

    def __init__(self):
        self.system = (
            "You are a professional football scouting and transfer assistant. "
            "Help users discover players, analyze their performance statistics, "
            "check transfer availability, estimate transfer fees, and compare players. "
            "Use the available tools whenever player information, statistics, "
            "or transfer status is required. "
            "Always check a player's availability before recommending a transfer target. "
            "Provide concise, accurate, and data-driven recommendations."
        )

    def run(self, user_message: str) -> str:
        messages = [
            {
                "role": "system",
                "content": self.system
            },
            {
                "role": "user",
                "content": user_message
            }
        ]

        print(f"\nUser: {user_message}")

        while True:
            response = chat(
                model="qwen2:7b",   
                messages=messages,
                tools=TOOLS
            )
            message = response["message"]

            # Final answer
            if not message.get("tool_calls"):
                return message["content"]

            # Execute tool calls
            for tool_call in message["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                arguments = tool_call["function"]["arguments"]
                print(f"\n→ Calling: {tool_name}({arguments})")
                result = TOOL_FUNCTIONS[tool_name](**arguments)
                print(f"← Result: {result}")
                messages.append(message)
                messages.append({
                    "role": "tool",
                    "content": result
                })


# ─────────────────────────────────────────────
# DEMO
# ─────────────────────────────────────────────

if __name__ == "__main__":
    agent = TransferAgent()

    queries = [
        "I'm looking for a world-class striker. What options do you have?",
        "Can you give me the detailed statistics and scouting report for Victor Osimhen?",
        "Is Alexander Isak available for transfer, and what would be the expected transfer fee?"
    ]

    for query in queries:
        answer = agent.run(query)
        print(f"\nAgent: {answer}")
        print("-" * 60)