# 使用官方推薦的 PyTorch 基礎映像檔
FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

# 設定工作目錄
WORKDIR /workspace

# 安裝必要的系統工具，並在結束後清理快取以縮小映像檔體積
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# 從 GitHub 下載 FaceFusion 專案 (已修正為純文字網址)
RUN git clone https://github.com/facefusion/facefusion.git

# 進入 FaceFusion 目錄並安裝其依賴
WORKDIR /workspace/facefusion
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
# 執行 FaceFusion 安裝腳本，指定使用 CUDA，並跳過虛擬環境
RUN python install.py --onnxruntime cuda-11.8 --skip-venv || true

# 複製我們自己的 API 依賴設定檔
COPY requirements.txt /workspace/
# 安裝 API 依賴
RUN pip install -r /workspace/requirements.txt

# 複製我們的 API 處理程式
COPY handler.py /workspace/
WORKDIR /workspace

# 設定容器啟動時執行的命令
CMD ["python", "-u", "handler.py"]
