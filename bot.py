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
    """Simulate flipping discs after a move"""
    opponent = get_opponent(player)
    directions = [-1, 1, -8, 8, -9, -7, 7, 9]
    flips = []
    new_board = board.copy()

    def on_board(pos):
        return 0 <= pos < 64

    def same_row(a, b):
        return a // 8 == b // 8

    for d in directions:
        temp = []
        cur = move + d
        
        # Follow direction while finding opponent pieces
        while on_board(cur) and new_board[cur] == opponent:
            if d in [-1, 1] and not same_row(cur, cur - d):
                break
            temp.append(cur)
            cur += d
        
        # If we end on our piece, all pieces in between get flipped
        if on_board(cur) and new_board[cur] == player and temp:
            flips.extend(temp)

    # Apply flips
    for f in flips:
        new_board[f] = player
    new_board[move] = player
    return new_board

def simulate_move(board, move, player):
    """Simulate a move and return the resulting board"""
    return flip_discs(board, move, player)

def count_stable_discs(board, player):
    """Count stable discs - pieces that can never be flipped"""
    stable = [False] * 64
    opponent = get_opponent(player)
    
    # Check corners first
    corners = [0, 7, 56, 63]
    for corner in corners:
        if board[corner] == player:
            stable[corner] = True
    
    # Iteratively find stable pieces connected to already stable pieces
    changed = True
    iterations = 0
    while changed and iterations < 10:  # Prevent infinite loops
        changed = False
        iterations += 1
        
        for pos in range(64):
            if stable[pos] or board[pos] != player:
                continue
                
            row, col = pos_to_coord(pos)
            is_stable = False
            
            # Check if this piece is stable in any direction
            directions = [(0, 1), (1, 0), (1, 1), (1, -1)]  # horizontal, vertical, diagonal
            
            for dr, dc in directions:
                both_directions_stable = True
                
                # Check both directions along this line
                for direction_multiplier in [1, -1]:
                    r, c = row + dr * direction_multiplier, col + dc * direction_multiplier
                    found_stable_or_edge = False
                    
                    while 0 <= r < 8 and 0 <= c < 8:
                        pos_check = coord_to_pos(r, c)
                        if board[pos_check] == opponent:
                            both_directions_stable = False
                            break
                        if stable[pos_check] and board[pos_check] == player:
                            found_stable_or_edge = True
                            break
                        if board[pos_check] == 'E':
                            both_directions_stable = False
                            break
                        r, c = r + dr * direction_multiplier, c + dc * direction_multiplier
                    
                    # If we hit the edge without finding opponent, that's stable too
                    if not (0 <= r < 8 and 0 <= c < 8):
                        found_stable_or_edge = True
                    
                    if not found_stable_or_edge:
                        both_directions_stable = False
                        break
                
                if both_directions_stable:
                    is_stable = True
                    break
            
            if is_stable:
                stable[pos] = True
                changed = True
    
    return sum(1 for i in range(64) if stable[i])

def get_valid_moves_for_player(board, player):
    """Calculate valid moves for a player - for simulation purposes only"""
    opponent = get_opponent(player)
    directions = [-1, 1, -8, 8, -9, -7, 7, 9]
    valid_moves = set()

    def on_board(pos):
        return 0 <= pos < 64

    def same_row(a, b):
        return a // 8 == b // 8

    for i, cell in enumerate(board):
        if cell != 'E':
            continue
            
        for d in directions:
            cur = i + d
            found_opponent = False
            
            # Look for opponent pieces in this direction
            while on_board(cur) and board[cur] == opponent:
                if d in [-1, 1] and not same_row(cur, cur - d):
                    break
                found_opponent = True
                cur += d
            
            # If we found opponent pieces and end on our piece, this is valid
            if found_opponent and on_board(cur) and board[cur] == player:
                valid_moves.add(i)
                break
    
    return list(map(str, valid_moves))

def evaluate_mobility(board, player):
    """Evaluate mobility - number of legal moves"""
    player_moves = len(get_valid_moves_for_player(board, player))
    opponent_moves = len(get_valid_moves_for_player(board, get_opponent(player)))
    
    if player_moves + opponent_moves == 0:
        return 0
    return (player_moves - opponent_moves) / (player_moves + opponent_moves) * 100

