import pytest
from unittest.mock import MagicMock, patch
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QGraphicsScene, QWidget, QMessageBox
import json
from clip_item import ClipItem
from main_window import MainWindow
from project import ProjectManager
from player import MPVPlayer
from history import UndoStack
from ffmpeg_generator import FilterGraphGenerator
from playback_manager import PlaybackManager
app = QApplication([])

class MockConfigManager:
    def __init__(self, path):
        self.get = MagicMock(return_value=None)
        self.set = MagicMock()

class MockTimelineContainer(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.get_state = MagicMock(return_value=[])
        self.load_state = MagicMock()
        self.playhead_pos = 0.0
        self.timeline_view = MagicMock()
        self.set_visual_time = MagicMock()
        self.time_updated = MagicMock()
        self.clip_selected = MagicMock()
        self.file_dropped = MagicMock()
        self.data_changed = MagicMock()
        self.seek_request = MagicMock()
        self.clip_split_requested = MagicMock()
        self.track_volume_changed = MagicMock()
        self.time_updated.connect = MagicMock()
        self.clip_selected.connect = MagicMock()
        self.file_dropped.connect = MagicMock()
        self.data_changed.connect = MagicMock()
        self.seek_request.connect = MagicMock()
        self.clip_split_requested.connect = MagicMock()
        self.track_volume_changed.connect = MagicMock()
        self.set_time = MagicMock()
        self.update_clip_positions = MagicMock()
        self.get_content_end = MagicMock(return_value=10.0)

class MockInspectorWidget(QWidget):
    def __init__(self, main_window=None):
        super().__init__()
        self.combo_res = MagicMock()
        self.combo_res.currentText.return_value = "1920x1080"
        self.combo_res.findText.return_value = 0
        self.set_clip = MagicMock()
        self.track_mute_toggled = MagicMock()
        self.param_changed = MagicMock()
        self.resolution_changed = MagicMock()
        self.crop_toggled = MagicMock()
        self.track_mute_toggled.connect = MagicMock()
        self.param_changed.connect = MagicMock()
        self.resolution_changed.connect = MagicMock()
        self.crop_toggled.connect = MagicMock()

class MockMediaPoolWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.clear = MagicMock()
        self.add_file = MagicMock()
        self.count = MagicMock(return_value=0)
        self.item = MagicMock()
        self.media_double_clicked = MagicMock()
        self.media_double_clicked.connect = MagicMock()

class MockPreviewWidget(QWidget):
    def __init__(self, player_node, parent=None):
        super().__init__(parent)
        self.player_node = player_node
        self.param_changed = MagicMock()
        self.play_requested = MagicMock()
        self.seek_requested = MagicMock()
        self.overlay = MagicMock()
        self.set_player = MagicMock()
        self.interaction_started = MagicMock()
        self.interaction_ended = MagicMock()
        self.param_changed.connect = MagicMock()
        self.play_requested.connect = MagicMock()
        self.interaction_started.connect = MagicMock()
        self.interaction_ended.connect = MagicMock()
    
class MockClipModel:
    def __init__(self, uid, name, start, duration, track, media_type='video', **kwargs):
        self.uid = uid
        self.name = name
        self.start = start
        self.duration = duration
        self.track = track
        self.media_type = media_type
        self.speed = 1.0
        self.volume = 100
        self.linked_uid = None
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        return {
            'uid': self.uid, 'name': self.name, 'start': self.start, 
            'dur': self.duration, 'track': self.track, 'media_type': self.media_type
        }
@pytest.fixture
def clean_scene():
    scene = QGraphicsScene()
    yield scene
    scene.clear()
@pytest.fixture
def clip_item_fixture(clean_scene):
    model = MockClipModel("test_uid_1", "Test Clip", 0, 10, 0)
    item = ClipItem(model)
    clean_scene.addItem(item)
    return item
@pytest.fixture
def other_clip_item_fixture(clean_scene):
    model = MockClipModel("test_uid_2", "Other Clip", 5, 10, 1)
    item = ClipItem(model)
    clean_scene.addItem(item)
    return item

def test_toggle_play_starts_filter_graph():
    with patch('main_window.MainWindow.__init__', lambda x, y: None), \
         patch('playback_manager.FilterGraphGenerator') as mock_gen_class:
        mock_mpv = MagicMock()
        mock_mpv.is_playing.return_value = False
        mock_gen_inst = mock_gen_class.return_value
        mock_gen_inst.build.return_value = (["input.mp4"], "filter_str", "[v]", "[a]", False)
        mw = MainWindow("test_dir")
        mw.player_node = mock_mpv
        mw.timeline = MockTimelineContainer()
        mw.timeline.get_state.return_value = [{'uid': 'c1', 'start': 0, 'dur': 10, 'path': 'dummy.mp4'}]
        mw.inspector = MockInspectorWidget()
        mw.playback = PlaybackManager(mw.player_node, mw.timeline, mw.inspector)
        mw.act_proxy = MagicMock(isChecked=MagicMock(return_value=False))
        mw.track_volumes = {}
        mw.track_mutes = {}
        mw.toggle_play()
        mock_gen_class.assert_called_once()
        mock_gen_inst.build.assert_called_once()
@patch('main_window.ConfigManager', new=MockConfigManager)
def test_initial_history_state_on_load():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer', new=MockTimelineContainer), \
        patch('main_window.InspectorWidget', new=MockInspectorWidget), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget', new=MockMediaPoolWidget), \
        patch('main_window.BinaryManager'):
        mock_pm_inst = MockPM.return_value
        mock_pm_inst.get_latest_project_dir.return_value = "dummy_dir"
        timeline_data = [{'uid': 'c1'}, {'uid': 'c2'}]
        mock_pm_inst.load_project_from_dir.return_value = {
            'timeline': timeline_data,
            'ui_state': {}
        }
        mw = MainWindow("test_dir")
        mw.history.push(timeline_data, force=True)
        assert 'c1' in mw.history.current_state_map
        assert 'c2' in mw.history.current_state_map
        assert len(mw.history.current_state_map) == 2
