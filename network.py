"""
Lightweight TCP networking for the RTS chess game.

Protocol: length-prefixed JSON messages.
    [4 bytes big-endian length][UTF-8 JSON payload]

Server is authoritative — it runs the simulation and broadcasts state.
Client sends only input events (move, stop).
"""

import json
import socket
import struct
import threading


HEADER = 4          # 4-byte length prefix
PORT = 5555
SYNC_HZ = 20       # state broadcasts per second


# -- helpers -----------------------------------------------------------------

def _send(sock, obj):
    """Send a JSON-serialisable object with a length prefix."""
    data = json.dumps(obj).encode("utf-8")
    sock.sendall(struct.pack("!I", len(data)) + data)


def _recv(sock):
    """Receive one length-prefixed JSON message.  Returns dict or None."""
    raw_len = _recvall(sock, HEADER)
    if raw_len is None:
        return None
    msg_len = struct.unpack("!I", raw_len)[0]
    if msg_len > 10_000_000:          # sanity cap
        return None
    raw = _recvall(sock, msg_len)
    if raw is None:
        return None
    return json.loads(raw.decode("utf-8"))


def _recvall(sock, n):
    buf = b""
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except (ConnectionResetError, ConnectionAbortedError, OSError):
            return None
        if not chunk:
            return None
        buf += chunk
    return buf


# -- serialisation -----------------------------------------------------------

def piece_to_dict(p):
    return {
        "color": p.color,
        "name": p.name,
        "col": p.col,
        "row": p.row,
        "hp": p.hp,
        "max_hp": p.max_hp,
        "alive": p.alive,
        "moving": p.moving,
        "target_col": p.target_col,
        "target_row": p.target_row,
        "pixel_x": p.pixel_x,
        "pixel_y": p.pixel_y,
        "origin_col": p.origin_col,
        "origin_row": p.origin_row,
        "knight_phase": p.knight_phase,
        "knight_alpha": p.knight_alpha,
        "knight_dest_alpha": p.knight_dest_alpha,
        "knight_timer": p.knight_timer,
        "knight_duration": p.knight_duration,
        "path": p.path,
        "path_index": p.path_index,
        "waiting": p.waiting,
        "being_attacked": p.being_attacked,
        "has_moved": p.has_moved,
    }


def apply_state(pieces, state_list):
    """Overwrite every field of each Piece from the server snapshot."""
    for i, d in enumerate(state_list):
        if i >= len(pieces):
            break
        p = pieces[i]
        p.color = d["color"]
        p.name = d["name"]
        p.col = d["col"]
        p.row = d["row"]
        p.hp = d["hp"]
        p.max_hp = d["max_hp"]
        p.alive = d["alive"]
        p.moving = d["moving"]
        p.target_col = d["target_col"]
        p.target_row = d["target_row"]
        p.pixel_x = d["pixel_x"]
        p.pixel_y = d["pixel_y"]
        p.origin_col = d["origin_col"]
        p.origin_row = d["origin_row"]
        p.knight_phase = d["knight_phase"]
        p.knight_alpha = d["knight_alpha"]
        p.knight_dest_alpha = d["knight_dest_alpha"]
        p.knight_timer = d["knight_timer"]
        p.knight_duration = d["knight_duration"]
        p.path = [tuple(t) for t in d["path"]]
        p.path_index = d["path_index"]
        p.waiting = d["waiting"]
        p.being_attacked = d.get("being_attacked", False)
        p.has_moved = d["has_moved"]
        # attack_target is a reference — can't serialise; server is
        # authoritative for combat anyway.
        p.attack_target = None


# -- Server ------------------------------------------------------------------

class Server:
    """Runs on the host (white player).  Accepts one client (black)."""

    def __init__(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("0.0.0.0", PORT))
        self.sock.listen(1)
        self.client = None
        self.connected = False
        self.incoming = []          # list of dicts from client
        self._lock = threading.Lock()
        self._stop = False

    def wait_for_client(self):
        """Block until a client connects (call before game loop)."""
        print(f"[server] Listening on port {PORT} ...")
        self.client, addr = self.sock.accept()
        self.client.settimeout(0.5)
        self.connected = True
        print(f"[server] Client connected from {addr}")
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        while not self._stop:
            msg = _recv(self.client)
            if msg is None:
                self.connected = False
                break
            with self._lock:
                self.incoming.append(msg)

    def get_messages(self):
        with self._lock:
            msgs = list(self.incoming)
            self.incoming.clear()
        return msgs

    def send_state(self, pieces, game_over, winner):
        if not self.connected:
            return
        payload = {
            "type": "state",
            "pieces": [piece_to_dict(p) for p in pieces],
            "game_over": game_over,
            "winner": winner,
        }
        try:
            _send(self.client, payload)
        except OSError:
            self.connected = False

    def close(self):
        self._stop = True
        if self.client:
            self.client.close()
        self.sock.close()


# -- Client ------------------------------------------------------------------

class Client:
    """Runs on the joining player (black)."""

    def __init__(self, host):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.host = host
        self.connected = False
        self.incoming = []
        self._lock = threading.Lock()
        self._stop = False

    def connect(self):
        print(f"[client] Connecting to {self.host}:{PORT} ...")
        self.sock.connect((self.host, PORT))
        self.sock.settimeout(0.5)
        self.connected = True
        print("[client] Connected!")
        t = threading.Thread(target=self._recv_loop, daemon=True)
        t.start()

    def _recv_loop(self):
        while not self._stop:
            msg = _recv(self.sock)
            if msg is None:
                self.connected = False
                break
            with self._lock:
                self.incoming.append(msg)

    def get_messages(self):
        with self._lock:
            msgs = list(self.incoming)
            self.incoming.clear()
        return msgs

    def send_move(self, piece_index, target_col, target_row):
        if not self.connected:
            return
        try:
            _send(self.sock, {
                "type": "move",
                "piece_index": piece_index,
                "target_col": target_col,
                "target_row": target_row,
            })
        except OSError:
            self.connected = False

    def send_stop(self, piece_index):
        if not self.connected:
            return
        try:
            _send(self.sock, {
                "type": "stop",
                "piece_index": piece_index,
            })
        except OSError:
            self.connected = False

    def close(self):
        self._stop = True
        self.sock.close()