def evaluate_corner_and_edge_strategy(board, player):
    """Advanced corner and edge evaluation"""
    opponent = get_opponent(player)
    score = 0
    
    # Corner positions and their dangerous X-squares
    corner_data = {
        0: [1, 8, 9],      # top-left corner and its X-squares
        7: [6, 15, 14],    # top-right corner and its X-squares  
        56: [48, 49, 57],  # bottom-left corner and its X-squares
        63: [54, 55, 62]   # bottom-right corner and its X-squares
    }
    
    for corner, x_squares in corner_data.items():
        if board[corner] == player:
            score += 100  # Corner captured - huge bonus
        elif board[corner] == opponent:
            score -= 100  # Opponent has corner - huge penalty
        elif board[corner] == 'E':
            # Corner is empty - evaluate X-square danger
            for x_square in x_squares:
                if board[x_square] == player:
                    score -= 25  # We're in X-square - very dangerous
                elif board[x_square] == opponent:
                    score += 10   # Opponent in X-square - good for us
    
    # Edge evaluation (excluding corners and X-squares)
    safe_edges = []
    # Top and bottom edges (excluding corners and X-squares)
    for i in [2, 3, 4, 5]:
        safe_edges.extend([i, i + 56])  # top and bottom
    # Left and right edges (excluding corners and X-squares)  
    for i in [16, 24, 32, 40]:
        safe_edges.extend([i, i + 7])  # left and right
    
    edge_score = 0
    for pos in safe_edges:
        if board[pos] == player:
            edge_score += 5
        elif board[pos] == opponent:
            edge_score -= 5
    
    return score + edge_score

def evaluate_parity(board):
    """Parity evaluation - who gets the last move"""
    empty_count = sum(1 for cell in board if cell == 'E')
    # Even number of empty squares is generally better
    return 3 if empty_count % 2 == 0 else -3

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
    """Advanced evaluation considering multiple strategic factors"""
    opponent = get_opponent(player)
    phase = get_game_phase(board)
    
    # Basic piece count
    player_count = sum(1 for cell in board if cell == player)
    opponent_count = sum(1 for cell in board if cell == opponent)
    
    if phase == 'opening':
        # Opening: Prioritize mobility, avoid X-squares, prefer fewer pieces
        mobility_score = evaluate_mobility(board, player) * 4
        corner_score = evaluate_corner_and_edge_strategy(board, player) * 2
        piece_score = (opponent_count - player_count) * 1  # Fewer pieces better in opening
        parity_score = evaluate_parity(board)
        
        return mobility_score + corner_score + piece_score + parity_score
        
    elif phase == 'midgame':
        # Midgame: Balance all factors
        mobility_score = evaluate_mobility(board, player) * 2
        corner_score = evaluate_corner_and_edge_strategy(board, player) * 3
        stable_score = (count_stable_discs(board, player) - count_stable_discs(board, opponent)) * 8
        piece_score = (player_count - opponent_count) * 1
        parity_score = evaluate_parity(board)
        
        return mobility_score + corner_score + stable_score + piece_score + parity_score
        
    else:  # endgame
        # Endgame: Maximize piece count and stability
        piece_score = (player_count - opponent_count) * 15
        stable_score = (count_stable_discs(board, player) - count_stable_discs(board, opponent)) * 10
        corner_score = evaluate_corner_and_edge_strategy(board, player) * 2
        
        return piece_score + stable_score + corner_score

def order_moves(board, moves, player):
    """Order moves by their immediate evaluation for better alpha-beta pruning"""
    if not moves:
        return moves
        
    move_scores = []
    for move_str in moves:
        try:
            move = int(move_str)
            new_board = simulate_move(board, move, player)
            score = evaluate_board_advanced(new_board, player)
            move_scores.append((score, move_str))
        except (ValueError, IndexError):
            # Skip invalid moves
            continue
    
    # Sort by score in descending order (best moves first)
    move_scores.sort(reverse=True)
    return [move for score, move in move_scores]

