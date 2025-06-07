FROM runpod/pytorch:2.0.1-py3.10-cuda11.8.0-devel-ubuntu22.04

WORKDIR /workspace

# 只安裝必要的系統依賴
RUN apt-get update && apt-get install -y \
    git ffmpeg python3-pip \
    && rm -rf /var/lib/apt/lists/*

# 安裝 RunPod 和基本依賴
COPY requirements.txt /workspace/
RUN pip install --upgrade pip
RUN pip install -r /workspace/requirements.txt

# 複製處理程式
COPY handler.py /workspace/

CMD ["python", "-u", "handler.py"]
