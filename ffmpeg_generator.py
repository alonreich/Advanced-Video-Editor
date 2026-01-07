import logging

class FilterGraphGenerator:
    def __init__(self, clips, width=1920, height=1080, volumes=None, mutes=None):
        self.clips = clips
        self.w = width
        self.h = height
        self.vols = volumes or {}
        self.mutes = mutes or {}
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def build(self, start_time=0.0, duration=None, is_export=False, for_vlc=False):
        inputs = []
        file_map = {}
        filter_parts = []
        render_end = start_time + (duration if duration else 99999)
        raw_clips = [c for c in self.clips if c['start'] < render_end and (c['start'] + c['dur']) > start_time]
        for c in raw_clips:
            path = c.get('path')
            if not path:
                continue
            norm = path.replace('\\', '/')
            if norm not in file_map:
                file_map[norm] = len(inputs)
                inputs.append(norm)
        if not inputs:
            total_duration = duration if duration else 10.0
            filter_str = (
                f"color=c=black:s={self.w}x{self.h}:d={total_duration}[vo]" +
                f";anullsrc=channel_layout=stereo:sample_rate=44100[ao]"
            )
            return [], filter_str, "[vo]", "[ao]", False
        sorted_by_layer = sorted([c for c in raw_clips if c.get('width', 0) > 0], key=lambda x: -x['track'])
        visible_video = []
        for clip in sorted_by_layer:
            is_occluded = False
            for higher in visible_video:
                if higher['track'] <= clip['track']:
                    continue
                higher_end = higher['start'] + higher['dur']
                clip_end = clip['start'] + clip['dur']
                time_covered = (higher['start'] <= clip['start'] and higher_end >= clip_end)
                is_cropped = (higher.get('crop_x1', 0.0) > 0.001 or higher.get('crop_y1', 0.0) > 0.001 or 
                              higher.get('crop_x2', 1.0) < 0.999 or higher.get('crop_y2', 1.0) < 0.999)
                is_full_screen = (not is_cropped and 
                                  higher.get('scale_x', 1.0) >= 1.0 and higher.get('scale_y', 1.0) >= 1.0 and
                                  abs(higher.get('pos_x', 0)) < 0.001 and abs(higher.get('pos_y', 0)) < 0.001)
                if time_covered and is_full_screen and higher.get('opacity', 1.0) >= 0.99:
                    fade_in_end = higher['start'] + higher.get('fade_in', 0)
                    fade_out_start = higher_end - higher.get('fade_out', 0)
                    if clip['start'] >= fade_in_end and (clip['start'] + clip['dur']) <= fade_out_start:
                        is_occluded = True
                        self.logger.info(f"[OCCLUSION] Dropping hidden clip {clip['uid']} (covered by {higher['uid']})")
                        break
            if not is_occluded:
                visible_video.append(clip)
        audio_clips = [c for c in raw_clips if c.get('has_audio', True)]
        main_input_used_for_video = False
        if inputs:
            p0 = inputs[0]
            main_input_used_for_video = any(c['path'].replace('\\', '/') == p0 for c in visible_video)
        video_clips = sorted(visible_video, key=lambda x: (x['track'], x['start']))
        total_dur = max([c['start'] + c['dur'] for c in self.clips], default=10)
        filter_parts.append(f"color=c=black:s={self.w}x{self.h}:d={total_dur+5:.3f}[base]")
        last_v = "[base]"
        for i, clip in enumerate(video_clips):
            idx = file_map[clip['path'].replace('\\', '/')]
            lbl = f"v{i}"
            speed = float(clip['speed'])
            input_label = f"raw_v{i}"
            filter_parts.insert(0, f"[{idx}:v]null[{input_label}]")
            chain = [
                f"[{input_label}]trim=start={clip['source_in']}:duration={clip['dur'] * speed}",
                "setpts=PTS-STARTPTS",
                f"setpts=PTS*{1/speed:.6f}"
            ]
            if clip.get('crop_x2', 1) - clip.get('crop_x1', 0) < 0.99:
                cw = f"iw*({clip['crop_x2']}-{clip['crop_x1']})"
                ch = f"ih*({clip['crop_y2']}-{clip['crop_y1']})"
                cx = f"iw*{clip['crop_x1']}"
                cy = f"ih*({clip['crop_y1']})"
                chain.append(f"crop={cw}:{ch}:{cx}:{cy}")
            fade_in = float(clip.get('fade_in', 0.0))
            fade_out = float(clip.get('fade_out', 0.0))
            if fade_in > 0:
                chain.append(f"fade=t=in:st=0:d={fade_in:.3f}")
            if fade_out > 0:
                start_fade_out = (clip['dur'] * speed) - fade_out
                chain.append(f"fade=t=out:st={start_fade_out:.3f}:d={fade_out:.3f}")
            opacity = clip.get('opacity', 1.0)
            if opacity < 1.0:
                chain.append(f"format=rgba,colorchannelmixer=aa={opacity:.2f}")
            target_w = int(self.w * clip.get('scale_x', 1.0))
            target_h = int(self.h * clip.get('scale_y', 1.0))
            chain.append(
                f"scale={target_w}:{target_h}:force_original_aspect_ratio=decrease,"
                f"pad={target_w}:{target_h}:(ow-iw)/2:(oh-ih)/2:color=black@0"
            )
            if is_export:
                chain.append("setsar=1")
            filter_parts.append(",".join(chain) + f"[{lbl}_p]")
            x = (self.w - target_w) / 2 + (self.w * clip.get('pos_x', 0))
            y = (self.h - target_h) / 2 - (self.h * clip.get('pos_y', 0))
            filter_parts.append(f"{last_v}[{lbl}_p]overlay=x={int(x)}:y={int(y)}:eof_action=pass[bg{i}]")
            last_v = f"[bg{i}]"
        audio_stream_usage = {}
        for clip in audio_clips:
            if clip.get('muted') or self.mutes.get(clip['track']):
                continue
            idx = file_map[clip['path'].replace('\\', '/')]
            audio_stream_usage[idx] = audio_stream_usage.get(idx, 0) + 1
        for idx, n in audio_stream_usage.items():
            if n > 1:
                outs = "".join([f"[aud_{idx}_{k}]" for k in range(n)])
                filter_parts.insert(0, f"[{idx}:a]asplit={n}{outs}")
        audio_stream_counters = {idx: 0 for idx in audio_stream_usage}
        audio_outs = []
        for i, clip in enumerate(audio_clips):
            if clip.get('muted') or self.mutes.get(clip['track']):
                continue
            input_idx = file_map[clip['path'].replace('\\', '/')]
            if audio_stream_usage.get(input_idx, 0) > 1:
                n = audio_stream_counters[input_idx]
                src = f"[aud_{input_idx}_{n}]"
                audio_stream_counters[input_idx] += 1
            else:
                src = f"[{input_idx}:a]"
            audio_pad = f"[a{i}_out]"
            vol = (clip.get('volume', 100) / 100.0) * self.vols.get(clip['track'], 1.0)
            speed = float(clip.get('speed', 1.0))
            audio_chain = [
                f"{src}atrim=start={clip['source_in']}:duration={clip['dur']}",
                "asetpts=PTS-STARTPTS",
            ]
            if speed != 1.0:
                atempo_filters = []
                temp_speed = speed
                while temp_speed > 2.0:
                    atempo_filters.append("atempo=2.0")
                    temp_speed /= 2.0
                while temp_speed < 0.5 and temp_speed > 0:
                    atempo_filters.append("atempo=0.5")
                    temp_speed /= 0.5
                if temp_speed != 1.0:
                    atempo_filters.append(f"atempo={temp_speed}")
                if atempo_filters:
                    audio_chain.append(",".join(atempo_filters))
            audio_chain.extend([
                f"volume={vol:.2f}",
                f"adelay={int(clip['start'] * 1000)}:all=1{audio_pad}"
            ])
            filter_parts.append(",".join(audio_chain))
            audio_outs.append(audio_pad)
        if audio_outs:
            filter_parts.append(f"{'' .join(audio_outs)}amix=inputs={len(audio_outs)}:dropout_transition=0[out_a]")
            filter_parts.append("[out_a]aresample=44100[ao]")
        else:
            filter_parts.append("anullsrc=channel_layout=stereo:sample_rate=44100[ao]")
        filter_parts.append(f"{last_v}null[vo]")
        full_filter = ";".join(filter_parts)
        return inputs, full_filter, "[vo]", "[ao]", main_input_used_for_video

    def _generate_vlc_filter_string(self, clips):
        if not clips: return ""
        c = clips[0]
        vlc_ops = []
        if any(c.get(f'crop_{x}') is not None for x in ['x1', 'y1', 'x2', 'y2']):
            top = int(c.get('crop_y1', 0) * 1080)
            left = int(c.get('crop_x1', 0) * 1920)
            bottom = int((1 - c.get('crop_y2', 1)) * 1080)
            right = int((1 - c.get('crop_x2', 1)) * 1920)
            vlc_ops.append(f"croppadd{{croptop={top},cropbottom={bottom},cropleft={left},cropright={right}}}")
        vol = c.get('volume', 100) / 100.0
        return ":".join(vlc_ops)