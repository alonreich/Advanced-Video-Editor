import uuid
from PyQt5.QtGui import QPen
from PyQt5.QtCore import Qt, QPointF
from clip_item import ClipItem
from model import ClipModel

class TimelineOperations:
    def __init__(self, view):
        self.view = view 

    def split_audio_video(self, clip_item):
        self.view.logger.info(f"Splitting audio for clip {clip_item.name}")
        new_audio = ClipModel.from_dict(clip_item.model.to_dict())
        new_audio.uid = str(uuid.uuid4())
        new_audio.media_type = 'audio'
        new_audio.track = clip_item.track + 1
        new_audio.width = 0
        new_audio.height = 0
        clip_item.model.muted = True
        self.view.add_clip(new_audio)
        clip_item.update()
        self.view.data_changed.emit()

    def get_snapped_x(self, x_pos, track_idx=None, ignore_item=None, threshold=20):
        if not self.view.snapping_enabled:
            if self.view.snap_line:
                self.view.scene.removeItem(self.view.snap_line)
                self.view.snap_line = None
            return x_pos
        snaps = [0, self.view.playhead_pos * self.view.scale_factor]
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item != ignore_item:
                is_same = (track_idx is not None and item.track == track_idx)
                eff_th = threshold * 1.5 if is_same else threshold
                sx, ex = item.x(), item.x() + item.rect().width()
                if abs(x_pos - sx) < eff_th: snaps.append(sx)
                if abs(x_pos - ex) < eff_th: snaps.append(ex)
        closest, min_dist = None, float('inf')
        for s in snaps:
            dist = abs(x_pos - s)
            if dist < min_dist: min_dist, closest = dist, s
        if self.view.snap_line:
            self.view.scene.removeItem(self.view.snap_line)
            self.view.snap_line = None
        if min_dist <= threshold and closest is not None:
            pen = QPen(Qt.cyan, 1)
            h = self.view.scene.height()
            self.view.snap_line = self.view.scene.addLine(closest, 0, closest, h, pen)
            self.view.snap_line.setZValue(100)
            return closest
        return x_pos

    def compact_lanes(self):
        items = [i for i in self.view.scene.items() if isinstance(i, ClipItem)]
        if not items:
            self.view.set_num_tracks(3)
            return
        occupied = sorted(list(set(i.track for i in items)))
        if not occupied:
            self.view.set_num_tracks(3)
            return
        if len(occupied) <= 2:
            self.view.set_num_tracks(3)
        else:
            self.view.set_num_tracks(len(occupied))
        mapping = {old: new for new, old in enumerate(occupied)}
        if all(k==v for k,v in mapping.items()): return
        self.view.logger.info(f"Compacting: {mapping}")
        for item in items:
            if item.track in mapping:
                new_t = mapping[item.track]
                item.track = new_t
                item.model.track = new_t
                item.setY(new_t * self.view.track_height + 35)
        self.view.data_changed.emit()
        self.view.scene.update()

    def reorder_tracks(self, s_idx, t_idx):
        if s_idx == t_idx: return
        self.view.scene.blockSignals(True)
        try:
            items = [i for i in self.view.scene.items() if isinstance(i, ClipItem)]
            src_items = [i for i in items if i.track == s_idx]
            if s_idx < t_idx:
                for i in items:
                    if s_idx < i.track <= t_idx:
                        i.track -= 1
                        i.model.track -= 1
                        i.setY(i.track * self.view.track_height + 35)
            else:
                for i in items:
                    if t_idx <= i.track < s_idx:
                        i.track += 1
                        i.model.track += 1
                        i.setY(i.track * self.view.track_height + 35)
            for i in src_items:
                i.track = t_idx
                i.model.track = t_idx
                i.setY(t_idx * self.view.track_height + 35)
        finally:
            self.view.scene.blockSignals(False)
        self.view.data_changed.emit()
        self.view.scene.update()

    def move_clip(self, clip_uid, pos):
        for item in self.view.scene.items():
            if isinstance(item, ClipItem) and item.model.uid == clip_uid:
                item.setPos(QPointF(pos[0], pos[1]))
                item.model.start = pos[0] / self.view.scale_factor
                item.model.track = int(pos[1] / self.view.track_height)
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
                return
