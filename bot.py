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
    edges = [1, 2, 3, 4, 5, 6,      # top edge
             8, 16, 24, 32, 40, 48,  # left edge  
             15, 23, 31, 39, 47, 55, # right edge
             57, 58, 59, 60, 61, 62] # bottom edge
    
    # Count empty squares to determine game phase
    empty_count = board.count('E')
    is_endgame = empty_count <= 16  # Last quarter of game
    is_midgame = empty_count <= 32  # Last half of game
    
    score = 0
    player_pieces = 0
    opponent_pieces = 0

    for i in range(64):
        if board[i] == player:
            player_pieces += 1
            base_score = 1
            
            # Corner control - valuable but not overwhelming
            if i in corners:
                if is_endgame:
                    base_score += 20  # Reduced from 50
                elif is_midgame:
                    base_score += 15  # Reduced from 35
                else:
                    base_score += 12  # Reduced from 25
            
            # Edge control - moderate bonus
            elif i in edges:
                if is_endgame:
                    base_score += 6   # Reduced from 15
                elif is_midgame:
                    base_score += 4   # Reduced from 8
                else:
                    base_score += 2   # Reduced from 3
            
            # Adjacent to corners - less penalty/bonus
            elif i in [1, 8, 9]:  # adjacent to corner 0
                if board[0] == player:
                    base_score += 3  # Reduced from 5
                elif is_endgame:
                    base_score += 1  # Reduced from 2
                else:
                    base_score -= 2  # Reduced penalty from -3
            elif i in [6, 14, 15]:  # adjacent to corner 7
                if board[7] == player:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            elif i in [48, 49, 57]:  # adjacent to corner 56
                if board[56] == player:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            elif i in [54, 55, 62]:  # adjacent to corner 63
                if board[63] == player:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            
            score += base_score
            
        elif board[i] == opponent:
            opponent_pieces += 1
            base_score = 1
            
            # Same logic for opponent (subtract their advantages)
            if i in corners:
                if is_endgame:
                    base_score += 20
                elif is_midgame:
                    base_score += 15
                else:
                    base_score += 12
            elif i in edges:
                if is_endgame:
                    base_score += 6
                elif is_midgame:
                    base_score += 4
                else:
                    base_score += 2
            elif i in [1, 8, 9]:
                if board[0] == opponent:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            elif i in [6, 14, 15]:
                if board[7] == opponent:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            elif i in [48, 49, 57]:
                if board[56] == opponent:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            elif i in [54, 55, 62]:
                if board[63] == opponent:
                    base_score += 3
                elif is_endgame:
                    base_score += 1
                else:
                    base_score -= 2
            
            score -= base_score

    # Endgame bonus: prioritize piece count when few squares left
    if is_endgame:
        score += (player_pieces - opponent_pieces) * 2  # Reduced from 3
    
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
def minimax(board, depth, maximizing, player, legal_moves, alpha, beta):
    if depth == 0 or not legal_moves:
        return evaluate_board(board, player), None

    # Check if we're in endgame for opponent behavior
    empty_count = board.count('E')
    is_endgame = empty_count <= 12  # Last 12 moves - opponent plays optimally

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
        # For opponent moves, only evaluate top 3 options to save time (except endgame)
        if len(legal_moves) > 6 and not is_endgame:
            # Quick evaluation to filter moves
            quick_scores = []
            for move in legal_moves:
                new_board = simulate_move(board, int(move), get_opponent(player))
                quick_score = evaluate_board(new_board, get_opponent(player))
                quick_scores.append((quick_score, move))
            quick_scores.sort(reverse=True)  # Best for opponent first
            legal_moves = [move for _, move in quick_scores[:6]]  # Keep top 6
        
        # Evaluate filtered moves properly
        move_scores = []
        for move in legal_moves:
            new_board = simulate_move(board, int(move), get_opponent(player))
            my_moves = get_legal_moves(new_board, player)
            eval_score, _ = minimax(new_board, depth - 1, True, player, my_moves, alpha, beta)
            move_scores.append((eval_score, move))
            # Early termination for speed
            beta = min(beta, eval_score)
            if beta <= alpha:
                break
        
        move_scores.sort()  # Best opponent moves first (lowest scores for us)
        
        # ENDGAME: Opponent always plays their best move
        if is_endgame:
            return move_scores[0]
        
        # MID-GAME: Opponent chooses: 70% best move, 20% 2nd best, 10% 3rd best
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
    depth = 3 if len(possible_moves) > 8 else 4
    
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