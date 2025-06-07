import runpod
import os
import sys
import subprocess
import base64
import tempfile
import requests
import json
from pathlib import Path

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

def run_command(cmd, cwd='/facefusion', timeout=300):
    """執行命令並返回詳細結果"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=cwd,
            timeout=timeout
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
            'error': 'Timeout',
            'cmd': ' '.join(cmd)
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'cmd': ' '.join(cmd)
        }

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
    """RunPod Handler - 漸進式測試版本"""
    try:
        inputs = job['input']
        action = inputs.get('action', 'swap')
        
        # === 健康檢查 ===
        if action == 'health':
            facefusion_exists = os.path.exists('/facefusion')
            return {
                "status": "healthy",
                "version": "5.0.0-progressive",
                "facefusion_installed": facefusion_exists,
                "working_directory": os.getcwd(),
                "python_path": sys.executable
            }
        
        # === 探索模式 ===
        elif action == 'explore':
            exploration_results = {}
            
            # 1. 基本幫助
            help_cmds = [
                ['--help'],
                ['headless-run', '--help'],
                ['run', '--help']
            ]
            
            for help_cmd in help_cmds:
                cmd = [sys.executable, '/facefusion/facefusion.py'] + help_cmd
                result = run_command(cmd)
                key = '_'.join(help_cmd)
                exploration_results[f'help_{key}'] = {
                    'stdout': result.get('stdout', '')[:1000],
                    'stderr': result.get('stderr', '')[:500]
                }
            
            # 2. 尋找更多參數（透過錯誤訊息）
            test_cmd = [sys.executable, '/facefusion/facefusion.py', 'headless-run', 
                       '-s', 'dummy.jpg', '-t', 'dummy.mp4', '--help']
            result = run_command(test_cmd)
            exploration_results['detailed_params'] = {
                'stdout': result.get('stdout', ''),
                'stderr': result.get('stderr', '')
            }
            
            # 3. 檢查配置和目錄結構
            exploration_results['structure'] = {
                'config_exists': os.path.exists('/facefusion/facefusion.ini'),
                'models_dir': os.path.exists('/facefusion/models'),
                'temp_exists': os.path.exists('/facefusion/.temp')
            }
            
            return {
                "action": "explore",
                "exploration_results": exploration_results
            }
        
        # === 測試模式 - 新增 ===
        elif action == 'test':
            # 用於測試特定命令組合
            test_cmd = inputs.get('command', [])
            if not test_cmd:
                return {"error": "No test command provided"}
            
            # 如果命令不是完整路徑，補充完整路徑
            if not test_cmd[0].startswith('/'):
                test_cmd = [sys.executable, '/facefusion/facefusion.py'] + test_cmd
            
            result = run_command(test_cmd)
            return {
                "action": "test",
                "result": result
            }
        
        # === 換臉功能 ===
        elif action == 'swap':
            # 建立臨時目錄
            with tempfile.TemporaryDirectory() as temp_dir:
                # 1. 準備檔案
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4")
                output_path = os.path.join(temp_dir, "output.mp4")
                
                # 下載或解碼檔案
                if not inputs.get('source') or not inputs.get('target'):
                    return {"error": "Missing source or target"}
                
                # 處理 source
                if inputs['source'].startswith('http'):
                    if not download_file(inputs['source'], source_path):
                        return {"error": "Failed to download source"}
                else:
                    try:
                        with open(source_path, 'wb') as f:
                            f.write(base64.b64decode(inputs['source']))
                    except:
                        return {"error": "Failed to decode source"}
                
                # 處理 target
                if inputs['target'].startswith('http'):
                    if not download_file(inputs['target'], target_path):
                        return {"error": "Failed to download target"}
                else:
                    try:
                        with open(target_path, 'wb') as f:
                            f.write(base64.b64decode(inputs['target']))
                    except:
                        return {"error": "Failed to decode target"}
                
                # 驗證檔案存在
                if not os.path.exists(source_path) or os.path.getsize(source_path) == 0:
                    return {"error": "Invalid source file"}
                if not os.path.exists(target_path) or os.path.getsize(target_path) == 0:
                    return {"error": "Invalid target file"}
                
                print(f"Files ready - Source: {os.path.getsize(source_path)}B, Target: {os.path.getsize(target_path)}B")
                
                # 2. 漸進式嘗試不同的命令組合
                attempts = []
                
                # 策略1: 最基本的命令
                attempts.append({
                    'name': 'Basic command',
                    'cmd': [sys.executable, '/facefusion/facefusion.py', 'headless-run',
                           '-s', source_path,
                           '-t', target_path,
                           '-o', output_path]
                })
                
                # 策略2: 加入 skip-download 避免下載模型
                attempts.append({
                    'name': 'Skip download',
                    'cmd': [sys.executable, '/facefusion/facefusion.py', 'headless-run',
                           '-s', source_path,
                           '-t', target_path,
                           '-o', output_path,
                           '--skip-download']
                })
                
                # 策略3: 指定處理器 (face_swapper)
                attempts.append({
                    'name': 'With face_swapper',
                    'cmd': [sys.executable, '/facefusion/facefusion.py', 'headless-run',
                           '-s', source_path,
                           '-t', target_path,
                           '-o', output_path,
                           '--processors', 'face_swapper']
                })
                
                # 策略4: 使用配置檔案
                if os.path.exists('/facefusion/facefusion.ini'):
                    attempts.append({
                        'name': 'With config',
                        'cmd': [sys.executable, '/facefusion/facefusion.py', 'headless-run',
                               '--config-path', '/facefusion/facefusion.ini',
                               '-s', source_path,
                               '-t', target_path,
                               '-o', output_path]
                    })
                
                # 策略5: 指定執行提供者
                for provider in ['cuda', 'cpu']:
                    attempts.append({
                        'name': f'With {provider}',
                        'cmd': [sys.executable, '/facefusion/facefusion.py', 'headless-run',
                               '-s', source_path,
                               '-t', target_path,
                               '-o', output_path,
                               '--execution-providers', provider]
                    })
                
                # 執行所有嘗試
                all_results = []
                success_result = None
                
                for attempt in attempts:
                    print(f"\n=== Trying: {attempt['name']} ===")
                    result = run_command(attempt['cmd'])
                    
                    result_info = {
                        'name': attempt['name'],
                        'success': result['success'],
                        'returncode': result.get('returncode', -1),
                        'error': result.get('error', ''),
                        'stderr_preview': result.get('stderr', '')[:300]
                    }
                    
                    # 如果有特定的錯誤訊息，提取關鍵資訊
                    stderr = result.get('stderr', '')
                    if 'no module named' in stderr.lower():
                        result_info['missing_module'] = True
                    if 'usage:' in stderr:
                        result_info['usage_error'] = True
                        
                    all_results.append(result_info)
                    
                    if result['success']:
                        success_result = result
                        print(f"Success with: {attempt['name']}")
                        break
                    else:
                        print(f"Failed: {result.get('stderr', '')[:200]}")
                
                # 3. 處理結果
                if success_result:
                    # 尋找輸出檔案
                    possible_paths = [
                        output_path,
                        '/facefusion/.temp/output.mp4',
                        os.path.join(temp_dir, 'output.mp4')
                    ]
                    
                    # 也檢查 facefusion 目錄下的新檔案
                    found_files = find_output_files(possible_paths + ['/facefusion/.temp', temp_dir])
                    
                    for file_path in found_files:
                        if os.path.exists(file_path) and os.path.getsize(file_path) > 1000:  # 至少 1KB
                            with open(file_path, 'rb') as f:
                                output_base64 = base64.b64encode(f.read()).decode()
                            
                            return {
                                "success": True,
                                "output": output_base64,
                                "message": "Face swap completed!",
                                "output_location": file_path,
                                "file_size": os.path.getsize(file_path),
                                "successful_strategy": [r for r in all_results if r['success']][0]['name']
                            }
                    
                    # 成功執行但找不到輸出
                    return {
                        "success": False,
                        "error": "Process completed but output not found",
                        "searched_files": found_files,
                        "attempts": all_results,
                        "stdout": success_result.get('stdout', '')[:500]
                    }
                
                # 所有嘗試都失敗
                return {
                    "success": False,
                    "error": "All strategies failed",
                    "attempts": all_results,
                    "suggestion": "Use 'test' action with custom command to debug"
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