def minimax_advanced(board, depth, maximizing, player, alpha, beta, original_player, possible_moves=None):
    """Advanced minimax with better evaluation and move ordering"""
    
    if maximizing:
        current_player = original_player
        if possible_moves is None:
            legal_moves = get_valid_moves_for_player(board, current_player)
        else:
            legal_moves = possible_moves
    else:
        current_player = get_opponent(original_player)
        legal_moves = get_valid_moves_for_player(board, current_player)
    
    if depth == 0 or not legal_moves:
        return evaluate_board_advanced(board, original_player), None
    
    # Order moves for better pruning
    legal_moves = order_moves(board, legal_moves, current_player)
    
    best_move = legal_moves[0] if legal_moves else None
    
    if maximizing:
        max_eval = float('-inf')
        for move_str in legal_moves:
            try:
                move = int(move_str)
                new_board = simulate_move(board, move, current_player)
                eval_score, _ = minimax_advanced(new_board, depth - 1, False, player, alpha, beta, original_player)
                
                if eval_score > max_eval:
                    max_eval = eval_score
                    best_move = move_str
                    
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break  # Alpha-beta pruning
            except (ValueError, IndexError):
                continue
                
        return max_eval, best_move
    else:
        min_eval = float('inf')
        for move_str in legal_moves:
            try:
                move = int(move_str)
                new_board = simulate_move(board, move, current_player)
                eval_score, _ = minimax_advanced(new_board, depth - 1, True, player, alpha, beta, original_player)
                
                if eval_score < min_eval:
                    min_eval = eval_score
                    best_move = move_str
                    
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break  # Alpha-beta pruning
            except (ValueError, IndexError):
                continue
                
        return min_eval, best_move

def get_adaptive_depth(board, moves_available):
    """Adjust search depth based on game state"""
    empty = sum(1 for cell in board if cell == 'E')
    
    if empty <= 10:  # Endgame - search very deep
        return min(empty, 8)
    elif empty <= 15:  # Late midgame
        return 6
    elif len(moves_available) <= 5:  # Few moves available - can afford deeper search
        return 5
    else:  # Opening/early midgame
        return 4

def handle_command(command):
    """Handle game command and return best move"""
    try:
        # Parse possible moves
        possible = command.get("possibleMoves", "").strip()
        if not possible:
            return "-1"
        
        possible_moves = [move.strip() for move in possible.split(",") if move.strip()]
        if not possible_moves:
            return "-1"
            
        # Parse board
        board_status = command.get("boardStatus", "")
        if not board_status:
            return "-1"
            
        board = parse_board(board_status)
        if len(board) != 64:
            return "-1"
            
        player = command.get("player", "")
        if player not in ["P1", "P2"]:
            return "-1"
        
        # If only one move available, take it
        if len(possible_moves) == 1:
            return possible_moves[0]
        
        # Use adaptive depth based on game state
        depth = get_adaptive_depth(board, possible_moves)
        
        # Use advanced minimax to find best move
        _, best_move = minimax_advanced(
            board, 
            depth=depth, 
            maximizing=True, 
            player=player,
            alpha=float('-inf'), 
            beta=float('inf'), 
            original_player=player,
            possible_moves=possible_moves
        )
        
        # Validate the move is in possible moves
        if best_move and best_move in possible_moves:
            return str(best_move)
        else:
            # Fallback to first available move
            return possible_moves[0]
            
    except Exception as e:
        print(f"Error in handle_command: {e}")
        # Return first possible move as fallback
        possible = command.get("possibleMoves", "").strip()
        if possible:
            moves = [move.strip() for move in possible.split(",") if move.strip()]
            if moves:
                return moves[0]
        return "-1"

def main():
    try:
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
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON received: {e}")
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
                    ack = json_data.get("acknowledge", "")
                    reason = json_data.get("reason", "")
                    print(f"Acknowledgement: {ack}")
                    if reason:
                        print(f"Reason: {reason}")

                elif dtype == "result":
                    result = json_data.get("gameResult", "")
                    print(f"Game Over: {result}")
                    break
                    
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    main()