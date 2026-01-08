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
        occluders = []
        for c in raw_clips:
            is_full_screen = (c.get('scale_x', 1.0) >= 1.0 and c.get('scale_y', 1.0) >= 1.0 and 
                              c.get('crop_x1', 0.0) == 0.0 and c.get('crop_y1', 0.0) == 0.0 and 
                              c.get('crop_x2', 1.0) == 1.0 and c.get('crop_y2', 1.0) == 1.0)
            is_opaque = c.get('opacity', 1.0) >= 1.0
            if is_full_screen and is_opaque and c.get('width', 0) > 0:
                occluders.append({'start': c['start'], 'end': c['start'] + c['dur'], 'track': c['track']})
            path = c.get('path')
            if not path:
                continue
            norm = path.replace('\\', '/')
            escaped_path = norm.replace("'", "'\\''")
            if norm not in file_map:
                file_map[norm] = len(inputs)
                inputs.append(norm)
            c['escaped_path'] = escaped_path
        if not inputs:
            total_duration = duration if duration else 10.0
            return [], "", "[vo]", "[ao]", False
        visible_video = [c for c in raw_clips if c.get('width', 0) > 0]
        sorted_by_layer = sorted(visible_video, key=lambda x: -x['track'])
        occluded_uids = set()
        for i, lower_clip in enumerate(visible_video):
            l_start = lower_clip['start']
            l_end = l_start + lower_clip['dur']
            visible_intervals = [(l_start, l_end)]
            for top_clip in [c for c in visible_video if c['track'] < lower_clip['track']]:
                is_occluder = (top_clip.get('scale_x', 1.0) >= 1.0 and 
                               top_clip.get('scale_y', 1.0) >= 1.0 and 
                               top_clip.get('opacity', 1.0) >= 1.0 and
                               top_clip.get('crop_x1', 0.0) == 0.0 and 
                               top_clip.get('crop_y1', 0.0) == 0.0)
                if is_occluder:
                    t_start, t_end = top_clip['start'], top_clip['start'] + top_clip['dur']
                    new_intervals = []
                    for v_start, v_end in visible_intervals:
                        if t_start <= v_start and t_end >= v_end:
                            continue
                        elif t_start > v_start and t_end < v_end:
                            new_intervals.extend([(v_start, t_start), (t_end, v_end)])
                        elif t_start <= v_start and t_end > v_start:
                            new_intervals.append((t_end, v_end))
                        elif t_start < v_end and t_end >= v_end:
                            new_intervals.append((v_start, t_start))
                        else:
                            new_intervals.append((v_start, v_end))
                    visible_intervals = new_intervals
                if not visible_intervals: break
            if not visible_intervals or sum(e - s for s, e in visible_intervals) < 0.033:
                occluded_uids.add(lower_clip['uid'])
        visible_video = [c for c in visible_video if c['uid'] not in occluded_uids]
        if occluded_uids:
            self.logger.info(f"[RENDER] Occlusion aware: Dropped {len(occluded_uids)} hidden clips from graph.")
        video_clips = sorted(visible_video, key=lambda x: (-x['track'], x['start']))
        video_stream_counters = {idx: 0 for idx in file_map.values()}
        audio_clips = [c for c in raw_clips if c.get('has_audio', True)]
        main_input_used_for_video = False
        if inputs:
            p0 = inputs[0]
            main_input_used_for_video = any(c['path'].replace('\\', '/') == p0 for c in visible_video)
        video_stream_usage = {}
        for clip in video_clips:
            idx = file_map[clip['path'].replace('\\', '/')]
            video_stream_usage[idx] = video_stream_usage.get(idx, 0) + 1
        total_dur = max([c['start'] + c['dur'] for c in self.clips], default=10)
        filter_parts.append(f"color=c=black:s={self.w}x{self.h}:d={total_dur:.3f}[base]")
        last_v = "[base]"
        for i, clip in enumerate(video_clips):
            idx = file_map[clip['path'].replace('\\', '/')]
            if video_stream_usage.get(idx, 0) > 1:
                n = video_stream_counters[idx]
                input_stream = f"[vid_{idx}_{n}]"
                video_stream_counters[idx] += 1
            else:
                input_stream = f"[{idx}:v]"
            lbl = f"v{i}"
            speed = float(clip['speed'])
            clip_rel_offset = max(0, start_time - clip['start'])
            effective_source_in = clip['source_in'] + (clip_rel_offset * speed)
            effective_duration = (clip['dur'] - clip_rel_offset) * speed
            chain = [
                f"{input_stream}trim=start={effective_source_in}:duration={max(0.1, effective_duration)}",
                "setpts=PTS-STARTPTS",
                f"setpts=PTS*{1/speed:.6f}"
            ]
            start_freeze = clip.get('start_freeze', 0.0)
            if start_freeze > 0:
                chain.append(f"tpad=start_mode=clone:start_duration={start_freeze}")
            end_freeze = clip.get('end_freeze', 0.0)
            if end_freeze > 0:
                chain.append(f"tpad=stop_mode=clone:stop_duration={end_freeze}")
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
                f"pad={self.w}:{self.h}:(ow-iw)/2:(oh-ih)/2:color=black@0"
            )
            if is_export:
                chain.append("setsar=1")
            filter_parts.append(",".join(chain) + f"[{lbl}_p]")
            x = (self.w - target_w) / 2 + (self.w * clip.get('pos_x', 0))
            y = (self.h - target_h) / 2 - (self.h * clip.get('pos_y', 0))
            t_start = max(0, clip['start'] - start_time)
            t_end = t_start + clip['dur']
            enable_str = f":enable='between(t,{t_start:.3f},{t_end:.3f})'"
            filter_parts.append(f"{last_v}[{lbl}_p]overlay=x={int(x)}:y={int(y)}{enable_str}:eof_action=pass[bg{i}]")
            last_v = f"[bg{i}]"
        audio_stream_usage = {}
        for clip in audio_clips:
            if clip.get('muted') or self.mutes.get(clip['track']):
                continue
            idx = file_map[clip['path'].replace('\\', '/')]
            audio_stream_usage[idx] = audio_stream_usage.get(idx, 0) + 1
        for idx, count in audio_stream_usage.items():
            if count > 1:
                outputs = "".join([f"[src_aud_{idx}_{k}]" for k in range(count)])
                filter_parts.insert(0, f"[{idx}:a]asplit={count}{outputs}")
            else:
                pass
        audio_stream_counters = {idx: 0 for idx in audio_stream_usage}
        audio_outs = []
        for i, clip in enumerate(audio_clips):
            if clip.get('muted') or self.mutes.get(clip['track']):
                continue
            input_idx = file_map[clip['path'].replace('\\', '/')]
            if audio_stream_usage.get(input_idx, 0) > 1:
                n = audio_stream_counters[input_idx]
                src = f"[src_aud_{input_idx}_{n}]"
                audio_stream_counters[input_idx] += 1
            else:
                src = f"[{input_idx}:a]"
            audio_pad = f"[a{i}_out]"
            base_vol = (clip.get('volume', 100) / 100.0) * self.vols.get(clip['track'], 1.0)
            is_vo = "VO_" in clip.get('name', '') or clip.get('track') == -1
            duck_filter = ""
            if not is_vo:
                for vo_clip in [c for c in audio_clips if "VO_" in c.get('name', '') or c.get('track') == -1]:
                    vo_start = vo_clip['start']
                    vo_end = vo_start + vo_clip['dur']
                    duck_filter = f",volume=0.18:enable='between(t,{vo_start},{vo_end})'"
            vol_str = f"volume={base_vol:.2f}{duck_filter}"
            speed = float(clip.get('speed', 1.0))
            clip_rel_offset = max(0, start_time - clip['start'])
            effective_audio_in = clip['source_in'] + (clip_rel_offset * speed)
            remaining_dur = max(0.1, clip['dur'] - clip_rel_offset)
            src_duration = remaining_dur * speed
            audio_chain = [
                f"{src}atrim=start={effective_audio_in}:duration={src_duration:.6f}",
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
            relative_start = max(0, clip['start'] - start_time)
            audio_chain.extend([
                vol_str,
                f"adelay={int(relative_start * 1000)}:all=1{audio_pad}"
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