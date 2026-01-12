import logging
from filter_graph import FilterGraph, FilterNode

class FilterGraphGenerator:

    def __init__(self, clips, width=1920, height=1080, volumes=None, mutes=None, audio_analysis=None):
        self.clips = clips
        self.w = width
        self.h = height
        self.vols = volumes or {}
        self.mutes = mutes or {}
        self.audio_analysis = audio_analysis or {}
        self.logger = logging.getLogger("Advanced_Video_Editor")

    def build(self, start_time=0.0, duration=None, is_export=False):
        graph = FilterGraph()
        render_end = start_time + (duration if duration else 99999)
        raw_clips = [c for c in self.clips if c['start'] < render_end and (c.get('dur', c.get('duration', 0))) > start_time]
        for c in raw_clips:
            if c.get('path'):
                graph.add_input(c['path'])
        if not graph.inputs:
            return [], "", "[vo]", "[ao]", False
        video_clips = sorted([c for c in raw_clips if c.get('width', 0) > 0], key=lambda x: (x['track'], x['start']))
        audio_clips = [c for c in raw_clips if c.get('has_audio', True) and not (c.get('muted') or self.mutes.get(c['track']))]
        last_video_pin = self._build_video_chain(graph, video_clips, start_time, duration, is_export)
        last_audio_pin = self._build_audio_chain(graph, audio_clips, start_time)
        if last_video_pin:
            final_video_node = FilterNode("null", num_inputs=1, num_outputs=1)
            final_video_node.input_pins[0] = last_video_pin
            final_video_node.output_pins[0] = "[vo]"
            graph.add_node(final_video_node)
        if last_audio_pin:
            final_audio_node = FilterNode("aresample", {'sample_rate': 44100})
            final_audio_node.input_pins[0] = last_audio_pin
            final_audio_node.output_pins[0] = "[ao]"
            graph.add_node(final_audio_node)
        else:
            null_audio = FilterNode("anullsrc", {'channel_layout': 'stereo', 'sample_rate': 44100}, num_inputs=0)
            null_audio.output_pins[0] = "[ao]"
            graph.add_node(null_audio)
        main_input_used = any(c['path'].replace('\\','/') == graph.inputs[0] for c in video_clips) if graph.inputs else False
        return graph.inputs, graph.to_string(), "[vo]", "[ao]", main_input_used

    def _build_video_chain(self, graph, video_clips, start_time, duration, is_export):
        if duration is not None:
            window_dur = max(0.25, float(duration))
        else:
            max_end = max([c['start'] + c.get('dur', c.get('duration', 0)) for c in self.clips], default=start_time + 10.0)
            window_dur = max(0.25, min(30.0, max_end - start_time))
        if not is_export:
            window_dur = min(window_dur, 6.0)
        base_node = FilterNode("color", {'c': 'black', 's': f'{self.w}x{self.h}', 'd': f'{window_dur:.3f}'}, num_inputs=0)
        graph.add_node(base_node)
        last_v_pin = base_node.output_pins[0]
        video_src_pins = {}
        video_counts = {}
        for clip in video_clips:
            norm_path = clip['path'].replace('\\', '/')
            video_counts[norm_path] = video_counts.get(norm_path, 0) + 1
        for norm_path, count in video_counts.items():
            if count > 1:
                input_pin = graph.get_input_stream(norm_path, 'v')
                split_node = FilterNode("split", str(count), num_outputs=count)
                split_node.input_pins[0] = input_pin
                graph.add_node(split_node)
                video_src_pins[norm_path] = split_node.output_pins
            else:
                video_src_pins[norm_path] = [graph.get_input_stream(norm_path, 'v')]
        for clip in video_clips:
            norm_path = clip['path'].replace('\\', '/')
            if not video_src_pins.get(norm_path): continue
            clip_v_pin = video_src_pins[norm_path].pop(0)
            in_offset = max(0.0, start_time - clip['start'])
            remaining = clip.get('dur', clip.get('duration',0)) - in_offset
            if remaining <= 0: continue
            trim_node = FilterNode("trim", {'start': f'{in_offset:.3f}', 'duration': f'{remaining:.3f}'})
            trim_node.input_pins[0] = clip_v_pin
            graph.add_node(trim_node)
            scale_node = FilterNode("scale", {'w': int(self.w * clip.get('scale_x', 1.0)), 'h': int(self.h * clip.get('scale_y', 1.0)), 'flags': 'fast_bilinear'})
            graph.connect(trim_node, scale_node)
            graph.add_node(scale_node)
            rel_start = max(0.0, clip['start'] - start_time)
            pts_offset = rel_start / clip.get('speed', 1.0)
            setpts_node = FilterNode("setpts", {'expr': f'PTS-STARTPTS+{pts_offset:.3f}/TB'})
            graph.connect(scale_node, setpts_node)
            graph.add_node(setpts_node)
            overlay_node = FilterNode("overlay", {'x': f"((W-w)/2)+({clip.get('pos_x', 0.0)}*W)", 'y': f"((H-h)/2)-({clip.get('pos_y', 0.0)}*H)", 'enable': f"'between(t,{rel_start:.3f},{rel_start + remaining:.3f})'"}, num_inputs=2)
            overlay_node.input_pins[0] = last_v_pin
            graph.connect(setpts_node, overlay_node, from_pin_idx=0, to_pin_idx=1)
            graph.add_node(overlay_node)
            last_v_pin = overlay_node.output_pins[0]
        return last_v_pin
        
    def _build_audio_chain(self, graph, audio_clips, start_time):
        if not audio_clips:
            return None
        audio_src_pins = {}
        audio_counts = {}
        for clip in audio_clips:
            norm_path = clip['path'].replace('\\', '/')
            audio_counts[norm_path] = audio_counts.get(norm_path, 0) + 1
        for norm_path, count in audio_counts.items():
            if count > 1:
                input_pin = graph.get_input_stream(norm_path, 'a')
                split_node = FilterNode("asplit", str(count), num_outputs=count)
                split_node.input_pins[0] = input_pin
                graph.add_node(split_node)
                audio_src_pins[norm_path] = split_node.output_pins
            else:
                audio_src_pins[norm_path] = [graph.get_input_stream(norm_path, 'a')]
        processed_audio_pins = []
        for clip in audio_clips:
            norm_path = clip['path'].replace('\\', '/')
            if not audio_src_pins.get(norm_path): continue
            clip_a_pin = audio_src_pins[norm_path].pop(0)
            in_offset = max(0.0, start_time - clip['start'])
            remaining = clip.get('dur', clip.get('duration',0)) - in_offset
            if remaining <= 0: continue
            trim_node = FilterNode("atrim", {'start': f'{in_offset:.3f}', 'duration': f'{remaining:.3f}'})
            trim_node.input_pins[0] = clip_a_pin
            graph.add_node(trim_node)
            setpts_node = FilterNode("asetpts", {'expr': 'PTS-STARTPTS'})
            graph.connect(trim_node, setpts_node)
            graph.add_node(setpts_node)
            delay_ms = int(max(0.0, clip['start'] - start_time) * 1000)
            last_pin_node = setpts_node
            if delay_ms > 0:
                delay_node = FilterNode("adelay", {'delays': f'{delay_ms}|{delay_ms}'})
                graph.connect(setpts_node, delay_node)
                graph.add_node(delay_node)
                last_pin_node = delay_node
            processed_audio_pins.append(last_pin_node.output_pins[0])
        if not processed_audio_pins:
            return None
        if len(processed_audio_pins) > 1:
            mix_node = FilterNode("amix", {'inputs': len(processed_audio_pins)}, num_inputs=len(processed_audio_pins))
            for i, pin in enumerate(processed_audio_pins):
                mix_node.input_pins[i] = pin
            graph.add_node(mix_node)
            return mix_node.output_pins[0]
        else:
            return processed_audio_pins[0]
