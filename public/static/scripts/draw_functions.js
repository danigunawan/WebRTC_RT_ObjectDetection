//draw boxes and labels on each detected object
function drawBoxes(objects) {

    //clear the previous drawings
    drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);

    //filter out objects that contain a class_name and then draw boxes and labels on each
    objects.filter(object => object.class_name).forEach(object => {

        let x = object.x * drawCanvas.width;
        let y = object.y * drawCanvas.height;
        let width = (object.width * drawCanvas.width) - x;
        let height = (object.height * drawCanvas.height) - y;

        //flip the x axis if local video is mirrored
        if (mirror) {
            x = drawCanvas.width - (x + width)
        }

        drawCtx.fillText(object.class_name + " - " + Math.round(object.score * 100) + "%", x + 5, y + 20);
        drawCtx.strokeRect(x, y, width, height);
        
    });
}

function intervalWebcamFrame (){

    let currentData = tempData;
    
    if (currentData != "{}") {
        //console.log('Elaborating message received: ' + currentData)

        let objects = JSON.parse(currentData);
        //draw the boxes
        drawBoxes(objects);
    } else {
        //clear the previous drawings
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    }
    
};








