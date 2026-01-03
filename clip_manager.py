import uuid
from PyQt5.QtWidgets import QApplication
from clip_item import ClipItem

class ClipManager:
    def __init__(self, main_window):
        self.mw = main_window

    def split_current(self):
        item = self.mw.timeline.get_selected_item()
        if not item: return
        self.split_at(item, self.mw.timeline.playhead_pos)

    def split_at(self, item, time):
        if not (item.start < time < item.start + item.duration): return
        self.mw.save_state_for_undo()
        split_rel = time - item.start
        right_dur = item.duration - split_rel
        item.duration = split_rel
        item.model.duration = split_rel
        item.setRect(0, 0, split_rel * item.scale, 30)
        new_data = item.model.to_dict()
        new_data.update({
            'uid': str(uuid.uuid4()),
            'start': time,
            'dur': right_dur,
            'source_in': item.model.source_in + split_rel
        })
        self.mw.timeline.add_clip(new_data)
        if hasattr(self.mw, 'asset_loader'):
            self.mw.asset_loader.regenerate_assets(new_data)

    def delete_current(self):
        item = self.mw.timeline.get_selected_item()
        if not item: return
        self.mw.save_state_for_undo()
        track, start, dur = item.track, item.start, item.duration
        shifts = [i for i in self.mw.timeline.scene.items() 
                  if isinstance(i, ClipItem) and i != item and i.track == track and i.start > start]
        for i in shifts:
            i.start -= dur
            i.model.start = i.start
            i.setX(i.start * i.scale)
        self.mw.timeline.remove_selected_clips()
        self.mw.inspector.set_clip(None)

    def on_param_changed(self, param, value):
        item = self.mw.timeline.get_selected_item()
        if not item: return
        curr = getattr(item.model, param, None)
        if curr != value and not self.mw.undo_lock:
            self.mw.save_state_for_undo()
        if param == "speed":
            item.set_speed(value)
            if self.mw.player_node.is_playing(): self.mw.player_node.set_speed(value)
        elif param == "volume":
            item.set_volume(value)
            if self.mw.player_node.is_playing(): self.mw.player_node.set_volume(value)
        elif param in ["crop_x1", "crop_y1", "crop_x2", "crop_y2", "pos_x", "pos_y", "scale_x", "scale_y"]:
            setattr(item.model, param, value)
            self.mw.preview.overlay.update()
            if self.mw.player_node.is_playing() and "crop" in param:
                self.mw.player_node.apply_crop(item.model)
