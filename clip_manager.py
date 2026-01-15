import uuid
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
            'source_in': item.model.source_in + split_rel,
            'linked_uid': None
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
        if not splitting_linked:
            self.mw.save_state_for_undo()
        return new_item

    def delete_current(self):
        """Deletes the selected clip and leaves a gap on the timeline."""
        selected_items = self.mw.timeline.get_selected_items()
        if not selected_items: return
        for item in selected_items:
            if item.model.linked_uid:
                for partner in self.mw.timeline.scene.items():
                    if isinstance(partner, ClipItem) and partner.model.uid == item.model.linked_uid:
                        self.mw.timeline.scene.removeItem(partner)
                        break
            self.mw.timeline.scene.removeItem(item)
        self.mw.timeline.update_tracks()
        self.mw.inspector.set_clip([])
        self.mw.timeline.data_changed.emit()
        self.mw.timeline.fit_to_view()
        earliest_delete = min([item.model.start for item in selected_items]) if selected_items else 0
        affected_tracks = set(item.model.track for item in selected_items)
        for track_num in sorted(list(affected_tracks)):
            self.mw.timeline.timeline_view.check_for_gaps(track_num, earliest_delete)
        self.mw.save_state_for_undo()

    def on_param_changed(self, param, value):
        self.mw.playback.player.pause()
        items = self.mw.timeline.get_selected_items()
        if not items: return
        affected_tracks_for_gap_check = set()
        changed = False
        for item in items:
            curr = getattr(item.model, param, None)
            if curr != value:
                changed = True
            if param == "speed":
                old_duration = item.model.duration
                item.set_speed(value)
                if item.model.linked_uid:
                    for partner in self.mw.timeline.scene.items():
                        if isinstance(partner, ClipItem) and partner.model.uid == item.model.linked_uid:
                            partner.set_speed(value)
                            break
                new_duration = item.model.duration
                if new_duration < old_duration:
                    affected_tracks_for_gap_check.add(item.model.track)
                actual = item.model.speed
                if abs(actual - value) > 0.001:
                    self.mw.inspector.update_clip_param("speed", actual)
                    self.mw.statusBar().showMessage("Action Blocked: Clip expansion would overlap neighbor.", 3000)
                else:
                    self.mw.playback.live_param_update("speed", value)
                    if not self.mw.player_node.is_playing():
                        self.mw.playback.mark_dirty(serious=True)
            elif param == "volume":
                item.set_volume(value)
                item.model.volume = value
                self.mw.player_node.set_volume(value)
            elif param in ["crop_x1", "crop_y1", "crop_x2", "crop_y2", "pos_x", "pos_y", "scale_x", "scale_y"]:
                setattr(item.model, param, value)
                self.mw.inspector.update_clip_param(param, value)
                self.mw.preview.overlay.update()
            elif param == "audio_gate_threshold":
                if hasattr(self.mw.recorder, 'worker') and self.mw.recorder.worker:
                    self.mw.recorder.worker.set_threshold(value)
                return
            elif param == "resync_partner":
                partner = None
                for it in self.mw.timeline.scene.items():
                    if isinstance(it, ClipItem) and it.model.uid == item.model.linked_uid:
                        partner = it
                        break
                if partner:
                    partner.model.start = item.model.start
                    partner.model.source_in = item.model.source_in
                    partner.setX(item.x())
                    partner.update_cache()
                    self.mw.timeline.data_changed.emit()
        if changed and not self.undo_lock:
            self.mw.save_state_for_undo()
        if affected_tracks_for_gap_check:
            for track in sorted(list(affected_tracks_for_gap_check)):
                if self.mw.timeline.timeline_view.check_for_gaps(track, 0):
                    break

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
            self.mw.save_state_for_undo()

    def ripple_delete_current(self):
        """Goal 5: Deletes selection and shifts subsequent clips without prompting."""
        selected_items = self.mw.timeline.get_selected_items()
        if not selected_items: return
        earliest_start = min([item.model.start for item in selected_items])
        latest_end = max([item.model.start + item.model.duration for item in selected_items])
        shift_amount = latest_end - earliest_start
        to_remove = set(selected_items)
        for item in selected_items:
            if item.model.linked_uid:
                for partner in self.mw.timeline.scene.items():
                    if isinstance(partner, ClipItem) and partner.model.uid == item.model.linked_uid:
                        to_remove.add(partner)
        for item in to_remove:
            self.mw.timeline.scene.removeItem(item)
        for item in self.mw.timeline.scene.items():
            if isinstance(item, ClipItem) and item not in to_remove:
                if item.model.start >= latest_end - 0.001:
                    item.model.start = max(0, item.model.start - shift_amount)
        self.mw.timeline.update_clip_positions()
        self.mw.timeline.update_tracks()
        self.mw.inspector.set_clip([])
        self.mw.timeline.data_changed.emit()
        self.mw.save_state_for_undo()
        self.mw.statusBar().showMessage(f"Ripple Deleted: Closed {shift_amount:.2f}s gap.", 2000)