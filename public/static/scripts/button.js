$('#objectsSelection').on('click',function() {            
    selectedObjectList = $(this).val()
});        

function onoffswitchClick(cb) {
    this.disabled = true
    console.log("Clicked, new value = " + cb.checked);
    var userThreshold = document.getElementById("userThreshold").value
    console.log("User Threshold = " + userThreshold);

    if (cb.checked){
        console.log("Execute startDetection");
        fetch('/startDetection', {
        body: JSON.stringify({
            detection_model: "ssd_mobilenet_v1_coco",
            threshold: userThreshold,
            userid : userid
        }),
        headers: {
            'Content-Type': 'application/json'
        },
        method: 'POST'
        })
        .then((res) => { return res.json() })
        .then((answer) => console.log(" startDetection answer status: " + answer.status + ". Answer description: " + answer.description))
        .catch(function(error) {
                    console.log('There has been a problem with your startDetection fetch operation: ' + error.message);
                });
        
        detectionEnabled = true
    } else {
        console.log("Execute stopDetection");
        fetch('/stopDetection', {
        body: JSON.stringify({
            userid : userid
        }),
        headers: {
            'Content-Type': 'application/json'
        },
        method: 'POST'
        })
        .then((res) => { return res.json() })
        .then((answer) => console.log(" stopDetection answer status: " + answer.status + ". Answer description: " + answer.description))
        .catch(function(error) {
                    console.log('There has been a problem with your stopDetection fetch operation: ' + error.message);
                });
                
        detectionEnabled = false
        //clear the previous drawings
        drawCtx.clearRect(0, 0, drawCanvas.width, drawCanvas.height);
    }
    this.disabled = false
    
}

function setThreshold(inp) {
    var userThreshold = inp.value
    console.log("User Threshold setThreshold = " + userThreshold);

    fetch('/setThreshold', {
    body: JSON.stringify({
        threshold: userThreshold,
        userid : userid
    }),
    headers: {
        'Content-Type': 'application/json'
    },
    method: 'POST'
    })
    .then((res) => { return res.json() })
    .then((answer) => console.log("setThreshold answer status: " + answer.status + ". Answer description: " + answer.description))
    .catch(function(error) {
                console.log('There has been a problem with your setThreshold fetch operation: ' + error.message);
            });
    
}