import argparse
import asyncio
import json
import logging
import os
import ssl

import cv2
import object_detection_api

from aiohttp import web
from av import VideoFrame

from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder
from PIL import Image
import queue as queue
import threading
import ssl
import uuid
import ml_working as ml

# Config
ROOT = os.path.dirname(__file__)
max_size_queue = 2
DEBUG = True
KEY_MLCHANNEL = 'ml_channel'
default_detection_enabled = False
default_detection_model = 'ssd_mobilenet_v1_coco' # TODO gestire meglio
default_threshold = 0.5
push_notification_enabled = True

#Global variable
ml_queue = queue.Queue(max_size_queue)
pcs = dict()
dcs = dict()
objectDetectionConfigs = dict()

def detect_object(image_object, threshold):
    return object_detection_api.get_objects(image_object, threshold)

# Classe trasformazione track
class VideoTransformTrack(VideoStreamTrack):
    def __init__(self, track, identifier):
        super().__init__()  # don't forget this!
        self.counter = 0
        self.track = track
        self.identifier = identifier

    async def recv(self):
        frame = await self.track.recv()
        self.counter += 1
        try:
            objectDetectionConfig = objectDetectionConfigs.get(self.identifier, None)
            if objectDetectionConfig is None:
                # Initialize Object Detection Config
                objectDetectionConfig = object_detection_api.DetectionObjectConfigHolder (default_detection_enabled, default_detection_model, default_threshold)
                objectDetectionConfigs[self.identifier] = objectDetectionConfig
                print('Init objectDetectionConfig for id: ' + str(self.identifier) + ': ' + str(objectDetectionConfig))
            
            if objectDetectionConfig.detection_enabled:
                mlUnitWork = ml.ML_UnitWork(ml.OBJECT_DETECTION_TASK_TYPE, frame.to_image(), objectDetectionConfig, self.identifier)
                ml_queue.put_nowait(mlUnitWork)
            return frame
        except queue.Full:
            # Se la coda è piena non scrivo in coda
            return frame
        except Exception as e:
            print('RECV VideoTransformTrack error:' + str(e))
            return frame

class DetectionDataHolder(threading.Thread):
    def __init__(self, loop):
        """
        Receives bounding box, class and scores data from ML Module.
        """
        threading.Thread.__init__(self)
        self.name = 'Detection Objects DataHandler'
        self.done = False
        self.data = "{}"
        self.loop = loop

    def run(self):
        print("Starting thread " + self.name)
        asyncio.set_event_loop(self.loop)
        self.loop.call_soon_threadsafe(self.update(self.name))
        print("Exiting thread " + self.name)

    def update(self, threadName):
        while not self.done:
            try:
                mlUnitWork = ml_queue.get()
                # print('DetectionDataHolder Recuperato oggtto dalla coda. Task type: ' + mlUnitWork.taskType)
                if mlUnitWork.taskType == ml.OBJECT_DETECTION_TASK_TYPE:
                    threshold = mlUnitWork.taskConfig.threshold
                    detection_enabled = mlUnitWork.taskConfig.detection_enabled
                    if detection_enabled:
                        self.data = detect_object(mlUnitWork.data, threshold)
                        if push_notification_enabled:
                            channel = dcs[mlUnitWork.taskIdentifier]
                            channel.send(self.data)
                            print('DetectionDataHolder Send to userid: ' + mlUnitWork.taskIdentifier)
                else:
                    print ('ML Task type not known: ' + mlUnitWork.taskType)
            except Exception as e:
                print("Error occured receiving data on ML client " + str(e))

    def stop(self):
        self.done = True
        self.data = "{}"

    def cleanData(self):
        self.data = "{}"

detectionData = None

