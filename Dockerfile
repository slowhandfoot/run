FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    git ffmpeg libgl1 libglib2.0-0 libsm6 libxext6 \
    libxrender-dev libgomp1 python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# 安裝 FaceFusion
RUN git clone https://github.com/facefusion/facefusion.git
WORKDIR /workspace/facefusion
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN python install.py --onnxruntime cuda-11.8 --skip-venv || true

# 安裝 API 依賴
COPY requirements.txt /workspace/
RUN pip install -r /workspace/requirements.txt

# 複製處理程式
COPY handler.py /workspace/
WORKDIR /workspace

CMD ["python", "-u", "handler.py"]
