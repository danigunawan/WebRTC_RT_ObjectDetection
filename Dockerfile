FROM tensorflow/tensorflow:nightly-py3-jupyter

# Install FFmpeg 3.2 via PPA
RUN apt-get install -y software-properties-common
RUN add-apt-repository ppa:jonathonf/ffmpeg-3 -y
RUN apt-get update && yes | apt-get upgrade
RUN apt-get install -y ffmpeg libav-tools x264 x265
RUN apt-get install -y git curl unzip wget vim emacs nano
RUN apt-get install -y build-essential libssl-dev libffi-dev libgtk2.0-dev
RUN apt-get install -y libavdevice-dev libavfilter-dev libopus-dev libvpx-dev pkg-config
RUN pip install aiohttp  
RUN pip install aiortc 
RUN pip install opencv-python

# Install Tensorflow Object Detection API
RUN apt-get install -y git curl unzip wget vim emacs nano

RUN mkdir -p /tensorflow/models

# Get the tensorflow models research directory, and move it into tensorflow
# source folder to match recommendation of installation
RUN git clone --depth 1 https://github.com/tensorflow/models.git && \
    mv models /tensorflow/

# Install the Tensorflow Object Detection API from here
# https://github.com/tensorflow/models/blob/master/research/object_detection/g3doc/installation.md

# Install object detection api dependencies
RUN apt-get install -y protobuf-compiler python-pil python-lxml python-tk && \
    pip install Cython && \
    pip install contextlib2 && \
    pip install jupyter && \
    pip install matplotlib && \
	pip install image && \
	pip install pillow && \
	pip install lxml && \
	pip install six 

# Install pycocoapi
RUN git clone --depth 1 https://github.com/cocodataset/cocoapi.git && \
    cd cocoapi/PythonAPI && \
    make -j8 && \
    cp -r pycocotools /tensorflow/models/research && \
    cd ../../ && \
    rm -rf cocoapi

# Get protoc 3.0.0, rather than the old version already in the container
RUN curl -OL "https://github.com/protocolbuffers/protobuf/releases/download/v3.6.1/protoc-3.6.1-linux-x86_64.zip" && \
    unzip protoc-3.6.1-linux-x86_64.zip -d proto3 && \
    mv proto3/bin/* /usr/local/bin && \
    mv proto3/include/* /usr/local/include && \
    rm -rf proto3 protoc-3.6.1-linux-x86_64.zip

# Run protoc on the object detection repo
RUN cd /tensorflow/models/research && \
	protoc object_detection/protos/*.proto --python_out=.

# Set the PYTHONPATH to finish installing the API
ENV PYTHONPATH $PYTHONPATH:/tensorflow/models/research:/tensorflow/models/research/slim
# 

# Download Tensorflow zoo model
RUN mkdir app
WORKDIR /app

RUN wget -nv http://download.tensorflow.org/models/object_detection/ssd_mobilenet_v1_coco_2018_01_28.tar.gz && \
	tar xvzf ssd_mobilenet_v1_coco_2018_01_28.tar.gz
	
# Deploy application file
COPY . /app

# Start Python server
CMD ["python","server.py","--cert-file", "ssl/domain.crt", "--key-file", "ssl/domain.key"]

EXPOSE 8888 8080
