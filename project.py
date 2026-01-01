import os
import shutil
import json
import uuid
import datetime
import logging

class ProjectManager:
    def __init__(self, base_dir):
        self.logger = logging.getLogger("Advanced_Video_Editor")
        self.projects_root = os.path.join(base_dir, "projects")
        self.current_project_dir = None
        self.assets_dir = None
        self.project_id = None
        self.project_name = "Untitled Project"
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

    def delete_all_projects(self):
        try:
            for item in os.listdir(self.projects_root):
                path = os.path.join(self.projects_root, item)
                if os.path.isdir(path):
                    shutil.rmtree(path)
            self.logger.info("All projects deleted.")
            self.current_project_dir = None
            self.create_project()
        except Exception as e:
            self.logger.error(f"Failed to delete all projects: {e}")

    def create_project(self):
        self.project_id = f"proj_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.project_name = "New Project"
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
            "name": self.project_name,
            "last_saved": str(datetime.datetime.now()),
            "timeline": timeline_state
        }
        with open(fpath, 'w') as f:
            json.dump(data, f, indent=4)

    def load_latest(self):
        return self.load_project_from_dir(self.get_latest_project_dir())

    def get_latest_project_dir(self):
        all_projs = sorted([
            os.path.join(self.projects_root, d) 
            for d in os.listdir(self.projects_root) 
            if os.path.isdir(os.path.join(self.projects_root, d))
        ], key=os.path.getmtime, reverse=True)
        return all_projs[0] if all_projs else None

    def load_project_from_dir(self, proj_dir):
        if not proj_dir: return None
        pj_file = os.path.join(proj_dir, "project.json")
        if os.path.exists(pj_file):
            try:
                with open(pj_file, 'r') as f:
                    data = json.load(f)
                    self.current_project_dir = proj_dir
                    self.assets_dir = os.path.join(proj_dir, "assets")
                    self.project_id = data.get("id")
                    self.project_name = data.get("name", "Untitled Project")
                    self.logger.info(f"Loaded project: {self.project_name} ({self.project_id})")
                    return data
            except Exception as e:
                self.logger.error(f"Corrupt project file: {e}")
        return None

    def get_all_projects(self):
        projs = []
        for d in os.listdir(self.projects_root):
            full_path = os.path.join(self.projects_root, d)
            if os.path.isdir(full_path):
                pj_file = os.path.join(full_path, "project.json")
                if os.path.exists(pj_file):
                    try:
                        with open(pj_file, 'r') as f:
                            data = json.load(f)
                            projs.append({
                                'dir': full_path,
                                'id': data.get('id'),
                                'name': data.get('name', 'Untitled'),
                                'last_saved': data.get('last_saved', 'Unknown')
                            })
                    except: pass
        projs.sort(key=lambda x: x['last_saved'], reverse=True)
        return projs
    def set_project_name(self, new_name):
        self.project_name = new_name

    def save_project_as(self, new_name, timeline_state):
        new_id = f"proj_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        new_proj_dir = os.path.join(self.projects_root, new_id)
        new_assets_dir = os.path.join(new_proj_dir, "assets")
        os.makedirs(new_assets_dir, exist_ok=True)
        if self.assets_dir and os.path.exists(self.assets_dir):
            for f in os.listdir(self.assets_dir):
                src = os.path.join(self.assets_dir, f)
                dst = os.path.join(new_assets_dir, f)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
        old_root = os.path.normpath(self.assets_dir) if self.assets_dir else ""
        updated_timeline = []
        for clip in timeline_state:
            c_copy = clip.copy()
            c_path = os.path.normpath(c_copy.get('path', ''))
            if old_root and c_path.startswith(old_root):
                rel = os.path.relpath(c_path, old_root)
                new_path = os.path.join(new_assets_dir, rel)
                c_copy['path'] = new_path.replace('\\', '/')
            updated_timeline.append(c_copy)
        data = {
            "id": new_id,
            "name": new_name,
            "last_saved": str(datetime.datetime.now()),
            "timeline": updated_timeline
        }
        with open(os.path.join(new_proj_dir, "project.json"), 'w') as f:
            json.dump(data, f, indent=4)
        self.logger.info(f"Saved Project As: {new_name} ({new_id})")
        return new_proj_dir
