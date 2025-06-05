import runpod
import os
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
                "python_path": os.sys.executable
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
                    subprocess.run(['wget', '-O', source_path, inputs['source']])
                else:
                    with open(source_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['source']))
                
                if inputs['target'].startswith('http'):
                    subprocess.run(['wget', '-O', target_path, inputs['target']])
                else:
                    with open(target_path, 'wb') as f:
                        f.write(base64.b64decode(inputs['target']))
                
                # 執行 FaceFusion
                cmd = [
                    'python', '/facefusion/run.py',
                    '--source', source_path,
                    '--target', target_path, 
                    '--output', output_path,
                    '--headless',
                    '--execution-providers', 'cuda'
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    return {
                        "success": False,
                        "error": result.stderr or result.stdout,
                        "command": ' '.join(cmd)
                    }
                
                # 讀取輸出
                if os.path.exists(output_path):
                    with open(output_path, 'rb') as f:
                        output_base64 = base64.b64encode(f.read()).decode()
                    
                    return {
                        "success": True,
                        "output": output_base64
                    }
                else:
                    return {
                        "success": False,
                        "error": "Output file not found"
                    }
        
        return {"error": "Unknown action"}
        
    except Exception as e:
        return {"error": str(e), "type": str(type(e))}

runpod.serverless.start({"handler": handler})
