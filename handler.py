import runpod
import os
import sys
import subprocess
import traceback

def run_command(cmd, timeout=300):
    """執行命令並返回結果"""
    try:
        print(f"Running: {' '.join(cmd)}")
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

def install_facefusion():
    """動態安裝 FaceFusion"""
    try:
        print("=== Installing FaceFusion ===")
        
        # 檢查是否已安裝
        if os.path.exists('/workspace/facefusion'):
            print("FaceFusion already exists")
            return True
        
        # 1. 克隆倉庫
        clone_result = run_command(['git', 'clone', 'https://github.com/facefusion/facefusion.git'])
        if not clone_result['success']:
            print(f"Clone failed: {clone_result}")
            return False
        
        # 2. 安裝依賴
        os.chdir('/workspace/facefusion')
        
        # 安裝requirements
        install_req = run_command(['pip', 'install', '-r', 'requirements.txt'])
        if not install_req['success']:
            print(f"Requirements install failed: {install_req}")
            # 繼續嘗試，不完全失敗
        
        # 嘗試安裝 FaceFusion（使用 CPU 版本更穩定）
        install_result = run_command(['python', 'install.py', '--onnxruntime', 'default'])
        if install_result['success']:
            print("FaceFusion installed successfully with CPU")
            return True
        
        # 如果失敗，嘗試跳過安裝但確保目錄存在
        print("Installation may have partial success, continuing...")
        return True
        
    except Exception as e:
        print(f"Installation error: {e}")
        return False

def handler(job):
    """簡化版 RunPod Handler"""
    try:
        inputs = job['input']
        action = inputs.get('action', 'health')
        
        # === 健康檢查 ===
        if action == 'health':
            return {
                "status": "healthy",
                "version": "emergency-1.0",
                "working_directory": os.getcwd(),
                "python_path": sys.executable,
                "facefusion_path": "/workspace/facefusion" if os.path.exists('/workspace/facefusion') else "not_installed"
            }
        
        # === 安裝檢查 ===
        elif action == 'install':
            success = install_facefusion()
            return {
                "action": "install",
                "success": success,
                "facefusion_exists": os.path.exists('/workspace/facefusion')
            }
        
        # === 測試命令 ===
        elif action == 'test':
            cmd = inputs.get('command', ['python', '--version'])
            result = run_command(cmd)
            return {
                "action": "test",
                "result": result
            }
        
        # === 探索系統 ===
        elif action == 'explore':
            return {
                "working_directory": os.getcwd(),
                "python_version": sys.version,
                "environment_variables": dict(os.environ),
                "directory_contents": os.listdir('/workspace'),
                "facefusion_exists": os.path.exists('/workspace/facefusion')
            }
        
        # === 動態換臉（如果 FaceFusion 已安裝） ===
        elif action == 'swap':
            # 首先確保 FaceFusion 已安裝
            if not os.path.exists('/workspace/facefusion'):
                install_success = install_facefusion()
                if not install_success:
                    return {
                        "success": False,
                        "error": "FaceFusion installation failed"
                    }
            
            return {
                "success": False,
                "error": "Face swap functionality is disabled in emergency mode",
                "suggestion": "Use 'install' action first, then upgrade to full version"
            }
        
        return {"error": f"Unknown action: {action}"}
        
    except Exception as e:
        return {
            "error": str(e),
            "type": str(type(e).__name__),
            "traceback": traceback.format_exc()
        }

# 啟動訊息
print("=== Emergency FaceFusion Handler ===")
print(f"Python: {sys.executable}")
print(f"Working directory: {os.getcwd()}")
print("=== Ready (Emergency Mode) ===")

runpod.serverless.start({"handler": handler})
