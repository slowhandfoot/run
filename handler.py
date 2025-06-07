import runpod
import os
import sys
import subprocess
import base64
import tempfile
import requests
import json

def download_file(url, path):
    """下載檔案的輔助函數"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Download failed: {e}")
        return False

def explore_facefusion():
    """探索 FaceFusion 的正確使用方式"""
    exploration_results = {}
    
    # 1. 檢查幫助信息
    help_commands = [
        [sys.executable, '/facefusion/facefusion.py', '--help'],
        [sys.executable, '/facefusion/facefusion.py', 'headless-run', '--help'],
        [sys.executable, '/facefusion/facefusion.py', 'run', '--help']
    ]
    
    for cmd in help_commands:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            cmd_str = ' '.join(cmd[-2:])  # 簡化顯示
            exploration_results[f"help_{cmd_str}"] = {
                "stdout": result.stdout[:1000],
                "stderr": result.stderr[:500]
            }
        except Exception as e:
            exploration_results[f"help_{' '.join(cmd[-2:])}"] = str(e)
    
    # 2. 檢查配置檔案
    if os.path.exists('/facefusion/facefusion.ini'):
        try:
            with open('/facefusion/facefusion.ini', 'r') as f:
                exploration_results['config_content'] = f.read()[:500]
        except:
            pass
    
    return exploration_results

def handler(job):
    """RunPod Handler - 完整重構版"""
    try:
        inputs = job['input']
        action = inputs.get('action', 'swap')
        
        if action == 'health':
            # 基本健康檢查
            facefusion_exists = os.path.exists('/facefusion')
            return {
                "status": "healthy",
                "version": "4.0.0",
                "facefusion_installed": facefusion_exists,
                "working_directory": os.getcwd(),
                "python_path": sys.executable
            }
        
        elif action == 'explore':
            # 新增：探索模式，了解 FaceFusion 的正確用法
            os.chdir('/facefusion')
            exploration = explore_facefusion()
            os.chdir('/workspace')
            
            return {
                "action": "explore",
                "exploration_results": exploration,
                "facefusion_files": os.listdir('/facefusion')[:20]
            }
        
        elif action == 'swap':
            # 創建臨時目錄
            with tempfile.TemporaryDirectory() as temp_dir:
                # 1. 下載檔案
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4") 
                output_path = os.path.join(temp_dir, "output.mp4")
                
                # 處理輸入檔案
                for file_type, file_path, input_data in [
                    ('source', source_path, inputs.get('source')),
                    ('target', target_path, inputs.get('target'))
                ]:
                    if not input_data:
                        return {"success": False, "error": f"Missing {file_type} input"}
                    
                    if input_data.startswith('http'):
                        if not download_file(input_data, file_path):
                            return {"success": False, "error": f"Failed to download {file_type}"}
                    else:
                        try:
                            with open(file_path, 'wb') as f:
                                f.write(base64.b64decode(input_data))
                        except Exception as e:
                            return {"success": False, "error": f"Failed to decode {file_type}: {str(e)}"}
                
                # 驗證檔案
                for file_type, file_path in [('source', source_path), ('target', target_path)]:
                    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
                        return {"success": False, "error": f"{file_type} file is invalid"}
                
                print(f"Files ready - Source: {os.path.getsize(source_path)}B, Target: {os.path.getsize(target_path)}B")
                
                # 2. 執行 FaceFusion
                os.chdir('/facefusion')
                
                # 根據之前的錯誤，我們知道需要探索正確的參數格式
                # 這裡嘗試最可能的幾種方式
                attempts = []
                
                # 嘗試 1: 最基本的格式
                attempt1 = {
                    "name": "Basic headless-run",
                    "cmd": [sys.executable, 'facefusion.py', 'headless-run',
                           '--source', source_path,
                           '--target', target_path,
                           '--output', output_path]
                }
                
                # 嘗試 2: 使用配置檔案
                attempt2 = {
                    "name": "With config",
                    "cmd": [sys.executable, 'facefusion.py', 'headless-run',
                           '--config-path', 'facefusion.ini',
                           '--source', source_path,
                           '--target', target_path,
                           '--output', output_path]
                }
                
                # 嘗試 3: 使用環境變數和參數
                attempt3 = {
                    "name": "With environment",
                    "cmd": [sys.executable, 'facefusion.py', 'run',
                           '--source', source_path,
                           '--target', target_path,
                           '--output', output_path,
                           '--execution-providers', 'cpu',  # 先用 CPU 測試
                           '--skip-download'],
                    "env": {
                        "GRADIO_SERVER_NAME": "0.0.0.0",
                        "GRADIO_SERVER_PORT": "7860"
                    }
                }
                
                attempts = [attempt1, attempt2, attempt3]
                
                # 執行嘗試
                best_result = None
                all_attempts_info = []
                
                for i, attempt in enumerate(attempts):
                    print(f"\n=== Attempt {i+1}: {attempt['name']} ===")
                    
                    env = os.environ.copy()
                    if 'env' in attempt:
                        env.update(attempt['env'])
                    
                    try:
                        result = subprocess.run(
                            attempt['cmd'],
                            capture_output=True,
                            text=True,
                            timeout=300,
                            env=env
                        )
                        
                        attempt_info = {
                            "name": attempt['name'],
                            "return_code": result.returncode,
                            "stdout_preview": result.stdout[:300],
                            "stderr_preview": result.stderr[:300]
                        }
                        all_attempts_info.append(attempt_info)
                        
                        print(f"Return code: {result.returncode}")
                        
                        if result.returncode == 0:
                            best_result = result
                            break
                            
                    except Exception as e:
                        all_attempts_info.append({
                            "name": attempt['name'],
                            "error": str(e)
                        })
                
                os.chdir('/workspace')
                
                # 3. 檢查結果
                if best_result and best_result.returncode == 0:
                    # 查找輸出檔案
                    search_paths = [
                        output_path,
                        os.path.join('/facefusion', 'output.mp4'),
                        os.path.join(temp_dir, 'output.mp4'),
                        '/facefusion/.temp/output.mp4'
                    ]
                    
                    # 也檢查臨時目錄中的所有 mp4
                    temp_mp4s = [os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.endswith('.mp4')]
                    search_paths.extend(temp_mp4s)
                    
                    for path in search_paths:
                        if os.path.exists(path) and os.path.getsize(path) > 0:
                            with open(path, 'rb') as f:
                                output_base64 = base64.b64encode(f.read()).decode()
                            
                            return {
                                "success": True,
                                "output": output_base64,
                                "message": "Face swap completed!",
                                "output_path": path,
                                "file_size": os.path.getsize(path)
                            }
                    
                    # 輸出檔案未找到
                    return {
                        "success": False,
                        "error": "Process completed but output not found",
                        "searched_paths": search_paths,
                        "temp_files": os.listdir(temp_dir),
                        "stdout": best_result.stdout[:500]
                    }
                else:
                    # 所有嘗試都失敗
                    return {
                        "success": False,
                        "error": "All attempts failed",
                        "attempts": all_attempts_info,
                        "suggestion": "Try 'explore' action first to understand the correct parameters"
                    }
        
        return {"error": f"Unknown action: {action}"}
        
    except Exception as e:
        import traceback
        return {
            "error": str(e), 
            "type": str(type(e).__name__),
            "traceback": traceback.format_exc()[:1000]
        }

runpod.serverless.start({"handler": handler})
