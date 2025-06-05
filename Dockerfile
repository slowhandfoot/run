FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /

# 安裝基本依賴
RUN apt-get update && apt-get install -y git wget ffmpeg && rm -rf /var/lib/apt/lists/*

# 克隆 FaceFusion（不指定版本）
RUN git clone https://github.com/facefusion/facefusion

# 安裝依賴
WORKDIR /facefusion
RUN pip install -r requirements.txt

# 安裝 onnxruntime
RUN pip install onnxruntime-gpu

# 安裝 RunPod
RUN pip install runpod

# 複製 handler
COPY handler.py /handler.py

# 設定工作目錄
WORKDIR /

CMD ["python", "-u", "/handler.py"]
