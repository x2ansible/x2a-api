from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
from typing import List, Dict, Union
import os
import subprocess

router = APIRouter()
UPLOAD_DIR = "uploads"  # Default fallback

def set_upload_dir(upload_dir: str):
    global UPLOAD_DIR
    UPLOAD_DIR = upload_dir
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    # Try to set write permissions (safe if it fails)
    try:
        os.chmod(UPLOAD_DIR, 0o775)
    except (OSError, PermissionError):
        pass  # Ignore if we can't set permissions

@router.post("/files/upload")
async def upload_files(files: List[UploadFile] = File(...)):
    # Ensure directory exists with permissions
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    saved: List[str] = []
    for file in files:
        dest_path = os.path.join(UPLOAD_DIR, file.filename)
        content = await file.read()
        
        try:
            with open(dest_path, "wb") as f:
                f.write(content)
            saved.append(file.filename)
        except PermissionError as e:
            raise HTTPException(
                status_code=500, 
                detail=f"Permission denied writing file {file.filename}. Check container upload directory permissions."
            )
    
    return {"saved_files": saved}

@router.get("/files/list")
async def list_folders():
    entries = os.listdir(UPLOAD_DIR)
    dirs = [
        e for e in entries
        if os.path.isdir(os.path.join(UPLOAD_DIR, e))
        and not os.path.isdir(os.path.join(UPLOAD_DIR, e, ".git"))
    ]
    folders = ["__ROOT__"] + dirs
    return {"folders": folders}

@router.get("/files/{folder}/list")
async def list_files_in_folder(folder: str):
    target = UPLOAD_DIR if folder == "__ROOT__" else os.path.join(UPLOAD_DIR, folder)
    if not os.path.exists(target):
        return JSONResponse(status_code=404, content={"error": "Folder not found"})
    files = [
        f for f in os.listdir(target)
        if os.path.isfile(os.path.join(target, f))
    ]
    return {"files": files}

@router.get("/files/tree")
async def get_file_tree(path: str = "") -> Dict[str, Union[str, list]]:
    root = os.path.join(UPLOAD_DIR, path) if path else UPLOAD_DIR
    if not os.path.exists(root):
        return {"path": path, "items": []}

    def is_relevant_file(entry: str) -> bool:
        """Check if file is relevant for any infrastructure-as-code technology"""
        entry_lower = entry.lower()
        
        # Comprehensive list of all supported file extensions
        relevant_extensions = (
            # Chef files
            ".rb", ".json", ".yml", ".yaml", ".erb",
            
            # Puppet files  
            ".pp", ".epp",
            
            # Terraform files
            ".tf", ".tfvars", ".hcl",
            
            # Ansible files
            ".yml", ".yaml", ".j2", ".jinja2",
            
            # BladeLogic files
            ".nsh", ".bl", ".sh", ".bash", ".bat", ".cmd", ".ps1",
            ".xml", ".properties", ".sql", ".md", ".txt", ".log",
            
            # Docker files
            ".dockerfile", ".docker",
            
            # Kubernetes files
            ".yaml", ".yml", ".json",
            
            # General automation and configuration files
            ".py", ".js", ".ts", ".go", ".java", ".scala",
            ".conf", ".cfg", ".ini", ".env", ".config",
            ".toml", ".yaml", ".yml", ".json", ".xml",
            ".template", ".tmpl", ".tpl",
            
            # Script files
            ".sh", ".bash", ".zsh", ".fish", ".csh", ".tcsh",
            ".bat", ".cmd", ".ps1", ".psm1", ".psd1",
            
            # Documentation and notes
            ".md", ".rst", ".txt", ".doc", ".docx", ".pdf",
            
            # Version control and CI/CD
            ".gitignore", ".gitattributes", ".travis.yml", 
            ".github", ".gitlab-ci.yml", ".circleci",
            
            # Package management
            ".lock", ".sum", ".mod", "requirements.txt", 
            "package.json", "composer.json", "pom.xml"
        )
        
        # Check file extension
        if entry_lower.endswith(relevant_extensions):
            return True
            
        # Check for special filenames without extensions
        special_filenames = {
            "dockerfile", "vagrantfile", "gemfile", "rakefile", 
            "makefile", "jenkinsfile", "readme", "license",
            "changelog", "contributing", "authors", "install",
            "setup", "configure", "bootstrap"
        }
        
        if any(entry_lower.startswith(name) for name in special_filenames):
            return True
            
        return False

    def list_dir(folder):
        items = []
        try:
            entries = os.listdir(folder)
        except (PermissionError, OSError):
            return items
            
        for entry in entries:
            # Skip hidden files and directories starting with .
            if entry.startswith('.'):
                continue
                
            full = os.path.join(folder, entry)
            rel = os.path.relpath(full, UPLOAD_DIR)
            
            try:
                if os.path.isdir(full):
                    # Skip common non-relevant directories
                    skip_dirs = {
                        "__pycache__", "node_modules", ".git", ".svn", 
                        ".hg", ".bzr", "target", "build", "dist",
                        ".terraform", ".vagrant", "venv", "env"
                    }
                    
                    if entry not in skip_dirs:
                        items.append({
                            "type": "folder",
                            "name": entry,
                            "path": rel,
                            "items": list_dir(full)
                        })
                        
                elif os.path.isfile(full) and is_relevant_file(entry):
                    items.append({
                        "type": "file", 
                        "name": entry, 
                        "path": rel
                    })
                    
            except (PermissionError, OSError):
                # Skip files/folders we can't access
                continue
                
        return items

    return {"path": path, "items": list_dir(root)}

