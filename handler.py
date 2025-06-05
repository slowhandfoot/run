import runpod
import os
import sys
import base64
import subprocess
import tempfile
import shutil
import requests
from typing import Dict, Any

sys.path.append('/workspace/facefusion')

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
        
        # 執行 FaceFusion
        cmd = [
            "python", "/workspace/facefusion/run.py",
            "--source", source_path,
            "--target", target_path,
            "--output", output_path,
            "--execution-providers", "cuda",
            "--headless",
            "--skip-download"
        ]
        
        # 加入選項
        if options.get('enhance_face'):
            cmd.extend(['--frame-processors', 'face_swapper', 'face_enhancer'])
            cmd.extend(['--face-enhancer-model', 'gfpgan_1.4'])
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": result.stderr or "Processing failed"
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
            return {
                "status": "healthy",
                "version": "1.0.0"
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
        return {"error": str(e)}

runpod.serverless.start({"handler": handler})
