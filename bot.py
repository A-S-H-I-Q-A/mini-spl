import socket
import json
import random
import copy

# Heuristic Weights
CORNER_WEIGHT = 40
EDGE_WEIGHT = 8
ADJ_CORNER_PENALTY = -2
MOBILITY_WEIGHT = 5
FRONTIER_PENALTY = 2

DIRECTIONS = [-1, 1, -8, 8, -9, -7, 7, 9]
CORNER_POSITIONS = [0, 7, 56, 63]
ADJACENT_TO_CORNERS = [1, 8, 9, 6, 14, 15, 48, 49, 54, 55, 62, 47]

def parse_board(board_str):
    return list(board_str)

def board_to_string(board):
    return ''.join(board)

def get_opponent(player):
    return 'W' if player == 'B' else 'B'

def is_on_board(index):
    return 0 <= index < 64

def valid_move(board, index, player):
    if board[index] != 'E':
        return False
    opponent = get_opponent(player)
    for direction in DIRECTIONS:
        i = index + direction
        found_opponent = False
        while is_on_board(i) and board[i] == opponent:
            found_opponent = True
            if (direction == -1 and i % 8 == 7) or \
               (direction == 1 and i % 8 == 0) or \
               (direction == -9 and i % 8 == 7) or \
               (direction == -7 and i % 8 == 0) or \
               (direction == 7 and i % 8 == 7) or \
               (direction == 9 and i % 8 == 0):
                break
            i += direction
        if is_on_board(i) and board[i] == player and found_opponent:
            return True
    return False

def get_legal_moves(board, player):
    return [i for i in range(64) if valid_move(board, i, player)]

def flip_discs(board, index, player):
    opponent = get_opponent(player)
    flipped = []
    for direction in DIRECTIONS:
        i = index + direction
        discs_to_flip = []
        while is_on_board(i) and board[i] == opponent:
            discs_to_flip.append(i)
            if (direction == -1 and i % 8 == 7) or \
               (direction == 1 and i % 8 == 0) or \
               (direction == -9 and i % 8 == 7) or \
               (direction == -7 and i % 8 == 0) or \
               (direction == 7 and i % 8 == 7) or \
               (direction == 9 and i % 8 == 0):
                break
            i += direction
        if is_on_board(i) and board[i] == player:
            flipped.extend(discs_to_flip)
    for i in flipped:
        board[i] = player

def simulate_move(board, index, player):
    new_board = board.copy()
    new_board[index] = player
    flip_discs(new_board, index, player)
    return new_board

def evaluate_board(board, player):
    opponent = get_opponent(player)
    score = 0
    player_discs = opponent_discs = 0
    mobility = len(get_legal_moves(board, player)) - len(get_legal_moves(board, opponent))

    for i, square in enumerate(board):
        if square == player:
            player_discs += 1
            if i in CORNER_POSITIONS:
                score += CORNER_WEIGHT
            elif i in ADJACENT_TO_CORNERS:
                score += ADJ_CORNER_PENALTY
            elif i % 8 == 0 or i % 8 == 7 or i < 8 or i > 55:
                score += EDGE_WEIGHT
            if any(is_on_board(i + d) and board[i + d] == 'E' for d in DIRECTIONS):
                score -= FRONTIER_PENALTY
        elif square == opponent:
            opponent_discs += 1
            if i in CORNER_POSITIONS:
                score -= CORNER_WEIGHT
            elif i in ADJACENT_TO_CORNERS:
                score -= ADJ_CORNER_PENALTY
            elif i % 8 == 0 or i % 8 == 7 or i < 8 or i > 55:
                score -= EDGE_WEIGHT
            if any(is_on_board(i + d) and board[i + d] == 'E' for d in DIRECTIONS):
                score += FRONTIER_PENALTY

    disc_diff = player_discs - opponent_discs
    score += disc_diff + MOBILITY_WEIGHT * mobility
    return score

def minimax(board, depth, alpha, beta, maximizing, player):
    opponent = get_opponent(player)
    legal_moves = get_legal_moves(board, player if maximizing else opponent)

    if depth == 0 or not legal_moves:
        return evaluate_board(board, player), None

    best_move = None

    if maximizing:
        max_eval = float('-inf')
        for move in legal_moves:
            new_board = simulate_move(board, move, player)
            eval_score, _ = minimax(new_board, depth - 1, alpha, beta, False, player)
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in legal_moves:
            new_board = simulate_move(board, move, opponent)
            eval_score, _ = minimax(new_board, depth - 1, alpha, beta, True, player)
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move

def handle_command(json_data):
    board = parse_board(json_data["board"])
    side = json_data["side"]
    legal_moves = get_legal_moves(board, side)

    if not legal_moves:
        return json.dumps({"response": "pass"})

    depth = 6 if board.count('E') < 20 else 5 if board.count('E') < 40 else 4
    _, best_move = minimax(board, depth, float('-inf'), float('inf'), True, side)

    if best_move is not None:
        return json.dumps({"response": str(best_move)})
    else:
        return json.dumps({"response": str(random.choice(legal_moves))})

def handle_request(json_data):
    dtype = json_data.get("type")
    if dtype == "command":
        return handle_command(json_data)
    else:
        return json.dumps({"response": "invalid"})

def recv_msg(sock):
    data = b""
    while True:
        part = sock.recv(1024)
        if not part:
            break
        data += part
        if b"\n" in part:
            break
    return data.decode().strip()

def main():
    HOST, PORT = "localhost", 12345
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.connect((HOST, PORT))
        sock.sendall(b'{"response": "hello"}\n')

        while True:
            data = recv_msg(sock)
            if not data:
                break
            try:
                json_data = json.loads(data)
                response = handle_request(json_data)
                sock.sendall((response + "\n").encode())
            except Exception as e:
                print(f"Error: {e}")
                break

if __name__ == "__main__":
    main()
