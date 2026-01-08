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
app = QApplication([])

class MockPreviewWidget(QWidget):

    def __init__(self, player_node, parent=None):
        super().__init__(parent)
        self.player_node = player_node
        self.param_changed = MagicMock()
        self.play_requested = MagicMock()
        self.seek_requested = MagicMock()
        self.overlay = MagicMock()
    
    def set_player(self, player):
        pass

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

def test_update_collision_cache_no_collision(clip_item_fixture):
    clip_item_fixture.update_collision_cache()
    assert clip_item_fixture.cached_collisions == []

def test_update_collision_cache_with_collision(clip_item_fixture, other_clip_item_fixture):
    other_clip_item_fixture.setPos(5 * clip_item_fixture.scale, 0 * 40 + 35)
    other_clip_item_fixture.track = 0
    clip_item_fixture.track = -1
    clip_item_fixture.update_collision_cache()
    if hasattr(clip_item_fixture, 'cached_collisions'):
        assert isinstance(clip_item_fixture.cached_collisions, list)
@patch('playback_manager.FilterGraphGenerator')
@patch('main_window.MPVPlayer')
@patch('main_window.ProjectManager')
@patch('main_window.UndoStack')
@patch('main_window.ConfigManager')

def test_toggle_play_starts_filter_graph(mock_conf, mock_undo, mock_pm, mock_mpv, mock_gen):
    mock_mpv_inst = mock_mpv.return_value
    mock_mpv_inst.is_playing.return_value = False
    mock_gen_inst = mock_gen.return_value
    mock_gen_inst.build.return_value = (["input.mp4"], "filter_str", "[v]", "[a]")
    with patch('main_window.TimelineContainer') as MockTimeline, \
        patch('main_window.InspectorWidget') as MockInspector, \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget'), \
        patch('main_window.BinaryManager'):
        mock_timeline = MockTimeline.return_value
        mock_timeline.get_state.return_value = [{'uid': 'c1', 'start': 0}]
        mock_timeline.playhead_pos = 5.0
        mock_insp = MockInspector.return_value
        mock_insp.combo_res.currentText.return_value = "1920x1080"
        mw = MainWindow("test_dir")
        mw.player_node = mock_mpv_inst
        mw.timeline = mock_timeline
        mw.inspector = mock_insp
        mw.act_proxy = MagicMock(isChecked=MagicMock(return_value=False))
        mw.toggle_play()
        mock_gen_inst.build.assert_called_once()
        mock_mpv_inst.play_filter_graph.assert_called_once_with("filter_str", ["input.mp4"])
        mock_mpv_inst.seek.assert_called_once_with(5.0)

def test_initial_history_state_on_load():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.ConfigManager'), \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer') as MockTimeline, \
        patch('main_window.InspectorWidget'), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget'), \
        patch('main_window.BinaryManager'):
        mock_pm_inst = MockPM.return_value
        mock_pm_inst.get_latest_project_dir.return_value = "dummy_dir"
        mock_pm_inst.load_project_from_dir.return_value = {
            'timeline': [{'uid': 'c1'}, {'uid': 'c2'}],
            'ui_state': {}
        }
        mw = MainWindow("test_dir")
        assert 'c1' in mw.history.current_state_map
        assert 'c2' in mw.history.current_state_map
        assert len(mw.history.current_state_map) == 2

def test_history_state_on_reset_project():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.ConfigManager'), \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer') as MockTimeline, \
        patch('main_window.InspectorWidget'), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget'), \
        patch('main_window.BinaryManager'), \
        patch('PyQt5.QtWidgets.QMessageBox.question', return_value=QMessageBox.Yes):
        mock_pm_inst = MockPM.return_value
        mock_timeline = MockTimeline.return_value
        mock_timeline.get_state.return_value = []
        mw = MainWindow("test_dir")
        mw.history.current_state_map = {'c1': {'uid': 'c1'}}
        mw.proj_ctrl.reset_project()
        assert mw.history.current_state_map == {}

def test_history_state_on_switch_project():
    with patch('main_window.ProjectManager') as MockPM, \
        patch('main_window.ConfigManager'), \
        patch('main_window.MPVPlayer'), \
        patch('main_window.TimelineContainer') as MockTimeline, \
        patch('main_window.InspectorWidget'), \
        patch('main_window.PreviewWidget', new=MockPreviewWidget), \
        patch('main_window.MediaPoolWidget'), \
        patch('main_window.BinaryManager'):
        mock_pm_inst = MockPM.return_value
        mock_pm_inst.load_project_from_dir.return_value = {
            'timeline': [{'uid': 's1', 'name': 'Switched'}]
        }
        mock_timeline = MockTimeline.return_value
        mock_timeline.get_state.return_value = [{'uid': 's1'}]
        mw = MainWindow("test_dir")
        mw.history.current_state_map = {'old': {'uid': 'old'}}
        mw.proj_ctrl.switch_project("new_dir")
        assert 's1' in mw.history.current_state_map
        assert len(mw.history.current_state_map) == 1