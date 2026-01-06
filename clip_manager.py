import uuid
from PyQt5.QtWidgets import QApplication
from clip_item import ClipItem

class ClipManager:
    def __init__(self, main_window):
        self.mw = main_window
        self.undo_lock = False

    def undo_lock_acquire(self):
        self.undo_lock = True

    def undo_lock_release(self):
        self.undo_lock = False

    def split_current(self):
        item = self.mw.timeline.get_selected_item()
        if not item: return
        self.split_at(item, self.mw.timeline.playhead_pos)

    def split_at(self, item, time, splitting_linked=False):
        """Splits a clip and its linked partner simultaneously."""
        if not (item.start < time < item.start + item.duration): return
        if not splitting_linked:
            self.mw.save_state_for_undo()
        split_rel = time - item.start
        right_dur = item.duration - split_rel
        item.duration = split_rel
        item.model.duration = split_rel
        item.setRect(0, 0, split_rel * item.scale, 40)
        new_data = item.model.to_dict()
        new_uid = str(uuid.uuid4())
        new_data.update({
            'uid': new_uid,
            'start': time,
            'dur': right_dur,
            'source_in': item.model.source_in + split_rel
        })
        new_item = self.mw.timeline.add_clip(new_data)
        if item.model.linked_uid and not splitting_linked:
            partner = None
            for it in self.mw.timeline.scene.items():
                if isinstance(it, ClipItem) and it.model.uid == item.model.linked_uid:
                    partner = it
                    break
            if partner:
                new_partner_item = self.split_at(partner, time, splitting_linked=True)
                if new_partner_item:
                    new_item.model.linked_uid = new_partner_item.model.uid
                    new_partner_item.model.linked_uid = new_item.model.uid
        if hasattr(self.mw, 'asset_loader'):
            self.mw.asset_loader.regenerate_assets(new_data)
        self.mw.timeline.fit_to_view()
        return new_item

    def delete_current(self):
        """Goal 5: Ripple editing to automatically propagate forward and maintain continuity."""
        item = self.mw.timeline.get_selected_item()
        if not item: return
        self.mw.save_state_for_undo()
        track = item.track
        start = item.model.start
        dur = item.model.duration
        subsequent_clips = [i for i in self.mw.timeline.scene.items() 
                            if isinstance(i, ClipItem) and i != item 
                            and i.track == track and i.model.start > start]
        for i in subsequent_clips:
            i.model.start -= dur
            i.setX(i.model.start * i.scale)
            if i.model.linked_uid:
                for partner in self.mw.timeline.scene.items():
                    if isinstance(partner, ClipItem) and partner.uid == i.model.linked_uid:
                        partner.model.start = i.model.start
                        partner.setX(partner.model.start * partner.scale)
        self.mw.timeline.remove_selected_clips()
        self.mw.timeline.update_tracks()
        self.mw.inspector.set_clip(None)
        self.mw.timeline.data_changed.emit()
        self.mw.timeline.fit_to_view()

    def on_param_changed(self, param, value):
        item = self.mw.timeline.get_selected_item()
        if not item: return
        curr = getattr(item.model, param, None)
        if curr != value and not self.undo_lock:
            self.mw.save_state_for_undo()
        if param == "speed":
            item.set_speed(value)
            self.mw.playback.live_param_update("speed", value)
            if not self.mw.player_node.is_playing():
                self.mw.playback.mark_dirty(serious=True)
        elif param == "volume":
            item.set_volume(value)
            self.mw.player_node.set_volume(value)
        elif param in ["crop_x1", "crop_y1", "crop_x2", "crop_y2", "pos_x", "pos_y", "scale_x", "scale_y"]:
            setattr(item.model, param, value)
            self.mw.inspector.update_clip_param(param, value)
            self.mw.preview.overlay.update()
        elif param == "resync_partner":
            self.mw.save_state_for_undo()
            partner = None
            for it in self.mw.timeline.scene.items():
                if isinstance(it, ClipItem) and it.uid == item.model.linked_uid:
                    partner = it
                    break
            if partner:
                partner.model.start = item.model.start
                partner.model.source_in = item.model.source_in
                partner.setX(item.x())
                partner.update_cache()
                self.mw.timeline.data_changed.emit()

    def toggle_link(self, clip_uid):
        """Severs the link between video and audio components."""
        target_item = None
        linked_item = None
        for item in self.mw.timeline.scene.items():
            if isinstance(item, ClipItem):
                if item.model.uid == clip_uid:
                    target_item = item
                elif target_item and item.model.uid == target_item.model.linked_uid:
                    linked_item = item
                elif not linked_item and target_item is None:
                    pass
        if target_item:
            self.mw.save_state_for_undo()
            old_link = target_item.model.linked_uid
            target_item.model.linked_uid = None
            if old_link and not linked_item:
                for item in self.mw.timeline.scene.items():
                    if isinstance(item, ClipItem) and item.model.uid == old_link:
                        linked_item = item
                        break
            if linked_item:
                linked_item.model.linked_uid = None
            self.mw.logger.info(f"Link severed for clip {clip_uid}")
            target_item.update()
            is_crop_mode = getattr(self.mw.preview.overlay, 'crop_mode', False)
            if self.mw.player_node.is_playing() and not is_crop_mode:
                self.mw.player_node.apply_crop(target_item.model)
