import os
import sys
import shutil
import copy
import logging
from PyQt5.QtWidgets import QMessageBox, QInputDialog, QApplication, QAction
from PyQt5.QtCore import QTimer, Qt, QByteArray

class ProjectController:
    def __init__(self, main_window):
        self.mw = main_window
        self.pm = main_window.pm
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.autosave_timer = QTimer(main_window)
        self.autosave_timer.timeout.connect(self.run_autosave)
        self.autosave_timer.start(10000)

    def load_initial(self):
        latest = self.pm.get_latest_project_dir()
        if latest:
            self.switch_project(latest)
        else:
            self.pm.create_project()
            self.mw.history.push(self.mw.timeline.get_state())

    def switch_project(self, path):
        self.mw.media_pool.clear()
        self.mw.timeline.load_state([])
        data = self.pm.load_project_from_dir(path)
        if data:
            timeline_data = data.get('timeline', [])
            asset_data = data.get('assets', [])
            self.mw.media_pool.clear()
            self.mw.timeline.load_state(timeline_data)
            self.mw.history.current_state_map = {c['uid']: copy.deepcopy(c) for c in timeline_data}
            self.restore_ui_state(data.get('ui_state', {}))
            seen_assets = set()
            for path in asset_data:
                if path and os.path.exists(path):
                    self.mw.media_pool.add_file(path)
                    seen_assets.add(path)
            for item in timeline_data:
                file_path = item.get('path')
                if file_path and file_path not in seen_assets:
                    self.mw.media_pool.add_file(file_path)
                    seen_assets.add(file_path)
                self.mw.asset_loader.regenerate_assets(item)
            self.mw.setWindowTitle(f"Advanced Video Editor - {self.pm.project_name}")
            self.mw.save_state_for_undo()

    def run_autosave(self):
        if not self.mw.is_dirty: return
        pool_assets = []
        for i in range(self.mw.media_pool.count()):
            item = self.mw.media_pool.item(i)
            path = item.data(Qt.UserRole)
            if path: pool_assets.append(path)
        ui = {
            "playhead": self.mw.timeline.playhead_pos,
            "zoom": self.mw.timeline.scale_factor,
            "scroll_x": self.mw.timeline.horizontalScrollBar().value(),
            "scroll_y": self.mw.timeline.verticalScrollBar().value(),
            "resolution": self.mw.inspector.combo_res.currentText()
        }
        self.pm.save_state(self.mw.timeline.get_state(), ui, assets=pool_assets, is_autosave=True)

    def restore_ui_state(self, ui):
        if not ui: return
        self.mw.timeline.set_time(ui.get('playhead', 0.0))
        self.mw.timeline.scale_factor = ui.get('zoom', 50)
        res = ui.get('resolution', "Landscape 1920x1080 (HD)")
        idx = self.mw.inspector.combo_res.findText(res)
        if idx >= 0:
            self.mw.inspector.combo_res.setCurrentIndex(idx)
        else:
            self.mw.inspector.combo_res.setCurrentIndex(0)
        self.mw.timeline.update_clip_positions()

    def reset_project(self):
        if QMessageBox.question(self.mw, 'Reset', "Start new project? Unsaved changes lost.", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            self.mw.timeline.load_state([])
            self.mw.media_pool.clear()
            self.pm.create_project()
            self.mw.history.push([])

    def delete_all_projects(self):
        if QMessageBox.warning(self.mw, "DELETE ALL", "PERMANENTLY DELETE ALL PROJECTS?", QMessageBox.Yes|QMessageBox.No) == QMessageBox.Yes:
            for f in ["cache", "projects", "__pycache__"]:
                shutil.rmtree(os.path.join(self.mw.base_dir, f), ignore_errors=True)
            os.execl(sys.executable, sys.executable, *sys.argv)

    def populate_menu(self, menu):
        menu.clear()
        menu.addAction(f"Rename: {self.pm.project_name}", self.rename_project)
        menu.addAction("Save As...", self.save_as)
        menu.addSeparator()
        for p in self.pm.get_all_projects():
            txt = f"{p['name']} [{p['last_saved'].split('.')[0]}]"
            a = QAction(txt, self.mw)
            if p['id'] == self.pm.project_id:
                a.setEnabled(False)
            else:
                a.triggered.connect(lambda _, d=p['dir']: self.switch_project(d))
            menu.addAction(a)

    def rename_project(self):
        name, ok = QInputDialog.getText(self.mw, "Rename", "New Name:", text=self.pm.project_name)
        if ok and name:
            self.pm.set_project_name(name)
            self.mw.setWindowTitle(f"Advanced Video Editor - {name}")

    def save_as(self):
        name, ok = QInputDialog.getText(self.mw, "Save As", "Name:", text=f"{self.pm.project_name} - Copy")
        if ok and name:
            new_dir = self.pm.save_project_as(name, self.mw.timeline.get_state())
            if new_dir: self.switch_project(new_dir)

    def setup_project_menu(self):
        pass

    def populate_project_list(self, menu):
        menu.clear()
        projects = self.pm.get_all_projects()
        projects.sort(key=lambda x: x['last_saved'], reverse=True)
        if not projects:
            dummy = QAction("No projects found", self.mw)
            dummy.setEnabled(False)
            menu.addAction(dummy)
            return
        for p in projects:
            date_str = p['last_saved'].split('.')[0]
            display_str = f"{p['name']}   [{date_str}]"
            action = QAction(display_str, self.mw)
            if p['id'] == self.pm.project_id:
                action.setCheckable(True)
                action.setChecked(True)
                action.setEnabled(False)
            action.triggered.connect(lambda checked, path=p['dir']: self.switch_project(path))
            menu.addAction(action)