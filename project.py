import os
import shutil
import json
import uuid
import datetime
import logging

class ProjectManager:
    def __init__(self, base_dir):
        self.logger = logging.getLogger("ProEditor")
        self.projects_root = os.path.join(base_dir, "projects")
        self.current_project_dir = None
        self.assets_dir = None
        self.project_id = None
        self.ensure_structure()

    def ensure_structure(self):
        os.makedirs(self.projects_root, exist_ok=True)
        all_projs = sorted([
            os.path.join(self.projects_root, d) 
            for d in os.listdir(self.projects_root) 
            if os.path.isdir(os.path.join(self.projects_root, d))
        ], key=os.path.getmtime)
        while len(all_projs) > 10:
            oldest = all_projs.pop(0)
            self.logger.info(f"FIFO Cleanup: Deleting old project {oldest}")
            shutil.rmtree(oldest, ignore_errors=True)

    def create_project(self):
        self.project_id = f"proj_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_project_dir = os.path.join(self.projects_root, self.project_id)
        self.assets_dir = os.path.join(self.current_project_dir, "assets")
        os.makedirs(self.assets_dir, exist_ok=True)
        self.logger.info(f"Created new project: {self.project_id}")
        return self.current_project_dir

    def import_asset(self, source_path):
        if not self.current_project_dir:
            self.create_project()
        fname = os.path.basename(source_path)
        dest_path = os.path.join(self.assets_dir, fname)
        if not os.path.exists(dest_path):
            self.logger.info(f"Staging asset: {fname}")
            try:
                shutil.copy2(source_path, dest_path)
            except Exception as e:
                self.logger.error(f"Failed to copy asset: {e}")
                return source_path
        return dest_path

    def save_state(self, timeline_state):
        if not self.current_project_dir: return
        fpath = os.path.join(self.current_project_dir, "project.json")
        data = {
            "id": self.project_id,
            "last_saved": str(datetime.datetime.now()),
            "timeline": timeline_state
        }
        with open(fpath, 'w') as f:
            json.dump(data, f, indent=4)

    def load_latest(self):
        all_projs = sorted([
            os.path.join(self.projects_root, d) 
            for d in os.listdir(self.projects_root) 
            if os.path.isdir(os.path.join(self.projects_root, d))
        ], key=os.path.getmtime, reverse=True)
        if not all_projs: return None
        latest = all_projs[0]
        pj_file = os.path.join(latest, "project.json")
        if os.path.exists(pj_file):
            try:
                with open(pj_file, 'r') as f:
                    data = json.load(f)
                    self.current_project_dir = latest
                    self.assets_dir = os.path.join(latest, "assets")
                    self.project_id = data.get("id")
                    self.logger.info(f"Loaded project: {self.project_id}")
                    return data
            except Exception as e:
                self.logger.error(f"Corrupt project file: {e}")
        return None
