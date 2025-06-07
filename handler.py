    import runpod
    import os
    import sys
    import subprocess
    import base64
    import tempfile
    import requests
    from pathlib import Path

    def download_file(url, path):
        """下載檔案並檢查是否成功"""
        try:
            print(f"Downloading from {url} to {path}...")
            response = requests.get(url, timeout=60)
            response.raise_for_status()
            with open(path, 'wb') as f:
                f.write(response.content)
            
            if os.path.getsize(path) > 0:
                print("Download successful.")
                return True
            else:
                print("Download failed: file is empty.")
                return False
        except Exception as e:
            print(f"Download failed: {e}")
            return False

    def run_command(cmd, cwd):
        """執行命令並返回詳細結果"""
        print(f"Executing command: {' '.join(cmd)} in {cwd}")
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, cwd=cwd, timeout=600 # 延長超時時間
            )
            return {
                'success': result.returncode == 0,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def find_output_file(search_dir):
        """在指定目錄中查找唯一的媒體輸出檔"""
        for ext in ['.mp4', '.jpg', '.png']:
            files = list(Path(search_dir).glob(f'*{ext}'))
            if files and os.path.getsize(files[0]) > 1000:
                return str(files[0])
        return None

    def handler(job):
        """RunPod Serverless Handler"""
        try:
            inputs = job['input']
            with tempfile.TemporaryDirectory() as temp_dir:
                source_path = os.path.join(temp_dir, "source.jpg")
                target_path = os.path.join(temp_dir, "target.mp4")
                output_dir = os.path.join(temp_dir, "output")
                os.makedirs(output_dir)

                source_url = inputs.get('source')
                target_url = inputs.get('target')

                if not source_url or not target_url:
                    return {"error": "缺少 'source' 或 'target' 的 URL。"}

                if not download_file(source_url, source_path):
                    return {"error": f"下載來源圖片失敗: {source_url}"}
                
                if not download_file(target_url, target_path):
                    return {"error": f"下載目標影片失敗: {target_url}"}

                ff_cmd = [
                    sys.executable, 'facefusion.py',
                    '--headless',
                    '--source', source_path,
                    '--target', target_path,
                    '--output-path', output_dir,
                    '--skip-download'
                ]
                
                result = run_command(ff_cmd, cwd='/workspace/facefusion')

                if not result['success']:
                    return {
                        "success": False,
                        "error": "FaceFusion 處理失敗。",
                        "details": {
                            "stdout": result.get('stdout', '')[-1500:],
                            "stderr": result.get('stderr', '')[-1500:]
                        }
                    }

                found_output_path = find_output_file(output_dir)
                if found_output_path:
                    with open(found_output_path, 'rb') as f:
                        output_base64 = base64.b64encode(f.read()).decode('utf-8')
                    return {"success": True, "output": output_base64}

                return {
                    "success": False,
                    "error": "處理完成，但找不到輸出檔案。",
                    "details": {"stdout": result.get('stdout', '')[-1500:]}
                }
        except Exception as e:
            return {"error": f"發生未知錯誤: {str(e)}"}

    runpod.serverless.start({"handler": handler})
