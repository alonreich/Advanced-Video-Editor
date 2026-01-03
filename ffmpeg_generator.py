import logging

class FilterGraphGenerator:
    def __init__(self, clips, width=1920, height=1080, volumes=None, mutes=None):
        self.clips = clips
        self.w = width
        self.h = height
        self.vols = volumes or {}
        self.mutes = mutes or {}
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def build(self, start_time=0.0, duration=None, is_export=False):
        inputs = []
        file_map = {}
        filter_parts = []
        render_end = start_time + (duration if duration else 99999)
        raw_clips = [c for c in self.clips if c['start'] < render_end and (c['start'] + c['dur']) > start_time]
        sorted_by_layer = sorted([c for c in raw_clips if c.get('width', 0) > 0], key=lambda x: -x['track'])
        visible_video = []
        for clip in sorted_by_layer:
            is_occluded = False
            for higher in visible_video:
                if higher['track'] <= clip['track']: continue
                if (higher['start'] < clip['start'] + clip['dur'] and
                    higher['start'] + higher['dur'] > clip['start']):
                    if (higher.get('scale_x', 1) >= 1.0 and higher.get('scale_y', 1) >= 1.0 and
                        higher.get('opacity', 1.0) == 1.0 and
                        higher.get('fade_in', 0) == 0 and higher.get('fade_out', 0) == 0 and
                        abs(higher.get('pos_x', 0)) < 0.01 and abs(higher.get('pos_y', 0)) < 0.01):
                        is_occluded = True
                        break
            if not is_occluded:
                visible_video.append(clip)
        audio_clips = [c for c in raw_clips if c.get('has_audio', True)]
        active_clips = visible_video + audio_clips
        for c in active_clips:
            path = c['path'].replace('\\', '/')
            if path not in file_map:
                file_map[path] = len(inputs)
                inputs.append(path)
        video_clips = sorted(visible_video, key=lambda x: (x['track'], x['start']))
        total_dur = max([c['start'] + c['dur'] for c in active_clips], default=10)
        filter_parts.append(f"color=c=black:s={self.w}x{self.h}:d={total_dur+5:.3f}[base]")
        last_v = "[base]"
        for i, clip in enumerate(video_clips):
            idx = file_map[clip['path'].replace('\\', '/')]
            lbl = f"v{i}"
            speed = float(clip['speed'])
            chain = [
                f"[{idx}:v]trim=start={clip['source_in']}:duration={clip['dur'] * speed}",
                "setpts=PTS-STARTPTS",
                f"setpts=PTS*{1/speed:.6f}"
            ]
            if clip.get('crop_x2', 1) - clip.get('crop_x1', 0) < 0.99:
                cw = f"iw*({clip['crop_x2']}-{clip['crop_x1']})"
                ch = f"ih*({clip['crop_y2']}-{clip['crop_y1']})"
                cx = f"iw*{clip['crop_x1']}"
                cy = f"ih*{clip['crop_y1']}"
                chain.append(f"crop={cw}:{ch}:{cx}:{cy}")
            target_w = int(self.w * clip.get('scale_x', 1.0))
            target_h = int(self.h * clip.get('scale_y', 1.0))
            chain.append(f"scale={target_w}:{target_h}")
            if is_export: chain.append("setsar=1")
            filter_parts.append(",".join(chain) + f"[{lbl}_p]")
            x = (self.w - target_w)/2 + (self.w * clip.get('pos_x', 0))
            y = (self.h - target_h)/2 - (self.h * clip.get('pos_y', 0))
            filter_parts.append(f"{last_v}[{lbl}_p]overlay=x={int(x)}:y={int(y)}:eof_action=pass[bg{i}]")
            last_v = f"[bg{i}]"
        audio_outs = []
        for i, clip in enumerate(audio_clips):
            if clip.get('muted') or self.mutes.get(clip['track']): continue
            idx = file_map[clip['path'].replace('\\', '/')]
            lbl = f"a{i}"
            speed = float(clip['speed'])
            vol = (clip.get('volume', 100)/100.0) * self.vols.get(clip['track'], 1.0)
            start_ms = int(clip['start'] * 1000)
            achain = [
                f"[{idx}:a]atrim=start={clip['source_in']}:duration={clip['dur'] * speed}",
                "asetpts=PTS-STARTPTS",
                f"atempo={speed}",
                f"volume={vol}",
                f"adelay={start_ms}|{start_ms}"
            ]
            filter_parts.append(",".join(achain) + f"[{lbl}]")
            audio_outs.append(f"[{lbl}]")
        if audio_outs:
            filter_parts.append(f"{''.join(audio_outs)}amix=inputs={len(audio_outs)}:dropout_transition=0[out_a]")
        else:
            filter_parts.append("anullsrc=channel_layout=stereo:sample_rate=44100[out_a]")
        filter_parts.append(f"{last_v}copy[vo]")
        filter_parts.append("[out_a]anull[ao]")
        full_filter = ";".join(filter_parts)
        return inputs, full_filter, "[vo]", "[ao]"
