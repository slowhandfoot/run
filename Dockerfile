FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /

# 安裝基本依賴
RUN apt-get update && apt-get install -y git wget && rm -rf /var/lib/apt/lists/*

# 克隆 FaceFusion
RUN git clone https://github.com/facefusion/facefusion --branch 2.6.1 --single-branch

# 安裝依賴
WORKDIR /facefusion
RUN pip install -r requirements.txt

# 下載模型
RUN python install.py --onnxruntime cuda --skip-conda

# 安裝 RunPod
RUN pip install runpod

# 複製 handler
COPY handler.py /handler.py

# 設定工作目錄
WORKDIR /

CMD ["python", "-u", "/handler.py"]
