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
        """Initializes the project directory structure."""
        os.makedirs(self.projects_root, exist_ok=True)
        if self.current_project_dir:
            os.makedirs(os.path.join(self.current_project_dir, "voiceover"), exist_ok=True)
        self.enforce_fifo_limit()

    def enforce_fifo_limit(self):
        """Goal 11: Strictly enforce 10-project limit using FIFO logic."""
        all_projs = [
            os.path.join(self.projects_root, d) 
            for d in os.listdir(self.projects_root) 
            if os.path.isdir(os.path.join(self.projects_root, d))
        ]
        all_projs.sort(key=os.path.getmtime)
        if len(all_projs) > 10:
            projects_to_delete = all_projs[:-10]
            for oldest in projects_to_delete:
                if oldest == self.current_project_dir:
                    continue
                self.logger.info(f"[FIFO] Naming and shaming old project for deletion: {oldest}")
                try:
                    shutil.rmtree(oldest, ignore_errors=True)
                except Exception as e:
                    self.logger.error(f"[FIFO] Failed to nuke {oldest}: {e}")

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
        self.enforce_fifo_limit()
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
        if self.assets_dir is None and self.current_project_dir:
            self.assets_dir = os.path.join(self.current_project_dir, "assets")
            os.makedirs(self.assets_dir, exist_ok=True)
        abs_path = os.path.abspath(source_path)
        if not os.path.exists(abs_path):
            self.logger.error(f"Asset not found: {source_path}")
            return source_path
        fname = os.path.basename(abs_path)
        name, ext = os.path.splitext(fname)
        dest_path = os.path.join(self.assets_dir, fname)
        counter = 1
        while os.path.exists(dest_path):
            dest_path = os.path.join(self.assets_dir, f"{name}_{counter}{ext}")
            counter += 1
        try:
            shutil.copy2(abs_path, dest_path)
            self.logger.info(f"Imported asset: {abs_path} -> {dest_path}")
            return dest_path
        except Exception as e:
            self.logger.error(f"Failed to import asset {abs_path}: {e}")
            return abs_path

    def save_state(self, timeline_state, ui_state=None, assets=None, is_autosave=False, is_emergency=False):
        """Goal 19: Emergency Sidecar Logging and Continuous Autosave."""
        if not self.current_project_dir:
            self.logger.warning("[SAVE] No active project directory to save state.")
            return
        if is_emergency:
            filename = "project.sidecar.json"
        elif is_autosave:
            filename = "project.autosave.json"
        else:
            filename = "project.json"
        fpath = os.path.join(self.current_project_dir, filename)
        data = {
            "id": self.project_id,
            "name": self.project_name,
            "last_saved": str(datetime.datetime.now()),
            "timeline": timeline_state,
            "ui_state": ui_state or {},
            "assets": assets or []
        }
        temp_path = fpath + ".tmp"
        try:
            with open(temp_path, 'w') as f:
                json.dump(data, f, indent=4)
            if os.path.exists(fpath):
                os.replace(temp_path, fpath)
            else:
                os.rename(temp_path, fpath)
            if not is_autosave:
                auto_path = os.path.join(self.current_project_dir, "project.autosave.json")
                if os.path.exists(auto_path):
                    os.remove(auto_path)
        except Exception as e:
            self.logger.error(f"Failed to save project: {e}")

    def load_latest(self):
        return self.load_project_from_dir(self.get_latest_project_dir())

    def get_latest_project_dir(self):
        def get_real_mtime(path):
            candidates = [os.path.getmtime(path)]
            p_json = os.path.join(path, "project.json")
            a_json = os.path.join(path, "project.autosave.json")
            if os.path.exists(p_json): candidates.append(os.path.getmtime(p_json))
            if os.path.exists(a_json): candidates.append(os.path.getmtime(a_json))
            return max(candidates)
        all_projs = [
            os.path.join(self.projects_root, d) 
            for d in os.listdir(self.projects_root) 
            if os.path.isdir(os.path.join(self.projects_root, d))
        ]
        if not all_projs: return None
        sorted_projs = sorted(all_projs, key=get_real_mtime, reverse=True)
        return sorted_projs[0]

    def load_project_from_dir(self, proj_dir):
        if not proj_dir: return None
        pj_path = os.path.join(proj_dir, "project.json")
        autosave_path = os.path.join(proj_dir, "project.autosave.json")
        pj_exists = os.path.exists(pj_path)
        autosave_exists = os.path.exists(autosave_path)
        load_path = None
        if pj_exists and autosave_exists:
            load_path = autosave_path if os.path.getmtime(autosave_path) > os.path.getmtime(pj_path) else pj_path
        elif pj_exists:
            load_path = pj_path
        elif autosave_exists:
            load_path = autosave_path
        if load_path:
            try:
                with open(load_path, 'r') as f:
                    data = json.load(f)
                    self.current_project_dir = proj_dir
                    self.assets_dir = os.path.join(proj_dir, "assets")
                    self.project_id = data.get("id")
                    self.project_name = data.get("name", "Untitled Project")
                    self.logger.info(f"Loaded project from {os.path.basename(load_path)}: {self.project_name} ({self.project_id})")
                    return data
            except Exception as e:
                self.logger.error(f"Corrupt project file at {load_path}: {e}")
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
        self.enforce_fifo_limit()
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

    def get_voiceover_target(self):
        """Generates a unique path for a new voiceover file."""
        if not self.current_project_dir:
            self.create_project()
        vo_dir = os.path.join(self.current_project_dir, "voiceover")
        os.makedirs(vo_dir, exist_ok=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"VO_{timestamp}.wav"
        return os.path.join(vo_dir, filename)