FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    git ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 python3-opencv wget curl \
    && rm -rf /var/lib/apt/lists/*

# 安裝 FaceFusion
RUN git clone https://github.com/facefusion/facefusion.git
WORKDIR /workspace/facefusion

# 升級 pip 並安裝依賴
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 重要：安裝 FaceFusion 和 ONNX Runtime
RUN python install.py --onnxruntime cuda-11.8 --skip-venv

# 關鍵步驟：使用官方 force-download 命令預下載所有模型
RUN python facefusion.py force-download

# 驗證模型已下載（應該在 .assets/models 目錄中）
RUN ls -la .assets/models/ && echo "Models downloaded successfully"

# 安裝 API 依賴
COPY requirements.txt /workspace/
RUN pip install -r /workspace/requirements.txt

# 複製處理程式
COPY handler.py /workspace/
WORKDIR /workspace

# 設置環境變數
ENV CUDA_VISIBLE_DEVICES=0
ENV PYTHONPATH=/workspace/facefusion:$PYTHONPATH

CMD ["python", "-u", "handler.py"]
