
"""Runs the inference on the OAK-D, but instead of using the camera it uses an external file

** mostly copied from random examples (https://github.com/luxonis/depthai-experiments)
"""

from pathlib import Path
import sys
import cv2
import depthai as dai
import numpy as np
from time import monotonic

nnPath = "models/20221214_bigkahunaburger_6shavesonly.blob"

mediaPath = "pics/test_google_earth.png"
# mediaPath = "pics/depth_video.mov"

num_of_classes = 3 # define the number of classes in the dataset
nn_shape = 256

def decode_deeplabv3p(output_tensor):
    output = output_tensor.reshape(nn_shape,nn_shape)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(3,3))

    # scale to [0 ... 2555] and apply colormap
    output = np.array(output) * (255/num_of_classes)

    output = cv2.dilate(output,kernel,iterations = 1)
    output = output.astype(np.uint8)

    output_colors = cv2.applyColorMap(output, cv2.COLORMAP_JET)

    # reset the color of 0 class
    output_colors[output == 0] = [0,0,0]

    return output_colors

def show_deeplabv3p(output_colors, frame):
    return cv2.addWeighted(frame,1, output_colors,0.3,0)


# Create pipeline
pipeline = dai.Pipeline()
pipeline.setOpenVINOVersion(version = dai.OpenVINO.VERSION_2021_4)

# Define sources and outputs
nn = pipeline.create(dai.node.NeuralNetwork)

xinFrame = pipeline.create(dai.node.XLinkIn)
nnOut = pipeline.create(dai.node.XLinkOut)

xinFrame.setStreamName("inFrame")
nnOut.setStreamName("nn")

# Properties
nn.setBlobPath(nnPath)
nn.setNumInferenceThreads(2)
nn.input.setBlocking(False)

# Linking
xinFrame.out.link(nn.input)
nn.out.link(nnOut.input)

# Connect to device and start pipeline
with dai.Device(pipeline) as device:

    # Input queue will be used to send video frames to the device.
    qIn = device.getInputQueue(name="inFrame")
    # Output queue will be used to get nn data from the video frames.
    qDet = device.getOutputQueue(name="nn", maxSize=4, blocking=False)

    frame = None
    output_colors = None

    def to_planar(arr: np.ndarray, shape: tuple) -> np.ndarray:
        return cv2.resize(arr, shape).transpose(2, 0, 1).flatten()

    cap = cv2.VideoCapture(mediaPath)
    using_video = cap.isOpened()
    if using_video:
        print(f"Using video...{mediaPath}")
        def test():
            return cap.isOpened()
    else:
        print(f"Using image...{mediaPath}")
        frame = cv2.imread(mediaPath, cv2.IMREAD_COLOR)
        def test():
            return True
    
    cv2.namedWindow("rgb", cv2.WINDOW_NORMAL)        
    while test():
        if using_video:
            read_correctly, new_frame = cap.read()
            if read_correctly:
                frame = new_frame
        img = dai.ImgFrame()
        img.setData(to_planar(frame, (nn_shape, nn_shape)))
        img.setTimestamp(monotonic())
        img.setWidth(nn_shape)
        img.setHeight(nn_shape)
        qIn.send(img)

        inDet = qDet.tryGet()

        if inDet is not None:
            lay1 = np.array(inDet.getFirstLayerInt32()).reshape(nn_shape,nn_shape)
            output_colors = decode_deeplabv3p(lay1)

        if (frame is not None) and (output_colors is not None):
            cv2.imshow("rgb", show_deeplabv3p(output_colors, cv2.resize(frame, (nn_shape,nn_shape))))

        if cv2.waitKey(1) == ord('q'):
            break