async def setThreshold(request):
    try:
        params = await request.json()

        uuid = params['userid'] # TODO raise exception if not present

        old_threshold = objectDetectionConfigs[uuid].threshold
        new_threshold = float(params.get('threshold', default_threshold))
        objectDetectionConfigs[uuid].threshold = new_threshold

        if DEBUG:
            print ('************* setThreshold Config: ' + str(objectDetectionConfigs[uuid]))
        
        response_obj = { 'status' : 'success',
                         'description': 'Threshold new value ({new_t}) set successfully (old value: {old_t})'.format(old_t=str(old_threshold),new_t=str(new_threshold))
                       }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        if DEBUG:
            print ('Error setThreshold ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'description': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def startDetection(request):
    try:
        params = await request.json()

        uuid = params['userid'] # TODO raise exception if not present

        objectDetectionConfigs[uuid].detection_enabled = True
        objectDetectionConfigs[uuid].detection_model = params.get('detection_model', default_detection_model)
        objectDetectionConfigs[uuid].threshold = float(params.get('threshold', default_threshold))

        if DEBUG:
            print ('************* startDetection Config: ' + str(objectDetectionConfigs[uuid]))
        
        response_obj = { 'status' : 'success',
                        'description': 'Object Detection Enabled for peerID {peerID}'.format(peerID=uuid)
                     }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        if DEBUG:
            print ('Error startDetection ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'description': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def stopDetection(request):
    try:
        params = await request.json()

        uuid = params['userid'] # TODO raise exception if not present

        objectDetectionConfigs[uuid].detection_enabled = False

        if DEBUG:
            print ('************* stopDetection Config: ' + str(objectDetectionConfigs[uuid]))
        
        response_obj = { 'status' : 'success',
                         'description': 'Object Detection Stopped for peerID {peerID}'.format(peerID=uuid)
                     }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        print ('Error stopDetection ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'description': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def index(request):
    content = open(os.path.join(ROOT + 'public/', 'index.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def javascript(request):
    content = open(os.path.join(ROOT + 'public/', 'client.js'), 'r').read()
    return web.Response(content_type='application/javascript', text=content)

async def generate_uuid():
    return str(uuid.uuid4())

async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(
        sdp=params['sdp'],
        type=params['type'])

    # Generate a random identifier
    userid = await generate_uuid()

    pc = RTCPeerConnection()
    pcs[userid] = pc

    # prepare local media
    recorder = MediaBlackhole()

    # ricezione evento datachannel (quando il peer all'altro capo effettua una createDataChannel)
    @pc.on('datachannel')
    def on_datachannel(channel):
        dcs[userid] = channel
        @channel.on('message')
        def on_message(message):
            try:
                print("Received message: " + message)
            except:
                print("Failed receiving module data.")
                channel.send("{}")

    @pc.on('iceconnectionstatechange')
    async def on_iceconnectionstatechange():
        print('ICE connection state is %s' % pc.iceConnectionState)
        if pc.iceConnectionState == 'failed':
            await pc.close()
            pcs.pop(userid, None)
            dcs.pop(userid, None)
            objectDetectionConfigs.pop(userid, None)

    @pc.on('track')
    def on_track(track):
        print('Track %s received' % track.kind)

        if track.kind == 'video':
            local_video = VideoTransformTrack(track, userid)
            pc.addTrack(local_video)
            print("Added local video (cnn).")

        @track.on('ended')
        async def on_ended():
            print('Track %s ended' % track.kind)
            await recorder.stop()

    # handle offer
    await pc.setRemoteDescription(offer)
    await recorder.start()

    # send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Start thread detection
    loop = asyncio.get_event_loop()
    detectionData = DetectionDataHolder(loop)
    detectionData.start()

    return web.Response(
        content_type='application/json',
        text=json.dumps({
            'sdp': pc.localDescription.sdp,
            'type': pc.localDescription.type,
            'userid': userid
        }))

async def on_shutdown(app):
    # close peer connections
    coros = [pcs[key].close() for key in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='WebRTC audio / video / data-channels demo')
    parser.add_argument('--cert-file', help='SSL certificate file (for HTTPS)')
    parser.add_argument('--key-file', help='SSL key file (for HTTPS)')
    parser.add_argument('--port', type=int, default=8080,
                        help='Port for HTTP server (default: 8080)')
    parser.add_argument('--verbose', '-v', action='count')
    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)

    if args.cert_file:
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(args.cert_file, args.key_file)
        print('Loaded SSL Certificate File: {cert_file} - Key File: {key_file}'.format(cert_file=args.cert_file, key_file=args.key_file))
    else:
        ssl_context = None

    app = web.Application()

    app.on_shutdown.append(on_shutdown)
    
    # routing path
    app.router.add_get('/', index)
    app.router.add_get('/client.js', javascript)
    app.router.add_post('/offer', offer)
    app.router.add_post('/startDetection', startDetection)
    app.router.add_post('/stopDetection', stopDetection)
    app.router.add_post('/setThreshold', setThreshold)
    
    # static files
    app.router.add_static('/static/', ROOT + 'public/static/', name='static',show_index=True)

    # start server
    web.run_app(app, port=args.port, ssl_context=ssl_context)
