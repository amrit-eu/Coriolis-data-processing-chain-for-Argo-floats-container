import os
import logging
from pathlib import Path
from datetime import datetime
import shutil

def setup_decoder_directories_for_float(float_wmo, base_dir="./decArgo", timestamp=True):
    """
    Set up the directory structure required for a specific Argo float decoder run.
    Each float gets its own unique directory structure to prevent overwriting.
    
    Args:
        float_id (str): Unique identifier for the float (e.g., "6902892")
        base_dir (str): Base directory for the decoder setup (default: "./decArgo")
        timestamp (bool): Whether to add timestamp to make directory unique
        
    Returns:
        dict: Dictionary containing all the created directory paths and float directory
    """
    
    # Create unique directory name for this float
    if timestamp:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M")
        float_dir_name = f"{float_wmo}_{timestamp_str}"
    else:
        float_dir_name = float_wmo
    
    # Convert to Path object for easier manipulation
    base_path = Path(base_dir)
    float_path = base_path / float_dir_name
    
    try:
         base_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating base directories for WMO {float_wmo}: {e}")
        raise    
    # Define the directory structure for this specific float
    directories = {
        'base': base_path,
        'float_dir': float_path,
        'config': float_path / "config",
        'input': float_path / "input", 
        'output': float_path / "output",
        'config_floats': float_path / "config" / "decArgo_config_floats",
        'json_float_info': float_path / "config" / "decArgo_config_floats" / "json_float_info",
        'json_float_meta': float_path / "config" / "decArgo_config_floats" / "json_float_meta_ir_sbd",
        'archive_cycle': float_path / "input" / "archive" / "cycle",
        'rsync_list': float_path / "input" / "rsync_list"
    }
   
    # Create all directories
    try:
        for name, path in directories.items():
            path.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created directory: {path}")
            
        print(f"Successfully created decoder directory structure for {float_wmo} at: {float_path.absolute()}")
        
        return {name: str(path.absolute()) for name, path in directories.items()}
        
    except Exception as e:
        logging.error(f"Error creating directories for {float_wmo}: {e}")
        raise
    
def get_volume_paths_for_float(float_dir_path):
    """
    Get the absolute paths for Docker volume mounts for a specific float.
    
    Args:
        float_dir_path (str or Path): Path to the specific float directory
        
    Returns:
        dict: Dictionary with volume mount paths
    """
    float_path = Path(float_dir_path).absolute()
    
    return {
        'input_volume': str(float_path / "input"),
        'config_volume': str(float_path / "config"), 
        'output_volume': str(float_path / "output"),
        'info_dir': str(float_path / "config" / "decArgo_config_floats" / "json_float_info"),
        'meta_dir': str(float_path / "config" / "decArgo_config_floats" / "json_float_meta_ir_sbd"),
        'archive_cycle_dir': str(float_path / "input" / "archive" / "cycle"),
        'rsync_list_dir': str(float_path / "input" / "rsync_list")
    }

def copy_rsync_list_files(src_dir: str, dst_dir: str):
    """Copy all files from src_dir into dst_dir."""
    os.makedirs(dst_dir, exist_ok=True)
    for item in os.listdir(src_dir):
        src_path = os.path.join(src_dir, item)
        dst_path = os.path.join(dst_dir, item)
        if os.path.isdir(src_path):
            # Copy directories recursively
            if os.path.exists(dst_path):
                shutil.rmtree(dst_path)  # remove existing dir first
            shutil.copytree(src_path, dst_path)
        else:
            # Copy individual files
            shutil.copy2(src_path, dst_path)

def cleanup_old_float_directories(base_dir="./decArgo", float_wmo=None):
    """
    Clean up old float directories, keeping only the most recent ones.
    
    Args:
        base_dir (str): Base directory to clean
        float_wmo (str): If provided, only clean directories for this specific float WMO
    """
    if float_wmo:
        base_path = Path(base_dir, float_wmo)
        if not base_path.exists():
            return
        
        float_dirs = [(d, d.stat().st_mtime) for d in base_path.iterdir() if d.is_dir()]
        float_dirs.sort(key=lambda x: x[1], reverse=True)  # Sort by modification time, newest first
        
        dirs_to_remove = float_dirs
        
        for dir_path, _ in dirs_to_remove:
            try:
                import shutil
                shutil.rmtree(dir_path)
                print(f"Removed old directory: {dir_path}")
            except Exception as e:
                print(f"Error removing {dir_path}: {e}")
                
def list_existing_float_directories(base_dir="./decArgo"):
    """
    List all existing float directories to avoid conflicts and see what's been processed.
    
    Args:
        base_dir (str): Base directory to search in
        
    Returns:
        list: List of existing float directory names
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        return []
    
    float_dirs = [d.name for d in base_path.iterdir() if d.is_dir() and d.name != '__pycache__']
    return sorted(float_dirs)