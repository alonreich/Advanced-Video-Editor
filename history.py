import logging
import copy

class UndoStack:

    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []
        self.current_state_map = {} 
        self.max_depth = 50
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def push(self, new_state_list, force=False):
        """Goal 12: Smart Push with Delta Compression."""
        try:
            new_state_map = {c['uid']: c for c in new_state_list}
            if not force and self.current_state_map == new_state_map:
                return
            command = self._compute_diff(self.current_state_map, new_state_map)
            if not any(command.values()):
                return
            self.undo_stack.append(command)
            self.redo_stack.clear()
            updated_state_map = {}
            for uid, data in new_state_map.items():
                if uid in command['added'] or uid in command['modified']:
                    updated_state_map[uid] = data.copy()
                else:
                    updated_state_map[uid] = self.current_state_map.get(uid, data)
            self.current_state_map = updated_state_map
            if len(self.undo_stack) > self.max_depth:
                self.undo_stack.pop(0)
            self.logger.debug(f"[HISTORY] Smart Push: +{len(command['added'])} -{len(command['removed'])} ~{len(command['modified'])}")
        except Exception as e:
            self.logger.error(f"Failed to push undo state: {e}", exc_info=True)

    def undo(self, _current_ignored=None):
        """Applies the reverse of the last command."""
        if not self.undo_stack:
            return None
        cmd = self.undo_stack.pop()
        self.redo_stack.append(cmd)
        for uid in cmd['added']:
            if uid in self.current_state_map:
                del self.current_state_map[uid]
        for uid, data in cmd['removed'].items():
            self.current_state_map[uid] = data
        for uid, changes in cmd['modified'].items():
            if uid in self.current_state_map:
                for param, val_bundle in changes.items():
                    self.current_state_map[uid][param] = val_bundle['old']
        return self._get_flat_state()

    def redo(self):
        if not self.redo_stack:
            return None
        cmd = self.redo_stack.pop()
        self.undo_stack.append(cmd)
        for uid, data in cmd['added'].items():
            self.current_state_map[uid] = data
        for uid in cmd['removed']:
            if uid in self.current_state_map:
                del self.current_state_map[uid]
        for uid, changes in cmd['modified'].items():
            if uid in self.current_state_map:
                for param, val_bundle in changes.items():
                    self.current_state_map[uid][param] = val_bundle['new']
        return self._get_flat_state()

    def _compute_diff(self, old_map, new_map):
        """Calculates granular changes between two timeline states."""
        cmd = {'added': {}, 'removed': {}, 'modified': {}}
        for uid, data in old_map.items():
            if uid not in new_map:
                cmd['removed'][uid] = data.copy()
        for uid, new_data in new_map.items():
            if uid not in old_map:
                cmd['added'][uid] = new_data.copy()
            else:
                old_data = old_map[uid]
                changes = {}
                for key, new_val in new_data.items():
                    old_val = old_data.get(key)
                    if old_val != new_val:
                        changes[key] = {'old': old_val, 'new': new_val}
                if changes:
                    cmd['modified'][uid] = changes
        return cmd

    def _get_flat_state(self):
        return list(self.current_state_map.values())