@router.post("/files/get_many")
async def get_many_files(files: List[str] = Body(...)):
    contents = []
    for rel_path in files:
        abs_path = os.path.join(UPLOAD_DIR, rel_path)
        if not os.path.isfile(abs_path):
            continue
            
        try:
            # Try UTF-8 first
            with open(abs_path, "r", encoding="utf-8") as f:
                content = f.read()
                contents.append({"path": rel_path, "content": content})
        except UnicodeDecodeError:
            try:
                # Fallback to latin-1 for files with different encodings
                with open(abs_path, "r", encoding="latin-1") as f:
                    content = f.read()
                    contents.append({"path": rel_path, "content": content})
            except Exception as e:
                # If we still can't read it, add a placeholder
                print(f"Warning: Could not read file {rel_path}: {e}")
                contents.append({
                    "path": rel_path, 
                    "content": f"# Error: Could not read file {rel_path}\n# Error: {str(e)}"
                })
        except Exception as e:
            print(f"Warning: Error reading file {rel_path}: {e}")
            contents.append({
                "path": rel_path, 
                "content": f"# Error: Could not read file {rel_path}\n# Error: {str(e)}"
            })
            
    return {"files": contents}

@router.post("/files/clone")
async def clone_repo(url: str = Form(...)):
    repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
    target_dir = os.path.join(UPLOAD_DIR, repo_name)

    if os.path.isdir(target_dir):
        return {"cloned": repo_name}

    try:
        # Ensure the upload directory exists
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        
        # Clone the repository
        subprocess.run(
            ["git", "clone", url, target_dir], 
            check=True,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        return {"cloned": repo_name}
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=500, 
            detail=f"Clone operation timed out for {url}"
        )
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if e.stderr else str(e)
        raise HTTPException(
            status_code=500, 
            detail=f"Clone failed: {error_msg}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Clone failed: {str(e)}"
        )

# Additional utility endpoints for debugging and management

@router.get("/files/stats")
async def get_file_stats():
    """Get statistics about the uploaded files"""
    try:
        total_files = 0
        total_folders = 0
        file_types = {}
        
        for root, dirs, files in os.walk(UPLOAD_DIR):
            total_folders += len(dirs)
            total_files += len(files)
            
            for file in files:
                ext = os.path.splitext(file)[1].lower()
                if ext:
                    file_types[ext] = file_types.get(ext, 0) + 1
                else:
                    file_types['no_extension'] = file_types.get('no_extension', 0) + 1
        
        return {
            "total_files": total_files,
            "total_folders": total_folders,
            "file_types": file_types,
            "upload_dir": UPLOAD_DIR
        }
    except Exception as e:
        return {"error": str(e)}

@router.delete("/files/{folder}")
async def delete_folder(folder: str):
    """Delete a folder and all its contents"""
    if folder == "__ROOT__":
        raise HTTPException(status_code=400, detail="Cannot delete root folder")
        
    target_dir = os.path.join(UPLOAD_DIR, folder)
    
    if not os.path.exists(target_dir):
        raise HTTPException(status_code=404, detail="Folder not found")
        
    if not os.path.isdir(target_dir):
        raise HTTPException(status_code=400, detail="Path is not a folder")
    
    try:
        import shutil
        shutil.rmtree(target_dir)
        return {"message": f"Folder '{folder}' deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to delete folder: {str(e)}"
        )