import socket
import json
import struct
import copy
import random
import math

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

def pos_to_coord(pos):
    return pos // 8, pos % 8

def coord_to_pos(row, col):
    return row * 8 + col

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

def count_stable_discs(board, player):
    """Count stable discs - pieces that can never be flipped"""
    stable = [False] * 64
    opponent = get_opponent(player)
    
    # Check corners first
    corners = [0, 7, 56, 63]
    for corner in corners:
        if board[corner] == player:
            stable[corner] = True
    
    # Check edges connected to stable corners
    directions = [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]
    
    changed = True
    while changed:
        changed = False
        for pos in range(64):
            if stable[pos] or board[pos] != player:
                continue
                
            row, col = pos_to_coord(pos)
            is_stable = False
            
            # Check if surrounded by stable pieces in any direction
            for dr, dc in directions:
                line_stable = True
                # Check both directions along this line
                for direction in [1, -1]:
                    r, c = row + dr * direction, col + dc * direction
                    while 0 <= r < 8 and 0 <= c < 8:
                        pos_check = coord_to_pos(r, c)
                        if board[pos_check] == opponent:
                            line_stable = False
                            break
                        if not stable[pos_check] and board[pos_check] == player:
                            line_stable = False
                            break
                        r, c = r + dr * direction, c + dc * direction
                
                if line_stable:
                    is_stable = True
                    break
            
            if is_stable:
                stable[pos] = True
                changed = True
    
    return sum(1 for i in range(64) if stable[i])

def evaluate_mobility(board, player):
    """Evaluate mobility - number of legal moves"""
    player_moves = len(get_legal_moves(board, player))
    opponent_moves = len(get_legal_moves(board, get_opponent(player)))
    
    if player_moves + opponent_moves == 0:
        return 0
    return (player_moves - opponent_moves) / (player_moves + opponent_moves) * 100

def evaluate_corner_strategy(board, player):
    """Advanced corner and edge evaluation"""
    opponent = get_opponent(player)
    score = 0
    
    # Corner positions and their adjacent dangerous squares
    corner_data = {
        0: [1, 8, 9],      # top-left
        7: [6, 15, 14],    # top-right  
        56: [48, 49, 57],  # bottom-left
        63: [54, 55, 62]   # bottom-right
    }
    
    for corner, adjacent in corner_data.items():
        if board[corner] == player:
            score += 100  # Corner captured
        elif board[corner] == opponent:
            score -= 100
        elif board[corner] == 'E':
            # Penalize giving opponent access to corners
            for adj in adjacent:
                if board[adj] == player:
                    score -= 20  # X-squares penalty
                elif board[adj] == opponent:
                    score += 20   # Opponent in X-square is bad for them
    
    # Edge control (excluding corners and X-squares)
    edges = [1, 2, 3, 4, 5, 6,    # top edge
             8, 16, 24, 32, 40, 48, # left edge  
             15, 23, 31, 39, 47, 55, # right edge
             57, 58, 59, 60, 61, 62] # bottom edge
    
    edge_score = 0
    for pos in edges:
        if board[pos] == player:
            edge_score += 5
        elif board[pos] == opponent:
            edge_score -= 5
    
    return score + edge_score

def evaluate_parity(board, player):
    """Parity - who gets the last move in empty regions"""
    empty_count = sum(1 for cell in board if cell == 'E')
    # Parity is good if we're likely to get the last move
    return 5 if empty_count % 2 == 0 else -5

def get_game_phase(board):
    """Determine game phase based on empty squares"""
    empty = sum(1 for cell in board if cell == 'E')
    if empty > 44:
        return 'opening'
    elif empty > 20:
        return 'midgame'  
    else:
        return 'endgame'

