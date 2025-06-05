import runpod
import os
import sys
import subprocess
import base64
import tempfile

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
            
            return {
                "status": "healthy",
                "facefusion_installed": facefusion_exists,
                "facefusion_files": files,
                "working_directory": os.getcwd(),
                "python_path": sys.executable
            }
        
        elif action == 'swap':
            # 創建臨時目錄
            with tempfile.TemporaryDirectory() as temp_dir:
                # 保存輸入檔案
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4") 
                output_path = os.path.join(temp_dir, "output.mp4")
                
                # 解碼 base64 輸入
                if inputs['source'].startswith('http'):
                    # 如果是 URL，下載檔案
                    subprocess.run(['wget', '-O', source_path, inputs['source']], check=True)
                else:
                    with open(source_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['source']))
                
                if inputs['target'].startswith('http'):
                    subprocess.run(['wget', '-O', target_path, inputs['target']], check=True)
                else:
                    with open(target_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['target']))
                
                # 使用 python -m 執行 FaceFusion
                os.chdir('/facefusion')
                
                # 嘗試不同的執行方式
                cmd_options = [
                    # 方式1: 作為模組執行
                    [sys.executable, '-m', 'facefusion'],
                    # 方式2: 執行 __main__.py
                    [sys.executable, '__main__.py'],
                    # 方式3: 執行 facefusion.py
                    [sys.executable, 'facefusion.py'],
                    # 方式4: 直接執行目錄
                    [sys.executable, '.']
                ]
                
                result = None
                successful_cmd = None
                
                for cmd_base in cmd_options:
                    try:
                        cmd = cmd_base + [
                            '--source', source_path,
                            '--target', target_path, 
                            '--output', output_path,
                            '--headless',
                            '--execution-providers', 'cuda'
                        ]
                        
                        print(f"Trying command: {' '.join(cmd)}")
                        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                        
                        if result.returncode == 0:
                            successful_cmd = cmd
                            break
                        else:
                            print(f"Command failed with return code {result.returncode}")
                            print(f"Error: {result.stderr[:500]}")
                    except Exception as e:
                        print(f"Command exception: {e}")
                        continue
                
                os.chdir('/')  # 返回根目錄
                
                if result is None or result.returncode != 0:
                    return {
                        "success": False,
                        "error": "All execution methods failed",
                        "last_error": result.stderr if result else "No result",
                        "files_in_facefusion": os.listdir('/facefusion')[:20]
                    }
                
                # 檢查輸出
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        output_base64 = base64.b64encode(f.read()).decode()
                    
                    return {
                        "success": True,
                        "output": output_base64,
                        "command_used": ' '.join(successful_cmd)
                    }
                else:
                    # 檢查其他可能的輸出位置
                    possible_outputs = [
                        output_path,
                        '/facefusion/output.mp4',
                        os.path.join(temp_dir, 'output.mp4')
                    ]
                    
                    for possible in possible_outputs:
                        if os.path.exists(possible):
                            with open(possible, 'rb') as f:
                                output_base64 = base64.b64encode(f.read()).decode()
                            return {
                                "success": True,
                                "output": output_base64,
                                "found_at": possible
                            }
                    
                    return {
                        "success": False,
                        "error": "Output file not found after processing"
                    }
        
        return {"error": "Unknown action"}
        
    except Exception as e:
        return {"error": str(e), "type": str(type(e))}

runpod.serverless.start({"handler": handler})
