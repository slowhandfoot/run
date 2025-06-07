import runpod
import os
import sys
import subprocess
import base64
import tempfile
import requests

def download_file(url, path):
    """下載檔案的輔助函數，支援多種方式"""
    try:
        # 方法 1: 使用 requests
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        with open(path, 'wb') as f:
            f.write(response.content)
        return True
    except Exception as e:
        print(f"Requests download failed: {e}")
        
        # 方法 2: 使用 wget
        try:
            result = subprocess.run(['wget', '-O', path, url], 
                                    capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True
            print(f"Wget failed: {result.stderr}")
        except Exception as e2:
            print(f"Wget error: {e2}")
            
        # 方法 3: 使用 curl
        try:
            result = subprocess.run(['curl', '-L', '-o', path, url], 
                                    capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True
            print(f"Curl failed: {result.stderr}")
        except Exception as e3:
            print(f"Curl error: {e3}")
    
    return False

def handler(job):
    """RunPod Handler"""
    try:
        inputs = job['input']
        action = inputs.get('action', 'swap')
        
        if action == 'health':
            # 檢查 FaceFusion 是否存在
            facefusion_exists = os.path.exists('/facefusion')
            files = []
            if facefusion_exists:
                files = os.listdir('/facefusion')[:10]
            
            # 檢查必要工具
            tools_status = {}
            for tool in ['wget', 'curl', 'ffmpeg']:
                try:
                    subprocess.run([tool, '--version'], capture_output=True, timeout=5)
                    tools_status[tool] = True
                except:
                    tools_status[tool] = False
            
            # 檢查 FaceFusion 結構
            facefusion_structure = {}
            if facefusion_exists:
                # 檢查是否有 facefusion 子目錄
                facefusion_subdir = os.path.exists('/facefusion/facefusion')
                if facefusion_subdir:
                    facefusion_structure['has_subdir'] = True
                    facefusion_structure['subdir_files'] = os.listdir('/facefusion/facefusion')[:5]
                
                # 檢查各種可能的入口點
                facefusion_structure['has_facefusion_py'] = os.path.exists('/facefusion/facefusion.py')
                facefusion_structure['has_main_py'] = os.path.exists('/facefusion/__main__.py')
                facefusion_structure['has_run_py'] = os.path.exists('/facefusion/run.py')
            
            return {
                "status": "healthy",
                "facefusion_installed": facefusion_exists,
                "facefusion_files": files,
                "facefusion_structure": facefusion_structure,
                "working_directory": os.getcwd(),
                "python_path": sys.executable,
                "tools_available": tools_status,
                "requests_module": 'requests' in sys.modules or True
            }
        
        elif action == 'swap':
            # 創建臨時目錄
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存輸入檔案
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4") 
                output_path = os.path.join(temp_dir, "output.mp4")
                
                # 處理 source
                if inputs['source'].startswith('http'):
                    print(f"Downloading source from: {inputs['source']}")
                    if not download_file(inputs['source'], source_path):
                        return {
                            "success": False,
                            "error": "Failed to download source file"
                        }
                else:
                    with open(source_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['source']))
                
                # 處理 target
                if inputs['target'].startswith('http'):
                    print(f"Downloading target from: {inputs['target']}")
                    if not download_file(inputs['target'], target_path):
                        return {
                            "success": False,
                            "error": "Failed to download target file"
                        }
                else:
                    with open(target_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['target']))
                
                # 檢查檔案是否存在
                if not os.path.exists(source_path):
                    return {"success": False, "error": "Source file not created"}
                if not os.path.exists(target_path):
                    return {"success": False, "error": "Target file not created"}
                
                print(f"Source size: {os.path.getsize(source_path)} bytes")
                print(f"Target size: {os.path.getsize(target_path)} bytes")
                
                # 設定 Python 路徑
                original_pythonpath = os.environ.get('PYTHONPATH', '')
                os.environ['PYTHONPATH'] = '/facefusion:' + original_pythonpath
                
                # 嘗試不同的執行方式
                cmd_options = []
                
                # 如果有 facefusion 子目錄，添加相應的執行方式
                if os.path.exists('/facefusion/facefusion'):
                    cmd_options.extend([
                        # 使用 PYTHONPATH 和 -m
                        [sys.executable, '-m', 'facefusion'],
                        # 直接執行子目錄
                        [sys.executable, '-m', 'facefusion.facefusion'],
                    ])
                
                # 標準執行方式
                cmd_options.extend([
                    # 直接執行 facefusion.py
                    [sys.executable, '/facefusion/facefusion.py'],
                    # 使用絕對路徑
                    ['python', '/facefusion/facefusion.py'],
                    # 嘗試作為腳本執行
                    ['python3', '/facefusion/facefusion.py'],
                ])
                
                result = None
                successful_cmd = None
                all_errors = []
                
                for i, cmd_base in enumerate(cmd_options):
                    try:
                        # 切換到 facefusion 目錄
                        os.chdir('/facefusion')
                        
                        cmd = cmd_base + [
                            '--source', source_path,
                            '--target', target_path, 
                            '--output', output_path,
                            '--headless',
                            '--execution-providers', 'cuda'
                        ]
                        
                        print(f"Attempt {i+1}: {' '.join(cmd)}")
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        
                        if result.returncode == 0:
                            successful_cmd = cmd
                            print(f"Success with command: {' '.join(cmd_base)}")
                            break
                        else:
                            error_msg = f"Command {i+1} failed: {result.stderr[:200]}"
                            print(error_msg)
                            all_errors.append(error_msg)
                    except Exception as e:
                        error_msg = f"Command {i+1} exception: {str(e)}"
                        print(error_msg)
                        all_errors.append(error_msg)
                        continue
                    finally:
                        # 確保回到原始目錄
                        os.chdir('/workspace')
                
                # 恢復原始 PYTHONPATH
                os.environ['PYTHONPATH'] = original_pythonpath
                
                if result is None or result.returncode != 0:
                    # 提供更詳細的錯誤信息
                    return {
                        "success": False,
                        "error": "All execution methods failed",
                        "all_errors": all_errors,
                        "last_stderr": result.stderr if result else "No result",
                        "files_in_facefusion": os.listdir('/facefusion')[:20],
                        "python_paths": sys.path[:5]
                    }
                
                # 檢查輸出
                possible_outputs = [
                    output_path,
                    '/facefusion/output.mp4',
                    os.path.join(temp_dir, 'output.mp4'),
                    '/facefusion/.temp/output.mp4',
                    '/workspace/output.mp4'
                ]
                
                for possible in possible_outputs:
                    if os.path.exists(possible):
                        with open(possible, 'rb') as f:
                            output_base64 = base64.b64encode(f.read()).decode()
                        return {
                            "success": True,
                            "output": output_base64,
                            "command_used": ' '.join(successful_cmd),
                            "found_at": possible
                        }
                
                return {
                    "success": False,
                    "error": "Output file not found after processing",
                    "checked_paths": possible_outputs
                }
        
        return {"error": "Unknown action"}
        
    except Exception as e:
        import traceback
        return {
            "error": str(e), 
            "type": str(type(e)),
            "traceback": traceback.format_exc()
        }

runpod.serverless.start({"handler": handler})
