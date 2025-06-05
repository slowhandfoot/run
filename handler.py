import runpod
import os
import sys
import base64
import subprocess
import tempfile
import shutil
import requests
from typing import Dict, Any

# 確認 FaceFusion 安裝路徑
FACEFUSION_PATH = '/workspace/facefusion'
if os.path.exists(FACEFUSION_PATH):
    sys.path.append(FACEFUSION_PATH)
    print(f"FaceFusion found at: {FACEFUSION_PATH}")
else:
    print(f"Warning: FaceFusion not found at {FACEFUSION_PATH}")
    # 列出 workspace 內容幫助除錯
    print("Workspace contents:", os.listdir('/workspace'))

def download_file(url: str, path: str) -> bool:
    """下載檔案"""
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return True
    except Exception as e:
        print(f"Download error: {e}")
        return False

def find_facefusion_executable():
    """尋找 FaceFusion 執行檔"""
    possible_paths = [
        '/workspace/facefusion/run.py',
        '/workspace/facefusion/facefusion.py',
        '/workspace/facefusion/__main__.py',
        '/workspace/facefusion/app.py',
        '/workspace/facefusion/main.py'
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"Found FaceFusion executable at: {path}")
            return path
    
    # 如果都找不到，列出 facefusion 目錄內容
    if os.path.exists('/workspace/facefusion'):
        print("FaceFusion directory contents:", os.listdir('/workspace/facefusion'))
        # 尋找所有 .py 檔案
        py_files = [f for f in os.listdir('/workspace/facefusion') if f.endswith('.py')]
        if py_files:
            print(f"Python files found: {py_files}")
            # 嘗試使用第一個找到的 .py 檔案
            return os.path.join('/workspace/facefusion', py_files[0])
    
    return None

def process_video_swap(source: str, target: str, options: Dict = {}) -> Dict[str, Any]:
    """執行影片換臉"""
    temp_dir = tempfile.mkdtemp()
    
    try:
        # 準備檔案
        source_path = os.path.join(temp_dir, "source.jpg")
        target_path = os.path.join(temp_dir, "target.mp4")
        output_path = os.path.join(temp_dir, "output.mp4")
        
        # 處理輸入（支援 URL 或 base64）
        for data, path in [(source, source_path), (target, target_path)]:
            if data.startswith('http'):
                if not download_file(data, path):
                    return {"success": False, "error": "Download failed"}
            else:
                with open(path, 'wb') as f:
                    f.write(base64.b64decode(data))
        
        # 尋找 FaceFusion 執行檔
        facefusion_executable = find_facefusion_executable()
        if not facefusion_executable:
            return {
                "success": False,
                "error": "FaceFusion executable not found. Please check installation."
            }
        
        # 執行 FaceFusion - 使用更通用的參數
        cmd = [
            "python", facefusion_executable,
            "--source", source_path,
            "--target", target_path,
            "--output", output_path,
            "--headless"
        ]
        
        # 嘗試添加 execution provider（如果支援）
        try:
            cmd.extend(["--execution-providers", "cuda"])
        except:
            pass
        
        # 加入選項
        if options.get('enhance_face'):
            try:
                cmd.extend(['--frame-processors', 'face_swapper', 'face_enhancer'])
                cmd.extend(['--face-enhancer-model', 'gfpgan_1.4'])
            except:
                # 如果參數不支援，忽略
                pass
        
        print(f"Running command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, cwd='/workspace/facefusion')
        
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"Processing failed: {result.stderr or result.stdout or 'Unknown error'}"
            }
        
        # 返回結果
        if os.path.exists(output_path):
            with open(output_path, 'rb') as f:
                output_data = base64.b64encode(f.read()).decode()
            
            return {
                "success": True,
                "output": output_data,
                "size": os.path.getsize(output_path)
            }
        else:
            return {"success": False, "error": "No output generated"}
            
    except Exception as e:
        return {"success": False, "error": str(e)}
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

def handler(job):
    """RunPod Handler"""
    try:
        inputs = job['input']
        
        # 簡單的路由
        action = inputs.get('action', 'swap')
        
        if action == 'health':
            # 健康檢查時也確認 FaceFusion 狀態
            facefusion_status = "installed" if find_facefusion_executable() else "not found"
            return {
                "status": "healthy",
                "version": "1.0.0",
                "facefusion": facefusion_status
            }
        
        elif action == 'swap':
            # 驗證輸入
            if 'source' not in inputs or 'target' not in inputs:
                return {
                    "error": "Missing source or target"
                }
            
            # 檔案大小限制（通過 URL 大小簡單判斷）
            if not inputs['source'].startswith('http') and len(inputs['source']) > 10_000_000:
                return {"error": "Source image too large (max 10MB)"}
            
            if not inputs['target'].startswith('http') and len(inputs['target']) > 200_000_000:
                return {"error": "Target video too large (max 200MB)"}
            
            # 處理
            result = process_video_swap(
                inputs['source'],
                inputs['target'],
                inputs.get('options', {})
            )
            
            return result
            
        else:
            return {"error": "Unknown action"}
            
    except Exception as e:
        return {"error": str(e), "type": str(type(e))}

runpod.serverless.start({"handler": handler})
