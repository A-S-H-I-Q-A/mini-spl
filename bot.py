import socket
import json
import struct
import copy
import random

HOST = '127.0.0.1'
PORT = 2024

def recv_msg(sock):
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    return recvall(sock, msglen).decode()

def recvall(sock, n):
    data = b''
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data += packet
    return data

def send_json(sock, obj):
    message = json.dumps(obj)
    message_bytes = message.encode()
    msg_len = struct.pack('>I', len(message_bytes))
    sock.sendall(msg_len + message_bytes)

def parse_board(status_str):
    return status_str.split(',')

def get_opponent(player):
    return 'P2' if player == 'P1' else 'P1'

def flip_discs(board, move, player):
    opponent = get_opponent(player)
    directions = [-1, 1, -8, 8, -9, -7, 7, 9]
    flips = []

    def on_board(pos):
        return 0 <= pos < 64

    def same_row(a, b):
        return a // 8 == b // 8

    for d in directions:
        temp = []
        cur = move + d
        while on_board(cur) and board[cur] == opponent:
            if d in [-1, 1] and not same_row(cur, cur - d):
                break
            temp.append(cur)
            cur += d
        if on_board(cur) and board[cur] == player:
            flips.extend(temp)

    for f in flips:
        board[f] = player
    board[move] = player
    return board


def simulate_move(board, move, player):
    new_board = board.copy()
    flip_discs(new_board, move, player)
    return new_board

def evaluate_board(board, player):
    opponent = get_opponent(player)
    corners = [0, 7, 56, 63]
    edges = [1, 2, 3, 4, 5, 6,
             8, 16, 24, 32, 40, 48,
             15, 23, 31, 39, 47, 55,
             57, 58, 59, 60, 61, 62]

    empty_count = board.count('E')
    is_endgame = empty_count <= 16
    is_midgame = empty_count <= 32

    score = 0
    player_pieces = 0
    opponent_pieces = 0

    for i in range(64):
        if board[i] == player or board[i] == opponent:
            current = board[i]
            value = 1
            if i in corners:
                value += 40 if is_endgame else 30 if is_midgame else 20
            elif i in edges:
                value += 8 if is_endgame else 5 if is_midgame else 3
            elif i in [1, 8, 9] and board[0] == current:
                value += 4
            elif i in [6, 14, 15] and board[7] == current:
                value += 4
            elif i in [48, 49, 57] and board[56] == current:
                value += 4
            elif i in [54, 55, 62] and board[63] == current:
                value += 4
            elif i in [1, 8, 9, 6, 14, 15, 48, 49, 57, 54, 55, 62]:
                value -= 2 if not is_endgame else -1

            if current == player:
                player_pieces += 1
                score += value
            else:
                opponent_pieces += 1
                score -= value

    if is_endgame:
        score += (player_pieces - opponent_pieces) * 2
    return score

def get_legal_moves(board, player):
    opponent = get_opponent(player)
    directions = [-1, 1, -8, 8, -9, -7, 7, 9]
    legal = set()

    def on_board(pos):
        return 0 <= pos < 64

    for i, cell in enumerate(board):
        if cell != 'E':
            continue
        for d in directions:
            cur = i + d
            path = []
            while on_board(cur) and board[cur] == opponent:
                if d in [-1, 1] and (cur // 8 != i // 8):
                    break
                path.append(cur)
                cur += d
            if path and on_board(cur) and board[cur] == player:
                legal.add(str(i))
                break
    return list(legal)

def minimax(board, depth, maximizing, player, legal_moves, alpha, beta):
    if depth == 0 or not legal_moves:
        return evaluate_board(board, player), None

    empty_count = board.count('E')
    is_endgame = empty_count <= 12

    best_move = legal_moves[0]
    if maximizing:
        max_eval = float('-inf')
        for move in legal_moves:
            new_board = simulate_move(board, int(move), player)
            opponent_moves = get_legal_moves(new_board, get_opponent(player))
            eval_score, _ = minimax(new_board, depth - 1, False, player, opponent_moves, alpha, beta)
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break
        return max_eval, best_move
    else:
        if len(legal_moves) > 6 and not is_endgame:
            quick_scores = []
            for move in legal_moves:
                new_board = simulate_move(board, int(move), get_opponent(player))
                quick_score = evaluate_board(new_board, get_opponent(player))
                quick_scores.append((quick_score, move))
            quick_scores.sort(reverse=True)
            legal_moves = [move for _, move in quick_scores[:6]]

        move_scores = []
        for move in legal_moves:
            new_board = simulate_move(board, int(move), get_opponent(player))
            my_moves = get_legal_moves(new_board, player)
            eval_score, _ = minimax(new_board, depth - 1, True, player, my_moves, alpha, beta)
            move_scores.append((eval_score, move))
            beta = min(beta, eval_score)
            if beta <= alpha:
                break

        move_scores.sort()

        if is_endgame:
            return move_scores[0]

        rand_val = random.random()
        if rand_val < 0.7 or len(move_scores) == 1:
            return move_scores[0]
        elif rand_val < 0.9 and len(move_scores) >= 2:
            return move_scores[1]
        elif len(move_scores) >= 3:
            return move_scores[2]
        else:
            return move_scores[0]

def handle_command(command):
    possible = command.get("possibleMoves", "").strip()
    if not possible:
        return "-1"
    possible_moves = possible.split(",")
    board = parse_board(command["boardStatus"])
    player = command["player"]
    
    # Reduce depth if too many moves to ensure speed
    depth = 5 if len(possible_moves) > 8 else 
    
    _, best = minimax(board, depth=depth, maximizing=True, player=player, legal_moves=possible_moves,
                      alpha=float('-inf'), beta=float('inf'))
    return str(best) if best else "-1"

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected to Gameleon server.")

        while True:
            data = recv_msg(s)
            if not data:
                print("Connection closed by server.")
                break

            try:
                json_data = json.loads(data)
            except json.JSONDecodeError:
                print("Invalid JSON received.")
                continue

            dtype = json_data.get("dataType", "")
            if dtype == "command":
                move = handle_command(json_data)
                response = {
                    "dataType": "response",
                    "move": move
                }
                send_json(s, response)

            elif dtype == "acknowledge":
                print(f"Acknowledgement: {json_data['acknowledge']} - {json_data.get('reason', '')}")

            elif dtype == "result":
                print(f"Game Over: {json_data['gameResult']}")

if __name__ == "__main__":
    main()