@patch('main_window.ConfigManager', new=MockConfigManager)
def test_history_state_on_reset_project():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer', new=MockTimelineContainer), \
        patch('main_window.InspectorWidget', new=MockInspectorWidget), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget', new=MockMediaPoolWidget), \
        patch('main_window.BinaryManager'), \
        patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
        mock_pm_inst = MockPM.return_value
        mw = MainWindow("test_dir")
        mw.history.current_state_map = {'c1': {'uid': 'c1'}}
        mw.proj_ctrl.reset_project()
        assert mw.history.current_state_map == {}
@patch('main_window.ConfigManager', new=MockConfigManager)
def test_history_state_on_switch_project():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer', new=MockTimelineContainer), \
        patch('main_window.InspectorWidget', new=MockInspectorWidget), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget', new=MockMediaPoolWidget), \
        patch('main_window.BinaryManager'):
        mock_pm_inst = MockPM.return_value
        timeline_data = [{'uid': 's1', 'name': 'Switched'}]
        mock_pm_inst.load_project_from_dir.return_value = {
            'timeline': timeline_data
        }
        mw = MainWindow("test_dir")
        mw.history.current_state_map = {'old': {'uid': 'old'}}
        mw.proj_ctrl.switch_project("new_dir")
        mw.history.push(timeline_data, force=True)
        assert 's1' in mw.history.current_state_map
        assert len(mw.history.current_state_map) == 1
@pytest.fixture
def undo_stack():
    """Provides a clean UndoStack instance for testing."""
    return UndoStack()

def test_undo_stack_initial_state(undo_stack):
    assert not undo_stack.undo_stack
    assert not undo_stack.redo_stack
    assert undo_stack.current_state_map == {}

def test_push_adds_to_undo_stack(undo_stack):
    initial_state = []
    new_state = [{'uid': 'clip1', 'start': 0, 'dur': 5}]
    undo_stack.push(initial_state)
    assert len(undo_stack.undo_stack) == 0
    undo_stack.push(new_state)
    assert len(undo_stack.undo_stack) == 1
    assert not undo_stack.redo_stack

def test_undo_reverts_state_and_populates_redo(undo_stack):
    state1 = []
    state2 = [{'uid': 'clip1', 'start': 0, 'dur': 5, 'name': 'A'}]
    undo_stack.push(state1)
    undo_stack.push(state2)
    reverted_state = undo_stack.undo()
    assert len(undo_stack.undo_stack) == 0
    assert len(undo_stack.redo_stack) == 1
    assert reverted_state == state1

def test_redo_reapplies_state_and_populates_undo(undo_stack):
    state1 = []
    state2 = [{'uid': 'clip1', 'start': 0, 'dur': 5, 'name': 'A'}]
    undo_stack.push(state1)
    undo_stack.push(state2)
    undo_stack.undo()
    redone_state = undo_stack.redo()
    assert len(undo_stack.undo_stack) == 1
    assert len(undo_stack.redo_stack) == 0
    assert redone_state[0]['name'] == 'A'

def test_smart_push_delta_compression(undo_stack):
    state1 = [{'uid': 'clip1', 'start': 0, 'dur': 5, 'track': 0}]
    undo_stack.push(state1, force=True)
    state2 = [{'uid': 'clip1', 'start': 2, 'dur': 5, 'track': 0}]
    undo_stack.push(state2)
    state3 = [{'uid': 'clip1', 'start': 2, 'dur': 5, 'track': 0}, {'uid': 'clip2', 'start': 10, 'dur': 10, 'track': 1}]
    undo_stack.push(state3)
    state4 = [{'uid': 'clip2', 'start': 10, 'dur': 10, 'track': 1}]
    undo_stack.push(state4)
    assert len(undo_stack.undo_stack) == 4
    s = undo_stack.undo()
    s_map = {c['uid']: c for c in s}
    assert len(s) == 2
    assert 'clip1' in s_map
    assert 'clip2' in s_map
    s = undo_stack.undo()
    assert len(s) == 1
    assert s[0]['uid'] == 'clip1'
    assert s[0]['start'] == 2
    s = undo_stack.undo()
    assert len(s) == 1
    assert s[0]['uid'] == 'clip1'
    assert s[0]['start'] == 0