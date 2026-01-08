import uuid
from PyQt5.QtGui import QPen
from PyQt5.QtCore import Qt, QPointF
from clip_item import ClipItem
from model import ClipModel

class TimelineOperations:
    def __init__(self, view):
        self.view = view 

    def split_audio_video(self, clip_item):
        """Goal 7: Separate video and audio using non-destructive collision search."""
        if clip_item.model.media_type != 'video' or not clip_item.model.has_audio:
            self.view.logger.warning("[AUDIO-SPLIT] Item has no audio stream to separate.")
            return
        self.view.mw.save_state_for_undo()
        self.view.logger.info(f"[AUDIO-SPLIT] Separating audio for: {clip_item.name}")
        start_t = clip_item.track + 1
        target_track = -1
        s1 = clip_item.model.start
        e1 = clip_item.model.start + clip_item.model.duration
        for t in range(start_t, self.view.num_tracks):
            is_blocked = False
            for item in self.view.scene.items():
                if isinstance(item, ClipItem) and item.track == t:
                    s2 = item.model.start
                    e2 = item.model.start + item.model.duration
                    if max(s1, s2) < min(e1, e2):
                        is_blocked = True
                        break
            if not is_blocked:
                target_track = t
                break
        if target_track == -1:
            self.view.mw.timeline.add_track()
            target_track = self.view.num_tracks - 1
            self.view.logger.info(f"[AUDIO-SPLIT] All lanes blocked. Created Track {target_track}")
        audio_data = clip_item.model.to_dict()
        audio_data.update({
            'uid': str(uuid.uuid4()),
            'name': f"{clip_item.name} (Audio)",
            'media_type': 'audio',
            'track': target_track,
            'width': 0, 'height': 0,
            'has_audio': True,
            'has_video': False,
            'linked_uid': clip_item.uid
        })
        clip_item.model.linked_uid = audio_data['uid']
        new_audio_item = self.view.add_clip(audio_data)
        clip_item.model.has_audio = False

        if hasattr(self.view.mw, 'asset_loader'):
            self.view.mw.asset_loader.regenerate_assets(new_audio_item.model.to_dict())
            
        self.view.mw.playback.mark_dirty(serious=True)
        self.view.data_changed.emit()
        self.view.scene.update()
        self.view.mw.save_state_for_undo()

    def get_snapped_x(self, x_pos, track_idx=None, ignore_items=None, threshold=20):

        playhead_x = self.view.playhead_pos * self.view.scale_factor
        extra_snaps = []
        selected = self.view.get_selected_item()
        if selected and hasattr(selected.model, 'scene_cuts'):
            extra_snaps = [(t + selected.model.start) * self.view.scale_factor for t in selected.model.scene_cuts]
        
        if abs(x_pos - playhead_x) < (threshold * 2):
            self._draw_snap_line(playhead_x)
            return playhead_x
            
        snaps = [0]
        if ignore_items is None: ignore_items = []
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item not in ignore_items:
                eff_th = threshold * 1.5 if (track_idx is not None and item.track == track_idx) else threshold
                sx, ex = item.x(), item.x() + item.rect().width()
                if abs(x_pos - sx) < eff_th: snaps.append(sx)
                if abs(x_pos - ex) < eff_th: snaps.append(ex)
        
        snaps.extend(extra_snaps)
        closest, min_dist = None, float('inf')
        for s in snaps:
            dist = abs(x_pos - s)
            if dist < min_dist: min_dist, closest = dist, s
            
        if min_dist <= threshold and closest is not None:
            self._draw_snap_line(closest)
            return closest
            
        if self.view.snap_line:
            self.view.snap_line.hide()
        return x_pos
        
    def _draw_snap_line(self, x):
        """Goal 8: Zero-flicker snap line updates via object reuse."""
        if not self.view.snap_line:
            from PyQt5.QtWidgets import QGraphicsLineItem
            pen = QPen(Qt.cyan, 1, Qt.DashLine)
            self.view.snap_line = self.view.scene.addLine(x, 0, x, self.view.scene.height(), pen)
            self.view.snap_line.setZValue(100)
        else:
            self.view.snap_line.setLine(x, 0, x, self.view.scene.height())
            self.view.snap_line.show()
        
    def compact_lanes(self):
        items = [i for i in self.view.scene.items() if isinstance(i, ClipItem)]
        if not items:
            return
        occupied = sorted(list(set(i.track for i in items)))
        if not occupied:
            return

    def reorder_tracks(self, s_idx, t_idx):
        self.view.mw.playback.player.pause()
        if s_idx == t_idx: return
        self.view.scene.blockSignals(True)
        try:

            items = [i for i in self.view.scene.items() if isinstance(i, ClipItem)]
            src_items = [i for i in items if i.track == s_idx]
            
            if s_idx < t_idx:
                for i in items:
                    if s_idx < i.track <= t_idx:
                        i.track -= 1
                        i.model.track = i.track
                        i.setY(i.track * self.view.track_height + 30)
            else:
                for i in items:
                    if t_idx <= i.track < s_idx:
                        i.track += 1
                        i.model.track = i.track
                        i.setY(i.track * self.view.track_height + 30)

            for i in src_items:
                i.track = t_idx
                i.model.track = t_idx
                i.setY(t_idx * self.view.track_height + 30)
        finally:
            self.view.scene.blockSignals(False)
        self.view.data_changed.emit()
        self.view.scene.update()
        
    def move_clip(self, clip_uid, pos, moving_linked=False):
        target_item = None
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                target_item = item
                break
        if target_item:
            target_item.setPos(QPointF(pos[0] * self.view.scale_factor, pos[1] * self.view.track_height + 30))
            target_item.model.start = pos[0]
            target_item.model.track = pos[1]
            if target_item.model.linked_uid and not moving_linked:
                self.move_clip(target_item.model.linked_uid, pos, moving_linked=True)
        return

    def set_clip_param(self, clip_uid, param, value):
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                setattr(item.model, param, value)
                item.update()
                return
        
    def update_clip_proxy_path(self, source_path, proxy_path):
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item.model.path == source_path:
                item.model.proxy_path = proxy_path
                item.update_cache()
                item.update()
        return