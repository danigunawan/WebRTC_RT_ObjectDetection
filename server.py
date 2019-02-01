# TODO:
# Quando faccio stopDetection deve cancellare il dato salvato in DataHolder
#   non funziona il cleanData in stopDetection perché evidentemente dopo il processo scoda e riscrive di nuovo l'oggetto DataHolder
# lato client quando ricevo messaggio vuoto {} devo pulire il canvas
# lato client quando mando stopDetection deve pulire il canvas altrimenti rimane l'ultima osservazione fatta
# gestione HTTPS
# modifica frontend gestione push notification e non polling

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

# Config
ROOT = os.path.dirname(__file__)
num_fetch_threads = 1
max_size_queue = 2
DEBUG = True
KEY_MLCHANNEL = 'ml_channel'
default_detection_enabled = False
default_detection_model = 'ssd_mobilenet_v1_coco' # TODO gestire meglio
default_threshold = 0.5
push_notification_enabled = True

# Config Detection Object Variable Class
class DetectionObjectConfigHolder():
    def __init__(self, detection_enabled, detection_model, threshold):
        print ('Costruttore DetectionObjectConfigHolder richiamato')
        self.detection_enabled = detection_enabled
        self.detection_model = detection_model
        self.threshold = float(threshold)
    
    def __str__(self):
        return 'detection_enabled: {enable}, detection_model: {detection_model},  threshold: {threshold}'.format(enable=self.detection_enabled, detection_model=self.detection_model, threshold=self.threshold )


#Global variable
ml_queue = queue.Queue(max_size_queue)
pcs = set()
dcs = dict()

# Variable manageable by client 
detectionObjectConfigHolder = DetectionObjectConfigHolder (default_detection_enabled, default_detection_model, default_threshold)

def detect_object(image_object, threshold):
    return object_detection_api.get_objects(image_object, threshold)

# TODO cancellare metodo
def detect_object_worker(q, threshold):
    while True:
        print(q.qsize())
        image_object = q.get()
        print (object_detection_api.get_objects(image_object, threshold))

# Classe trasformazione track
class VideoTransformTrack(VideoStreamTrack):
    def __init__(self, track):
        super().__init__()  # don't forget this!
        self.counter = 0
        self.track = track

    async def recv(self):
        frame = await self.track.recv()
        self.counter += 1
        try:
            if detectionObjectConfigHolder.detection_enabled:
                image_object = frame.to_image()
                ml_queue.put_nowait(image_object)
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
        Receives bounding box, class and scores data from ML Server.
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
                if KEY_MLCHANNEL in dcs:
                    channel = dcs[KEY_MLCHANNEL]
                else:
                    channel = None
                image_object = ml_queue.get()
                self.data = detect_object(image_object, detectionObjectConfigHolder.threshold)
                # Send object detection on RTC Data channel
                if push_notification_enabled and detectionObjectConfigHolder.detection_enabled and channel is not None:
                    channel.send(self.data)
            except Exception as e:
                print("Error occured receiving data on ML client " + str(e))

    def stop(self):
        self.done = True
        self.data = "{}"

    def cleanData(self):
        self.data = "{}"

detectionData = None

async def getConfigVariable(request):
    try:
        print ('### detectionObjectConfigHolder ### :  ' + str(detectionObjectConfigHolder))
        response_obj = { 'detection_enabled' : detectionObjectConfigHolder.detection_enabled,
                         'detection_model' : detectionObjectConfigHolder.detection_model,
                         'threshold' : detectionObjectConfigHolder.threshold
                       }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        if DEBUG:
            print ('Error startDetection ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def startDetection(request):
    try:
        detectionObjectConfigHolder.detection_enabled = True
        detectionObjectConfigHolder.detection_model = request.query.get('detection_model', default_detection_model)
        detectionObjectConfigHolder.threshold = float(request.query.get('threshold', default_threshold))

        if DEBUG:
            print ('************* startDetection Config: ' + str(detectionObjectConfigHolder))
        
        response_obj = { 'status' : 'success' }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        if DEBUG:
            print ('Error startDetection ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def stopDetection(request):
    try:
        detectionObjectConfigHolder.detection_enabled = False
        detectionData.cleanData()

        if DEBUG:
            print ('************* stopDetection Config: ' + str(detectionObjectConfigHolder))
        
        response_obj = { 'status' : 'success' }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        print ('Error stopDetection ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def sendMessage(request):
    try:
        message = request.query.get('message', 'sendMessage')

        channel = dcs[KEY_MLCHANNEL]
        channel.send(message)
                
        response_obj = { 'status' : 'success' }
        # return a success json response with status code 200 i.e. 'OK'
        return web.Response(text=json.dumps(response_obj), status=200)
    except Exception as e:
        print ('Error sendMessage ' + str(e))
        # Bad path where name is not set
        response_obj = { 'status' : 'failed', 'reason': str(e) }
        # return failed with a status code of 500 i.e. 'Server Error'
        return web.Response(text=json.dumps(response_obj), status=500)

async def index(request):
    content = open(os.path.join(ROOT + 'public/', 'index.html'), 'r').read()
    return web.Response(content_type='text/html', text=content)


async def javascript(request):
    content = open(os.path.join(ROOT + 'public/', 'client.js'), 'r').read()
    return web.Response(content_type='application/javascript', text=content)


async def offer(request):
    params = await request.json()
    offer = RTCSessionDescription(
        sdp=params['sdp'],
        type=params['type'])

    pc = RTCPeerConnection()
    pcs.add(pc)

    # prepare local media
    recorder = MediaBlackhole()

    # ricezione evento datachannel (quando il peer all'altro capo effettua una createDataChannel)
    @pc.on('datachannel')
    def on_datachannel(channel):
        dcs[KEY_MLCHANNEL] = channel
        @channel.on('message')
        def on_message(message):
            try:
                if isinstance(message, str) and message.startswith('getNewObjectDetection'):
                    a = 1
                    #channel.send(detectionData.data)
                elif isinstance(message, str) and message.startswith('Connected'):
                    a = 2
                    #channel.send('Datachannel connection established!')
            except:
                print("Failed receiving module data.")
                channel.send("{}")

    @pc.on('iceconnectionstatechange')
    async def on_iceconnectionstatechange():
        print('ICE connection state is %s' % pc.iceConnectionState)
        if pc.iceConnectionState == 'failed':
            await pc.close()
            pcs.discard(pc)

    @pc.on('track')
    def on_track(track):
        print('Track %s received' % track.kind)

        if track.kind == 'video':
            local_video = VideoTransformTrack(track)
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
            'type': pc.localDescription.type
        }))

async def on_shutdown(app):
    # close peer connections
    coros = [pc.close() for pc in pcs]
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

# Set up some threads to fetch ML object detection
    # for i in range(num_fetch_threads):
    #     worker = Thread(target=detect_object_worker, args=(ml_queue,threshold))
    #     worker.setDaemon(True)
    #     worker.start()
    #     print('Avviato thread ML Object Detection Worker')

    app = web.Application()

    app.on_shutdown.append(on_shutdown)
    
    # routing path
    app.router.add_get('/', index)
    app.router.add_get('/client.js', javascript)
    app.router.add_post('/offer', offer)
    app.router.add_post('/startDetection', startDetection)
    app.router.add_post('/stopDetection', stopDetection)
    app.router.add_get('/getConfigVariable', getConfigVariable)
    app.router.add_post('/sendMessage', sendMessage)
    
    # static files
    app.router.add_static('/static/', ROOT + 'public/static/', name='static',show_index=True)

    # start server
    web.run_app(app, port=args.port, ssl_context=ssl_context)
