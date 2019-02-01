function setupScreenAndCanvas(){
    //Set canvas sizes base don input video
    drawCanvas.width = video.videoWidth;
    drawCanvas.height = video.videoHeight;

    //Some styles for the drawcanvas
    drawCtx.lineWidth = 4;
    drawCtx.strokeStyle = "cyan";
    drawCtx.font = "20px Verdana";
    drawCtx.fillStyle = "cyan";

    console.log("setup screen and canvas");
}

//event metadata is ready - we need the video size
video.onloadedmetadata = () => {
    console.log("video metadata ready");
    setupScreenAndCanvas();     
};

video.onplaying = () => {
    console.log("video playing");
    setupScreenAndCanvas();     
};