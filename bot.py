import socket
import json
import struct
import copy

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
    score = 0

    for i in range(64):
        if board[i] == player:
            score += 1
            if i in corners:
                score += 25
        elif board[i] == opponent:
            score -= 1
            if i in corners:
                score -= 25
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

    best_move = legal_moves[0]
    if maximizing:
        max_eval = float('-inf')
        for move in legal_moves:
            new_board = simulate_move(board.copy(), int(move), player)
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
        min_eval = float('inf')
        for move in legal_moves:
            new_board = simulate_move(board.copy(), int(move), get_opponent(player))
            my_moves = get_legal_moves(new_board, player)
            eval_score, _ = minimax(new_board, depth - 1, True, player, my_moves, alpha, beta)
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        return min_eval, best_move

def handle_command(command):
    possible = command.get("possibleMoves", "").strip()
    if not possible:
        return "-1"
    possible_moves = possible.split(",")
    board = parse_board(command["boardStatus"])
    player = command["player"]
    _, best = minimax(board, depth=3, maximizing=True, player=player, legal_moves=possible_moves,
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