def evaluate_board_advanced(board, player):
    """Advanced evaluation function considering multiple strategic factors"""
    opponent = get_opponent(player)
    phase = get_game_phase(board)
    
    # Basic piece count
    player_count = sum(1 for cell in board if cell == player)
    opponent_count = sum(1 for cell in board if cell == opponent)
    
    if phase == 'opening':
        # Opening: Focus on mobility and avoid edges, minimize piece count
        mobility_score = evaluate_mobility(board, player) * 3
        corner_score = evaluate_corner_strategy(board, player) * 2
        piece_score = (opponent_count - player_count) * 2  # Fewer pieces better in opening
        parity_score = evaluate_parity(board, player)
        
        return mobility_score + corner_score + piece_score + parity_score
        
    elif phase == 'midgame':
        # Midgame: Balance between mobility, corners, and stability
        mobility_score = evaluate_mobility(board, player) * 2
        corner_score = evaluate_corner_strategy(board, player) * 3
        stable_score = (count_stable_discs(board, player) - count_stable_discs(board, opponent)) * 10
        piece_score = (player_count - opponent_count)
        
        return mobility_score + corner_score + stable_score + piece_score
        
    else:  # endgame
        # Endgame: Maximize piece count and stability
        piece_score = (player_count - opponent_count) * 10
        stable_score = (count_stable_discs(board, player) - count_stable_discs(board, opponent)) * 15
        corner_score = evaluate_corner_strategy(board, player) * 2
        
        return piece_score + stable_score + corner_score

def order_moves(board, moves, player):
    """Order moves by their immediate evaluation to improve alpha-beta pruning"""
    move_scores = []
    for move in moves:
        new_board = simulate_move(board.copy(), int(move), player)
        score = evaluate_board_advanced(new_board, player)
        move_scores.append((score, move))
    
    # Sort by score in descending order (best moves first)
    move_scores.sort(reverse=True)
    return [move for score, move in move_scores]

def minimax_advanced(board, depth, maximizing, player, alpha, beta, original_player):
    """Advanced minimax with better evaluation and move ordering"""
    legal_moves = get_legal_moves(board, player if maximizing else get_opponent(player))
    
    if depth == 0 or not legal_moves:
        return evaluate_board_advanced(board, original_player), None
    
    # Order moves for better pruning
    if legal_moves:
        legal_moves = order_moves(board, legal_moves, player if maximizing else get_opponent(player))
    
    best_move = legal_moves[0] if legal_moves else None
    
    if maximizing:
        max_eval = float('-inf')
        for move in legal_moves:
            new_board = simulate_move(board.copy(), int(move), player)
            eval_score, _ = minimax_advanced(new_board, depth - 1, False, player, alpha, beta, original_player)
            
            if eval_score > max_eval:
                max_eval = eval_score
                best_move = move
                
            alpha = max(alpha, eval_score)
            if beta <= alpha:
                break  # Alpha-beta pruning
                
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move in legal_moves:
            new_board = simulate_move(board.copy(), int(move), get_opponent(player))
            eval_score, _ = minimax_advanced(new_board, depth - 1, True, player, alpha, beta, original_player)
            
            if eval_score < min_eval:
                min_eval = eval_score
                best_move = move
                
            beta = min(beta, eval_score)
            if beta <= alpha:
                break  # Alpha-beta pruning
                
        return min_eval, best_move

def get_adaptive_depth(board, moves_count):
    """Adjust search depth based on game state"""
    empty = sum(1 for cell in board if cell == 'E')
    
    if empty <= 12:  # Endgame - search deeper
        return min(8, empty)
    elif empty <= 20:  # Late midgame
        return 6
    elif len(moves_count) <= 8:  # Few moves available
        return 5
    else:  # Opening/early midgame
        return 4

def handle_command(command):
    possible = command.get("possibleMoves", "").strip()
    if not possible:
        return "-1"
    
    possible_moves = possible.split(",")
    board = parse_board(command["boardStatus"])
    player = command["player"]
    
    # Use adaptive depth
    depth = get_adaptive_depth(board, possible_moves)
    
    # Use advanced minimax
    _, best = minimax_advanced(board, depth=depth, maximizing=True, player=player,
                             alpha=float('-inf'), beta=float('inf'), original_player=player)
    
    return str(best) if best else "-1"

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((HOST, PORT))
        print("Connected to Gameleon server with Advanced Strategy Bot.")

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
                print(f"Made move: {move}")

            elif dtype == "acknowledge":
                print(f"Acknowledgement: {json_data['acknowledge']} - {json_data.get('reason', '')}")

            elif dtype == "result":
                print(f"Game Over: {json_data['gameResult']}")

if __name__ == "__main__":
    main()