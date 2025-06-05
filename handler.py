import runpod
import os
import sys
import base64
import subprocess
import tempfile
import shutil
import requests
from typing import Dict, Any

# 將 FaceFusion 加入 Python 路徑
sys.path.insert(0, '/workspace/facefusion')

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
        
        # 方法1: 嘗試直接導入並使用 FaceFusion
        try:
            os.chdir('/workspace/facefusion')
            
            # 使用 python -m 方式執行
            cmd = [
                sys.executable, "-m", "facefusion",
                "--source", source_path,
                "--target", target_path,
                "--output", output_path,
                "--headless",
                "--execution-providers", "cuda"
            ]
            
            # 加入選項
            if options.get('enhance_face'):
                cmd.extend(['--frame-processors', 'face_swapper', 'face_enhancer'])
            
            print(f"Running command: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd='/workspace/facefusion')
            
        except Exception as e1:
            print(f"Method 1 failed: {e1}")
            
            # 方法2: 嘗試使用 run.py
            try:
                cmd = [
                    sys.executable, "run.py",
                    "--source", source_path,
                    "--target", target_path,
                    "--output", output_path,
                    "--headless",
                    "--execution-providers", "cuda"
                ]
                
                if options.get('enhance_face'):
                    cmd.extend(['--frame-processors', 'face_swapper', 'face_enhancer'])
                
                print(f"Running command (method 2): {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True, cwd='/workspace/facefusion')
                
            except Exception as e2:
                print(f"Method 2 failed: {e2}")
                
                # 方法3: 直接執行 Python 檔案
                main_file = None
                for possible_file in ['facefusion.py', '__main__.py', 'app.py', 'main.py']:
                    if os.path.exists(f'/workspace/facefusion/{possible_file}'):
                        main_file = possible_file
                        break
                
                if main_file:
                    cmd = [
                        sys.executable, f"/workspace/facefusion/{main_file}",
                        "--source", source_path,
                        "--target", target_path,
                        "--output", output_path,
                        "--headless"
                    ]
                    
                    print(f"Running command (method 3): {' '.join(cmd)}")
                    result = subprocess.run(cmd, capture_output=True, text=True)
                else:
                    return {
                        "success": False,
                        "error": "Cannot find FaceFusion executable. Files in directory: " + 
                                str(os.listdir('/workspace/facefusion'))
                    }
        
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
            # 檢查是否有其他可能的輸出檔案
            possible_outputs = [
                output_path,
                os.path.join(temp_dir, "output.mp4"),
                os.path.join(os.path.dirname(target_path), "output.mp4")
            ]
            
            for possible_output in possible_outputs:
                if os.path.exists(possible_output):
                    with open(possible_output, 'rb') as f:
                        output_data = base64.b64encode(f.read()).decode()
                    
                    return {
                        "success": True,
                        "output": output_data,
                        "size": os.path.getsize(possible_output)
                    }
            
            return {"success": False, "error": "No output generated"}
            
    except Exception as e:
        return {"success": False, "error": str(e), "type": str(type(e))}
    finally:
        os.chdir('/workspace')  # 返回原始目錄
        shutil.rmtree(temp_dir, ignore_errors=True)

def handler(job):
    """RunPod Handler"""
    try:
        inputs = job['input']
        
        # 簡單的路由
        action = inputs.get('action', 'swap')
        
        if action == 'health':
            # 健康檢查
            facefusion_installed = os.path.exists('/workspace/facefusion')
            files_in_facefusion = []
            if facefusion_installed:
                files_in_facefusion = os.listdir('/workspace/facefusion')[:10]  # 只列出前10個檔案
            
            return {
                "status": "healthy",
                "version": "1.0.0",
                "facefusion": "installed" if facefusion_installed else "not found",
                "facefusion_files": files_in_facefusion
            }
        
        elif action == 'swap':
            # 驗證輸入
            if 'source' not in inputs or 'target' not in inputs:
                return {
                    "error": "Missing source or target"
                }
            
            # 檔案大小限制（通過 base64 長度簡單判斷）
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
