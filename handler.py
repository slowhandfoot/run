import runpod
import os
import sys
import subprocess
import base64
import tempfile
import requests
import json
from pathlib import Path
import traceback
import time

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

def run_command(cmd, cwd='/workspace/facefusion', timeout=300):
    """執行命令並返回詳細結果"""
    try:
        print(f"Running command: {' '.join(cmd)} in {cwd}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout,
            env=dict(os.environ, PYTHONUNBUFFERED='1')
        )
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'cmd': ' '.join(cmd)
        }
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Command timeout',
            'cmd': ' '.join(cmd)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'cmd': ' '.join(cmd)
        }

def ensure_models_downloaded():
    """確保模型檔案已下載"""
    try:
        models_dir = '/workspace/facefusion/models'
        
        # 檢查是否已有模型檔案
        if os.path.exists(models_dir):
            onnx_files = list(Path(models_dir).glob('*.onnx'))
            if len(onnx_files) > 0:
                print(f"Found {len(onnx_files)} ONNX model files")
                return True
        
        print("No models found, attempting to download...")
        
        # 嘗試通過運行一個簡單的命令來觸發模型下載
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_source:
            # 創建一個小的測試圖片
            tmp_source.write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='))
            tmp_source_path = tmp_source.name
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tmp_target:
            tmp_target.write(base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=='))
            tmp_target_path = tmp_target.name
        
        try:
            # 嘗試運行 FaceFusion 來觸發模型下載，設定較長的超時時間
            cmd = [
                sys.executable, 'facefusion.py', 'headless-run',
                '--source', tmp_source_path,
                '--target', tmp_target_path,
                '--output', '/tmp/test_output.jpg',
                '--execution-providers', 'cpu'
            ]
            
            result = run_command(cmd, timeout=600)  # 10分鐘超時
            
            # 即使失敗也檢查是否下載了模型
            if os.path.exists(models_dir):
                onnx_files = list(Path(models_dir).glob('*.onnx'))
                if len(onnx_files) > 0:
                    print(f"Models downloaded successfully: {len(onnx_files)} files")
                    return True
            
            return False
            
        finally:
            # 清理臨時檔案
            try:
                os.unlink(tmp_source_path)
                os.unlink(tmp_target_path)
            except:
                pass
    
    except Exception as e:
        print(f"Model download error: {e}")
        return False

def find_output_files(base_paths, extensions=['.mp4', '.jpg', '.png']):
    """在多個路徑中查找輸出檔案"""
    found_files = []
    for base_path in base_paths:
        if os.path.exists(base_path):
            if os.path.isfile(base_path):
                found_files.append(base_path)
            elif os.path.isdir(base_path):
                for ext in extensions:
                    files = list(Path(base_path).glob(f'*{ext}'))
                    found_files.extend([str(f) for f in files])
    return found_files

def handler(job):
    """RunPod Handler - 最終版本"""
    try:
        inputs = job['input']
        action = inputs.get('action', 'swap')
        
        # === 健康檢查 ===
        if action == 'health':
            facefusion_exists = os.path.exists('/workspace/facefusion')
            
            # 檢查模型目錄和檔案
            models_dir = '/workspace/facefusion/models'
            models_exist = os.path.exists(models_dir)
            
            if models_exist:
                try:
                    model_files = list(Path(models_dir).glob('*.onnx'))
                    model_count = len(model_files)
                    model_names = [f.name for f in model_files[:5]]  # 前5個檔案名
                except:
                    model_count = 0
                    model_names = []
            else:
                model_count = 0
                model_names = []
            
            # 檢查 CUDA
            try:
                cuda_result = run_command([sys.executable, '-c', 'import torch; print(torch.cuda.is_available())'])
                cuda_available = 'True' in cuda_result.get('stdout', '')
            except:
                cuda_available = False
            
            return {
                "status": "healthy",
                "version": "5.0.0-final",
                "facefusion_installed": facefusion_exists,
                "working_directory": os.getcwd(),
                "python_path": sys.executable,
                "models_directory": models_exist,
                "model_files_count": model_count,
                "model_files_sample": model_names,
                "cuda_available": cuda_available
            }
        
        # === 探索模式 ===
        elif action == 'explore':
            exploration_results = {}
            
            # 1. FaceFusion 基本資訊
            help_result = run_command([sys.executable, 'facefusion.py', '--help'])
            exploration_results['facefusion_help'] = {
                'success': help_result.get('success', False),
                'stdout_preview': help_result.get('stdout', '')[:1000],
                'stderr_preview': help_result.get('stderr', '')[:500]
            }
            
            # 2. 目錄結構
            exploration_results['structure'] = {
                'facefusion_dir': os.path.exists('/workspace/facefusion'),
                'config_exists': os.path.exists('/workspace/facefusion/facefusion.ini'),
                'models_dir': os.path.exists('/workspace/facefusion/models'),
                'temp_dir': os.path.exists('/workspace/facefusion/.temp')
            }
            
            # 3. 模型檔案詳情
            models_dir = '/workspace/facefusion/models'
            if os.path.exists(models_dir):
                try:
                    all_files = list(Path(models_dir).rglob('*'))
                    exploration_results['model_details'] = {
                        'total_files': len(all_files),
                        'onnx_files': len([f for f in all_files if f.suffix == '.onnx']),
                        'file_list': [str(f.relative_to(models_dir)) for f in all_files[:20]]
                    }
                except Exception as e:
                    exploration_results['model_details'] = {'error': str(e)}
            
            return {
                "action": "explore",
                "exploration_results": exploration_results
            }
        
        # === 測試模式 ===
        elif action == 'test':
            test_cmd = inputs.get('command', [])
            if not test_cmd:
                return {"error": "No test command provided"}
            
            result = run_command(test_cmd)
            return {
                "action": "test",
                "result": result
            }
        
        # === 換臉功能 ===
        elif action == 'swap':
            print("Starting face swap process...")
            
            # 首先確保模型已下載
            if not ensure_models_downloaded():
                print("WARNING: Models may not be properly downloaded")
            
            # 建立臨時目錄
            with tempfile.TemporaryDirectory() as temp_dir:
                print(f"Working in temp directory: {temp_dir}")
                
                # 準備檔案路徑
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4")
                output_path = os.path.join(temp_dir, "output.mp4")
                
                # 檢查輸入
                if not inputs.get('source') or not inputs.get('target'):
                    return {"error": "Missing source or target"}
                
                # 處理來源檔案
                try:
                    if inputs['source'].startswith('http'):
                        if not download_file(inputs['source'], source_path):
                            return {"error": "Failed to download source"}
                    else:
                        with open(source_path, 'wb') as f:
                            f.write(base64.b64decode(inputs['source']))
                except Exception as e:
                    return {"error": f"Failed to process source: {str(e)}"}
                
                # 處理目標檔案
                try:
                    if inputs['target'].startswith('http'):
                        if not download_file(inputs['target'], target_path):
                            return {"error": "Failed to download target"}
                    else:
                        # 對於小的測試檔案，目標也可能是圖片
                        target_ext = '.jpg' if len(inputs['target']) < 1000 else '.mp4'
                        target_path = os.path.join(temp_dir, f"target{target_ext}")
                        with open(target_path, 'wb') as f:
                            f.write(base64.b64decode(inputs['target']))
                except Exception as e:
                    return {"error": f"Failed to process target: {str(e)}"}
                
                # 調整輸出檔案副檔名
                if target_path.endswith('.jpg'):
                    output_path = os.path.join(temp_dir, "output.jpg")
                
                # 驗證檔案
                if not os.path.exists(source_path) or os.path.getsize(source_path) == 0:
                    return {"error": "Invalid source file"}
                if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
                    return {"error": "Invalid target file"}
                
                print(f"Files ready - Source: {os.path.getsize(source_path)}B, Target: {os.path.getsize(target_path)}B")
                
                # 嘗試不同的處理策略
                strategies = [
                    {
                        'name': 'CPU execution',
                        'cmd': [sys.executable, 'facefusion.py', 'headless-run',
                               '--source', source_path,
                               '--target', target_path,
                               '--output', output_path,
                               '--execution-providers', 'cpu']
                    },
                    {
                        'name': 'CUDA execution',
                        'cmd': [sys.executable, 'facefusion.py', 'headless-run',
                               '--source', source_path,
                               '--target', target_path,
                               '--output', output_path,
                               '--execution-providers', 'cuda']
                    },
                    {
                        'name': 'Face swapper only',
                        'cmd': [sys.executable, 'facefusion.py', 'headless-run',
                               '--source', source_path,
                               '--target', target_path,
                               '--output', output_path,
                               '--processors', 'face_swapper',
                               '--execution-providers', 'cpu']
                    }
                ]
                
                all_results = []
                success_result = None
                
                for strategy in strategies:
                    print(f"\n=== Trying strategy: {strategy['name']} ===")
                    
                    result = run_command(strategy['cmd'], cwd='/workspace/facefusion', timeout=300)
                    
                    strategy_result = {
                        'name': strategy['name'],
                        'success': result['success'],
                        'returncode': result.get('returncode', -1),
                        'stdout_preview': result.get('stdout', '')[:1000],
                        'stderr_preview': result.get('stderr', '')[:1000],
                        'cmd': ' '.join(strategy['cmd'])
                    }
                    
                    all_results.append(strategy_result)
                    
                    if result['success'] and os.path.exists(output_path):
                        success_result = result
                        print(f"SUCCESS with strategy: {strategy['name']}")
                        break
                    else:
                        print(f"Strategy failed: {strategy['name']}")
                        if result.get('stderr'):
                            print(f"Error: {result['stderr'][:300]}")
                
                # 處理結果
                if success_result and os.path.exists(output_path) and os.path.getsize(output_path) > 100:
                    try:
                        with open(output_path, 'rb') as f:
                            output_base64 = base64.b64encode(f.read()).decode()
                        
                        return {
                            "success": True,
                            "output": output_base64,
                            "message": "Face swap completed successfully!",
                            "output_file": output_path,
                            "file_size": os.path.getsize(output_path),
                            "successful_strategy": [r for r in all_results if r['success']][0]['name'],
                            "all_attempts": all_results
                        }
                    except Exception as e:
                        return {
                            "success": False,
                            "error": f"Failed to read output file: {str(e)}",
                            "all_attempts": all_results
                        }
                
                # 失敗情況
                return {
                    "success": False,
                    "error": "All face swap strategies failed",
                    "all_attempts": all_results,
                    "debug_info": {
                        "output_exists": os.path.exists(output_path),
                        "output_size": os.path.getsize(output_path) if os.path.exists(output_path) else 0,
                        "temp_files": os.listdir(temp_dir)
                    }
                }
        
        return {"error": f"Unknown action: {action}"}
        
    except Exception as e:
        return {
            "error": str(e),
            "type": str(type(e).__name__),
            "traceback": traceback.format_exc()
        }

# 啟動時檢查
print("=== FaceFusion Handler Starting ===")
print(f"Python: {sys.executable}")
print(f"Working directory: {os.getcwd()}")
print(f"FaceFusion exists: {os.path.exists('/workspace/facefusion')}")

# 檢查模型目錄
models_dir = '/workspace/facefusion/models'
if os.path.exists(models_dir):
    model_files = list(Path(models_dir).glob('*.onnx'))
    print(f"Found {len(model_files)} ONNX models in {models_dir}")
else:
    print(f"Models directory {models_dir} does not exist")

print("=== Handler Ready ===")

runpod.serverless.start({"handler": handler})
