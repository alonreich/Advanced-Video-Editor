import json
import zlib

class UndoStack:
    def __init__(self, limit=50):
        self.history = []
        self.redo_stack = []
        self.limit = limit

    def push(self, state):
        # 1. Compress: Convert dict -> JSON string -> bytes -> Compressed bytes
        # sort_keys=True ensures identical states produce identical hashes
        blob = zlib.compress(json.dumps(state, sort_keys=True).encode('utf-8'))

        # 2. Deduplicate: If this state is identical to the last one, ignore it.
        if self.history and self.history[-1] == blob:
            return

        self.history.append(blob)
        if len(self.history) > self.limit:
            self.history.pop(0)
        
        # New branch of history, clear redo
        self.redo_stack.clear()

    def undo(self, current_state):
        if not self.history:
            return None
        
        # Save current "live" state to Redo stack before reverting
        current_blob = zlib.compress(json.dumps(current_state, sort_keys=True).encode('utf-8'))
        self.redo_stack.append(current_blob)

        # Pop previous state and decompress
        blob = self.history.pop()
        return json.loads(zlib.decompress(blob).decode('utf-8'))

    def redo(self, current_state):
        if not self.redo_stack:
            return None

        # Save current state to History stack before re-applying
        current_blob = zlib.compress(json.dumps(current_state, sort_keys=True).encode('utf-8'))
        self.history.append(current_blob)

        # Pop redo state and decompress
        blob = self.redo_stack.pop()
        return json.loads(zlib.decompress(blob).decode('utf-8'))

    def get_full_state(self):
        # Returns the raw compressed blobs (safe to pickle/save if needed)
        return {'history': self.history, 'redo': self.redo_stack}

    def load_full_state(self, data):
        self.history = data.get('history', [])
        self.redo_stack = data.get('redo', [])