import copy
class UndoStack:
    def __init__(self, limit=50):
        self.history = []
        self.redo_stack = []
        self.limit = limit
    def push(self, state):
        self.history.append(copy.deepcopy(state))
        if len(self.history) > self.limit: self.history.pop(0)
        self.redo_stack.clear()
    def undo(self, current_state):
        if not self.history: return None
        self.redo_stack.append(current_state)
        return self.history.pop()
    def redo(self, current_state):
        if not self.redo_stack: return None
        self.history.append(current_state)
        return self.redo_stack.pop()
    def get_full_state(self):
        return {'history': self.history, 'redo': self.redo_stack}
    def load_full_state(self, data):
        self.history = data.get('history', [])
        self.redo_stack = data.get('redo', [])