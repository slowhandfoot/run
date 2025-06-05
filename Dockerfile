FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    git \
    git-lfs \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    python3-opencv \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 安裝 Python 依賴
RUN pip install --upgrade pip setuptools wheel

# 克隆 FaceFusion (使用特定版本以確保穩定性)
RUN git clone https://github.com/facefusion/facefusion.git /workspace/facefusion
WORKDIR /workspace/facefusion

# 安裝 FaceFusion 依賴
RUN pip install -r requirements.txt --no-cache-dir

# 安裝 onnxruntime-gpu
RUN pip install onnxruntime-gpu==1.16.3 --no-cache-dir

# 下載必要的模型
RUN python install.py --onnxruntime cuda --skip-conda

# 安裝 API 依賴
COPY requirements.txt /workspace/
RUN pip install -r /workspace/requirements.txt --no-cache-dir

# 複製處理程式
COPY handler.py /workspace/

# 設定工作目錄
WORKDIR /workspace

# 測試 FaceFusion 是否正確安裝
RUN python -c "import sys; sys.path.append('/workspace/facefusion'); print('FaceFusion path test passed')"

# 列出 facefusion 目錄內容以便除錯
RUN ls -la /workspace/facefusion/

CMD ["python", "-u", "handler.py"]
